"""T052: private photo storage with size and type limits."""

import io

import pytest

from app.storage import photos
from app.storage.photos import (
    InvalidPhoto,
    LocalPhotoStore,
    VultrPhotoStore,
    check_key,
    detect_type,
    read_limited,
    save_photo,
    validate_photo,
)
from app.storage.settings import StorageSettings

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 100
HEIC = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 100
LIMIT = 1024


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, dict] = {}

    def put_object(self, **kwargs) -> None:
        self.objects[kwargs["Key"]] = kwargs

    def get_object(self, Bucket: str, Key: str) -> dict:
        return {"Body": io.BytesIO(self.objects[Key]["Body"])}

    def generate_presigned_url(self, op: str, Params: dict, ExpiresIn: int) -> str:
        return f"https://signed.example/{Params['Bucket']}/{Params['Key']}?expires={ExpiresIn}"


# ---- type detection ----


@pytest.mark.parametrize(
    ("data", "content_type"),
    [(JPEG, "image/jpeg"), (PNG, "image/png"), (WEBP, "image/webp"), (HEIC, "image/heic")],
)
def test_allowed_photo_types_are_detected_from_content(data, content_type) -> None:
    assert validate_photo(data, max_bytes=LIMIT).content_type == content_type


# ---- invalid uploads are rejected (done check) ----


@pytest.mark.parametrize(
    ("data", "declared", "reason"),
    [
        (b"", None, "empty"),
        (JPEG + b"\x00" * LIMIT, None, "too_large"),
        (b"hello, not a photo", "image/jpeg", "unsupported_type"),  # text renamed .jpg
        (b"<svg xmlns='http://www.w3.org/2000/svg'/>", "image/svg+xml", "unsupported_type"),
        (b"GIF89a" + b"\x00" * 20, "image/gif", "unsupported_type"),
        (b"%PDF-1.7" + b"\x00" * 20, "application/pdf", "unsupported_type"),
        (b"MZ" + b"\x00" * 20, None, "unsupported_type"),  # Windows executable
        (PNG, "image/jpeg", "type_mismatch"),
    ],
)
def test_invalid_uploads_are_rejected(data, declared, reason) -> None:
    with pytest.raises(InvalidPhoto) as error:
        validate_photo(data, declared, max_bytes=LIMIT)
    assert error.value.reason == reason


def test_declared_aliases_and_generic_type_are_accepted() -> None:
    assert validate_photo(JPEG, "image/jpg", max_bytes=LIMIT).extension == "jpg"
    assert validate_photo(JPEG, "image/jpeg; charset=binary", max_bytes=LIMIT)
    assert validate_photo(HEIC, "image/heif", max_bytes=LIMIT).extension == "heic"
    assert validate_photo(PNG, "application/octet-stream", max_bytes=LIMIT)


def test_size_limit_boundary() -> None:
    exact = JPEG + b"\x00" * (LIMIT - len(JPEG))
    assert len(exact) == LIMIT
    assert validate_photo(exact, max_bytes=LIMIT)
    with pytest.raises(InvalidPhoto):
        validate_photo(exact + b"\x00", max_bytes=LIMIT)


def test_default_limit_is_5_mb() -> None:
    assert StorageSettings(_env_file=None).photo_max_bytes == 5 * 1024 * 1024


def test_read_limited_stops_before_reading_everything() -> None:
    class Stream(io.BytesIO):
        reads = 0

        def read(self, size=-1):
            Stream.reads += 1
            return super().read(size)

    stream = Stream(JPEG + b"\x00" * (photos.CHUNK_BYTES * 10))
    with pytest.raises(InvalidPhoto) as error:
        read_limited(stream, max_bytes=photos.CHUNK_BYTES)
    assert error.value.reason == "too_large"
    assert Stream.reads == 2
    assert read_limited(io.BytesIO(PNG), max_bytes=LIMIT) == PNG


