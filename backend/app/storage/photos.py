"""Private crew-photo storage with size and type limits (T052).

Validation:
- The type comes from the file's own leading bytes, never its name. Allowed: JPEG, PNG,
  WebP, and HEIC/HEIF (phone photos). Everything else is rejected, including SVG and GIF.
- A declared content type that disagrees with the detected type is rejected.
- Uploads are read in chunks and stopped at `PHOTO_MAX_BYTES` (5 MB by default), so an
  oversized upload is never held in memory whole.

Storage:
- Every photo gets a new random key such as `photos/3f2a….jpg`. The uploader's file name
  never becomes part of a path.
- Photos are private. Local files sit in `PHOTO_LOCAL_DIR`, which git ignores. Vultr
  objects are stored with a private ACL and viewed through short-lived signed URLs.
- `get_photo_store()` uses Vultr Object Storage when all four `VULTR_OBJECT_STORAGE_*`
  settings are set, and the local directory otherwise (development).

A report stores the key as its photo reference. Routes decide who may view it.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Protocol
from uuid import uuid4

from app.storage.settings import StorageSettings, get_storage_settings

CHUNK_BYTES = 64 * 1024
KEY_PATTERN = re.compile(r"^photos/[0-9a-f]{32}\.(jpg|png|webp|heic)$")
_HEIF_BRANDS = frozenset({b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1"})


@dataclass(frozen=True)
class PhotoType:
    content_type: str
    extension: str


JPEG = PhotoType("image/jpeg", "jpg")
PNG = PhotoType("image/png", "png")
WEBP = PhotoType("image/webp", "webp")
HEIC = PhotoType("image/heic", "heic")
DECLARED_ALIASES = {"image/jpg": "image/jpeg", "image/heif": "image/heic"}


class InvalidPhoto(ValueError):
    """An upload was rejected. `reason` is a stable code for the API response."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class StoredPhoto:
    key: str
    content_type: str
    size_bytes: int


def detect_type(data: bytes) -> PhotoType | None:
    """Photo type from the file's leading bytes, or None when it isn't an allowed photo."""
    if data.startswith(b"\xff\xd8\xff"):
        return JPEG
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return WEBP
    if len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in _HEIF_BRANDS:
        return HEIC
    return None


def validate_photo(
    data: bytes, declared_content_type: str | None = None, max_bytes: int | None = None
) -> PhotoType:
    limit = max_bytes if max_bytes is not None else get_storage_settings().photo_max_bytes
    if not data:
        raise InvalidPhoto("empty", "The photo is empty.")
    if len(data) > limit:
        raise InvalidPhoto("too_large", f"The photo is larger than {limit // (1024 * 1024)} MB.")
    detected = detect_type(data)
    if detected is None:
        raise InvalidPhoto("unsupported_type", "Only JPEG, PNG, WebP, or HEIC photos are allowed.")
    if declared_content_type:
        declared = declared_content_type.split(";")[0].strip().lower()
        declared = DECLARED_ALIASES.get(declared, declared)
        if declared not in ("application/octet-stream", detected.content_type):
            raise InvalidPhoto(
                "type_mismatch",
                f"The file is {detected.content_type}, not the declared {declared}.",
            )
    return detected


def read_limited(stream: BinaryIO, max_bytes: int | None = None) -> bytes:
    """Read an upload stream, stopping as soon as it passes the size limit."""
    limit = max_bytes if max_bytes is not None else get_storage_settings().photo_max_bytes
    chunks: list[bytes] = []
    total = 0
    while chunk := stream.read(CHUNK_BYTES):
        total += len(chunk)
        if total > limit:
            raise InvalidPhoto(
                "too_large", f"The photo is larger than {limit // (1024 * 1024)} MB."
            )
        chunks.append(chunk)
    return b"".join(chunks)


class PhotoStore(Protocol):
    def save(self, data: bytes, photo_type: PhotoType) -> StoredPhoto: ...

    def load(self, key: str) -> bytes: ...


class LocalPhotoStore:
    """Development storage in a private local directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def save(self, data: bytes, photo_type: PhotoType) -> StoredPhoto:
        key = new_key(photo_type)
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:  # never overwrite an existing photo
            handle.write(data)
        return StoredPhoto(key, photo_type.content_type, len(data))

    def load(self, key: str) -> bytes:
        return (self.root / check_key(key)).read_bytes()


class VultrPhotoStore:
    """Vultr Object Storage (S3-compatible). Objects are private."""

    def __init__(self, bucket: str, client: Any, url_seconds: int = 900) -> None:
        self.bucket = bucket
        self.client = client
        self.url_seconds = url_seconds

    @classmethod
    def from_settings(cls, settings: StorageSettings) -> "VultrPhotoStore":
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=settings.vultr_object_storage_endpoint,
            aws_access_key_id=settings.vultr_object_storage_access_key.get_secret_value(),
            aws_secret_access_key=settings.vultr_object_storage_secret_key.get_secret_value(),
        )
        return cls(settings.vultr_object_storage_bucket, client, settings.photo_url_seconds)

    def save(self, data: bytes, photo_type: PhotoType) -> StoredPhoto:
        key = new_key(photo_type)
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=photo_type.content_type,
            ACL="private",
        )
        return StoredPhoto(key, photo_type.content_type, len(data))

    def load(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=check_key(key))
        return response["Body"].read()

    def signed_url(self, key: str) -> str:
        """Short-lived link for an authorized viewer. The object itself stays private."""
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": check_key(key)},
            ExpiresIn=self.url_seconds,
        )


def save_photo(
    store: PhotoStore,
    data: bytes,
    declared_content_type: str | None = None,
    max_bytes: int | None = None,
) -> StoredPhoto:
    """Validate, then store. Nothing is written for an invalid upload."""
    return store.save(data, validate_photo(data, declared_content_type, max_bytes))


def new_key(photo_type: PhotoType) -> str:
    return f"photos/{uuid4().hex}.{photo_type.extension}"


def check_key(key: str) -> str:
    """Accept only keys this module generated, so a key can never escape the store."""
    if not KEY_PATTERN.fullmatch(key):
        raise InvalidPhoto("invalid_key", "Unknown photo reference.")
    return key


_store: PhotoStore | None = None


def get_photo_store() -> PhotoStore:
    """FastAPI dependency: Vultr when fully configured, else the local directory."""
    global _store
    if _store is None:
        settings = get_storage_settings()
        if settings.vultr_configured:
            _store = VultrPhotoStore.from_settings(settings)
        else:
            _store = LocalPhotoStore(settings.photo_local_dir)
    return _store
