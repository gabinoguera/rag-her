import json

import pytest

from app.core.response_parser import ParseError, parse_llm_response


def _valid_response_dict(currency: str = "EUR") -> dict:
    return {
        "summary": "Estimación para desarrollo de módulo de autenticación",
        "estimated_effort": {
            "optimistic": {"days": 5, "hours": 40},
            "expected": {"days": 10, "hours": 80},
            "pessimistic": {"days": 15, "hours": 120},
        },
        "estimated_cost": {
            "optimistic": {"amount": 1750.0, "currency": currency},
            "expected": {"amount": 3500.0, "currency": currency},
            "pessimistic": {"amount": 5250.0, "currency": currency},
        },
        "suggested_unit_price": {
            "amount": 350.0,
            "unit": "día",
            "currency": currency,
            "basis": "Mediana de precios unitarios",
        },
        "suggested_breakdown": [
            {"name": "Backend API", "days": 5, "unit_price": 350.0, "total": 1750.0},
            {"name": "Testing", "days": 3, "unit_price": 350.0, "total": 1050.0},
            {"name": "Docs", "days": 2, "unit_price": 350.0, "total": 700.0},
        ],
        "suggested_technologies": ["Python", "FastAPI"],
        "notes": "Basado en 5 referencias.",
    }


class TestParseValidJSON:
    def test_parse_valid_json(self) -> None:
        raw = json.dumps(_valid_response_dict())
        result = parse_llm_response(raw, "EUR")
        assert result.summary == "Estimación para desarrollo de módulo de autenticación"
        assert result.estimated_effort["expected"].days == 10
        assert result.estimated_cost["expected"].amount == 3500.0
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
        data["estimated_effort"]["optimistic"]["days"] = 15
        data["estimated_effort"]["optimistic"]["hours"] = 120
        data["estimated_effort"]["pessimistic"]["days"] = 5
        data["estimated_effort"]["pessimistic"]["hours"] = 40
        raw = json.dumps(data)
        result = parse_llm_response(raw, "EUR")
        assert result.estimated_effort["optimistic"].days < result.estimated_effort["expected"].days
        assert result.estimated_effort["expected"].days < result.estimated_effort["pessimistic"].days

    def test_hours_recalculation(self) -> None:
        data = _valid_response_dict()
        # Set wrong hours
        data["estimated_effort"]["expected"]["hours"] = 999
        raw = json.dumps(data)
        result = parse_llm_response(raw, "EUR")
        assert result.estimated_effort["expected"].hours == 10 * 8  # days * 8


class TestErrors:
    def test_invalid_json_raises(self) -> None:
        with pytest.raises(ParseError):
            parse_llm_response("This is not JSON at all", "EUR")

    def test_missing_fields_raises(self) -> None:
        data = {"summary": "Incomplete response"}
        with pytest.raises(ParseError):
            parse_llm_response(json.dumps(data), "EUR")

    def test_negative_days_raises(self) -> None:
        data = _valid_response_dict()
        data["estimated_effort"]["optimistic"]["days"] = -1
        data["estimated_effort"]["optimistic"]["hours"] = -8
        with pytest.raises(ParseError):
            parse_llm_response(json.dumps(data), "EUR")
