"""T057: Gemini notice radius. Invalid or missing answers return None (category default)."""

import json

import pytest
from pydantic import BaseModel

from app.gemini import GeminiClient, suggest_notice_radius
from app.gemini.radius import MAX_RADIUS_MILES


def gemini(answer: dict | str | Exception, seen: list[str] | None = None) -> GeminiClient:
    def transport(prompt: str, schema: type[BaseModel]) -> str:
        if seen is not None:
            seen.append(prompt)
        if isinstance(answer, Exception):
            raise answer
        return answer if isinstance(answer, str) else json.dumps(answer)

    return GeminiClient("test-key", "test-model", 5.0, transport)


def answer(radius: float, evidence: list[str] | None = None) -> dict:
    return {
        "radius_miles": radius,
        "hazard_label": "downed line",
        "evidence": evidence or ["report:1"],
        "unknowns": [],
    }


def suggest(client: GeminiClient, evidence: list[str] | None = None) -> float | None:
    return suggest_notice_radius(
        "broken electrical pole or downed line",
        27.0,
        -82.0,
        "crew_report",
        evidence or ["report:1"],
        client=client,
    )


def test_valid_radius_is_returned() -> None:
    assert suggest(gemini(answer(1.5))) == 1.5


def test_maximum_radius_is_allowed() -> None:
    assert suggest(gemini(answer(MAX_RADIUS_MILES))) == MAX_RADIUS_MILES


@pytest.mark.parametrize("radius", [0, -1, 50.5, 500])
def test_out_of_range_radius_uses_the_default(radius: float) -> None:
    assert suggest(gemini(answer(radius))) is None


def test_unknown_evidence_uses_the_default() -> None:
    assert suggest(gemini(answer(2, ["made-up"]))) is None


@pytest.mark.parametrize(
    "bad",
    ["not json", '{"radius_miles": "far"}', json.dumps({**answer(2), "instruction": "Evacuate"})],
)
def test_invalid_output_uses_the_default(bad: str) -> None:
    assert suggest(gemini(bad)) is None


def test_timeout_or_error_uses_the_default() -> None:
    assert suggest(gemini(TimeoutError())) is None
    assert suggest(gemini(RuntimeError("boom"))) is None


def test_unconfigured_gemini_uses_the_default() -> None:
    assert suggest(GeminiClient(None, None, 5.0)) is None


def test_default_client_is_unconfigured_in_tests() -> None:
    # conftest blanks GEMINI_API_KEY, so this never reaches the network.
    assert suggest_notice_radius("flooding", 27.0, -82.0, "crew_report", ["report:1"]) is None


def test_prompt_carries_the_hazard_and_evidence_but_no_instruction_request() -> None:
    seen: list[str] = []
    suggest(gemini(answer(1), seen))
    prompt = seen[0]
    assert "broken electrical pole or downed line" in prompt
    assert '"crew_marked_present": true' in prompt
    assert "report:1" in prompt
    assert "Do not write instructions" in prompt