def test_detect_type_rejects_short_or_unknown_data() -> None:
    assert detect_type(b"\xff\xd8") is None
    assert detect_type(b"RIFF\x00\x00\x00\x00WAVE") is None
    assert detect_type(b"\x00\x00\x00\x18ftypisom") is None  # MP4 video, not HEIC


# ---- local store ----


def test_local_store_saves_privately_with_random_key(tmp_path) -> None:
    store = LocalPhotoStore(tmp_path)
    stored = save_photo(store, JPEG, "image/jpeg", max_bytes=LIMIT)
    assert stored.key.startswith("photos/") and stored.key.endswith(".jpg")
    assert stored.size_bytes == len(JPEG)
    assert store.load(stored.key) == JPEG
    assert (tmp_path / stored.key).is_file()
    second = save_photo(store, JPEG, max_bytes=LIMIT)
    assert second.key != stored.key


def test_invalid_upload_writes_nothing(tmp_path) -> None:
    with pytest.raises(InvalidPhoto):
        save_photo(LocalPhotoStore(tmp_path), b"not a photo", max_bytes=LIMIT)
    assert list(tmp_path.rglob("*")) == []


@pytest.mark.parametrize(
    "key",
    [
        "../secrets.env",
        "photos/../../etc/passwd",
        "photos/abc.jpg",
        "photos/" + "a" * 32 + ".exe",
        "/photos/" + "a" * 32 + ".jpg",
        "photos/" + "A" * 32 + ".jpg",
    ],
)
def test_keys_not_made_by_the_store_are_refused(tmp_path, key) -> None:
    with pytest.raises(InvalidPhoto) as error:
        LocalPhotoStore(tmp_path).load(key)
    assert error.value.reason == "invalid_key"
    with pytest.raises(InvalidPhoto):
        check_key(key)


# ---- Vultr store ----


def test_vultr_store_puts_private_objects_with_content_type() -> None:
    s3 = FakeS3()
    store = VultrPhotoStore("crew-photos", s3, url_seconds=900)
    stored = save_photo(store, PNG, "image/png", max_bytes=LIMIT)
    put = s3.objects[stored.key]
    assert put["Bucket"] == "crew-photos"
    assert put["ACL"] == "private"
    assert put["ContentType"] == "image/png"
    assert store.load(stored.key) == PNG
    assert store.signed_url(stored.key).endswith("?expires=900")


def test_vultr_store_refuses_foreign_keys() -> None:
    with pytest.raises(InvalidPhoto):
        VultrPhotoStore("crew-photos", FakeS3()).signed_url("../other-bucket/x.jpg")


# ---- choosing a backend ----


def test_uses_local_directory_unless_vultr_is_fully_configured(monkeypatch, tmp_path) -> None:
    partial = StorageSettings(
        vultr_object_storage_endpoint="https://ewr1.vultrobjects.com",
        vultr_object_storage_bucket="crew-photos",
        photo_local_dir=str(tmp_path),
        _env_file=None,
    )
    assert not partial.vultr_configured
    monkeypatch.setattr(photos, "_store", None)
    monkeypatch.setattr(photos, "get_storage_settings", lambda: partial)
    store = photos.get_photo_store()
    assert isinstance(store, LocalPhotoStore) and store.root == tmp_path


def test_full_vultr_settings_select_vultr(monkeypatch) -> None:
    full = StorageSettings(
        vultr_object_storage_endpoint="https://ewr1.vultrobjects.com",
        vultr_object_storage_access_key="key",
        vultr_object_storage_secret_key="s3cr3t-value-123",
        vultr_object_storage_bucket="crew-photos",
        _env_file=None,
    )
    assert full.vultr_configured
    assert "s3cr3t-value-123" not in repr(full)
    monkeypatch.setattr(photos, "_store", None)
    monkeypatch.setattr(photos, "get_storage_settings", lambda: full)
    monkeypatch.setattr(
        photos.VultrPhotoStore,
        "from_settings",
        classmethod(lambda cls, s: cls(s.vultr_object_storage_bucket, FakeS3())),
    )
    assert isinstance(photos.get_photo_store(), VultrPhotoStore)
