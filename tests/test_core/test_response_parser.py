import json

import pytest

from app.core.response_parser import ParseError, parse_llm_response


def _valid_response_dict() -> dict:
    return {
        "summary": "Estimación para desarrollo de módulo de autenticación",
        "estimated_effort": {
            "optimistic": {"hours": 40},
            "expected": {"hours": 80},
            "pessimistic": {"hours": 120},
        },
        "suggested_breakdown": [
            {
                "name": "Backend API",
                "tasks": [
                    {"name": "Diseño de endpoints", "hours": 16},
                    {"name": "Implementación de lógica", "hours": 16},
                    {"name": "Testing unitario", "hours": 8},
                ],
            },
            {
                "name": "Testing",
                "tasks": [
                    {"name": "Pruebas de integración", "hours": 12},
                    {"name": "Pruebas e2e", "hours": 12},
                ],
            },
            {
                "name": "Docs",
                "tasks": [
                    {"name": "Documentación técnica", "hours": 8},
                    {"name": "Guía de uso", "hours": 8},
                ],
            },
        ],
        "suggested_technologies": ["Python", "FastAPI"],
        "notes": "Basado en 5 referencias.",
    }


class TestParseValidJSON:
    def test_parse_valid_json(self) -> None:
        raw = json.dumps(_valid_response_dict())
        result = parse_llm_response(raw, "EUR")
        assert result.summary == "Estimación para desarrollo de módulo de autenticación"
        assert result.estimated_effort["expected"].hours == 80
        assert len(result.suggested_breakdown) == 3

    def test_parse_json_in_markdown_block(self) -> None:
        data = _valid_response_dict()
        raw = f"```json\n{json.dumps(data)}\n```"
        result = parse_llm_response(raw, "EUR")
        assert result.summary == data["summary"]

    def test_parse_json_with_prefix_text(self) -> None:
        data = _valid_response_dict()
        raw = f"Here is the estimation JSON:\n{json.dumps(data)}"
        result = parse_llm_response(raw, "EUR")
        assert result.summary == data["summary"]


class TestCoherenceFixes:
    def test_coherence_reorder(self) -> None:
        data = _valid_response_dict()
        # Swap optimistic and pessimistic effort
        data["estimated_effort"]["optimistic"]["hours"] = 120
        data["estimated_effort"]["pessimistic"]["hours"] = 40
        raw = json.dumps(data)
        result = parse_llm_response(raw, "EUR")
        assert result.estimated_effort["optimistic"].hours < result.estimated_effort["expected"].hours
        assert result.estimated_effort["expected"].hours < result.estimated_effort["pessimistic"].hours


class TestErrors:
    def test_invalid_json_raises(self) -> None:
        with pytest.raises(ParseError):
            parse_llm_response("This is not JSON at all", "EUR")

    def test_missing_fields_raises(self) -> None:
        data = {"summary": "Incomplete response"}
        with pytest.raises(ParseError):
            parse_llm_response(json.dumps(data), "EUR")

    def test_negative_hours_raises(self) -> None:
        data = _valid_response_dict()
        data["estimated_effort"]["optimistic"]["hours"] = -8
        with pytest.raises(ParseError):
            parse_llm_response(json.dumps(data), "EUR")
