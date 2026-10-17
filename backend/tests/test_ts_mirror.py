"""Keeps frontend/src/types/api.ts field names in sync with the Pydantic schemas."""

import re
from pathlib import Path

import pytest
from pydantic import BaseModel

import app.schemas as schemas

TS_FILE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "types" / "api.ts"
INTERFACE = re.compile(r"export interface (\w+)(?: extends (\w+))? \{(.*?)\n\}", re.S)
FIELD = re.compile(r"^  (\w+)\??:", re.M)


def ts_interfaces() -> dict[str, set[str]]:
    found: dict[str, tuple[str | None, set[str]]] = {
        name: (parent, set(FIELD.findall(body)))
        for name, parent, body in INTERFACE.findall(TS_FILE.read_text(encoding="utf-8"))
    }

    def fields(name: str) -> set[str]:
        parent, own = found[name]
        return own | (fields(parent) if parent else set())

    return {name: fields(name) for name in found}


def pydantic_models() -> dict[str, type[BaseModel]]:
    return {
        name: obj
        for name in schemas.__all__
        if isinstance(obj := getattr(schemas, name), type)
        and issubclass(obj, BaseModel)
        and obj is not schemas.Schema
    }


TS = ts_interfaces()
# ModelOutput is Cache's Python-only interface; the frontend never receives it.
PYTHON_ONLY = {"ModelOutput"}


@pytest.mark.parametrize("name", sorted(set(pydantic_models()) - PYTHON_ONLY))
def test_ts_interface_matches_model(name: str) -> None:
    assert name in TS, f"{name} missing from {TS_FILE.name}"
    assert TS[name] == set(pydantic_models()[name].model_fields)
