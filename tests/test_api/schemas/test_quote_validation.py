import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.api.schemas.quote_input import IngestRequest

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / name).read_text())


def _get_quote(fixture: dict[str, Any]) -> dict[str, Any]:
    """Extract the quote dict, whether wrapped in IngestRequest or standalone."""
    if "quote" in fixture:
        return fixture["quote"]
    return fixture


class TestValidQuotes:
    def test_valid_full_quote(self) -> None:
        data = _load_fixture("quote_platform_ia.json")
        request = IngestRequest.model_validate(data)

        assert request.quote.project is not None
        assert request.quote.project.title == "Plataforma de Gestion con IA"
        assert len(request.quote.scope_blocks) == 3
        assert len(request.quote.items) == 10
        assert request.quote.roadmap_phases is not None
        assert len(request.quote.roadmap_phases) == 5
        assert request.quote.team_members is not None
        assert len(request.quote.team_members) == 5
        assert request.quote.currency == "EUR"
        assert request.source == "manual_upload"
        assert request.ingested_by == "user_test_001"

    def test_valid_minimal_quote(self) -> None:
        data = _load_fixture("quote_minimal.json")
        request = IngestRequest.model_validate(data)

        assert request.quote.project is not None
        assert request.quote.project.title == "Proyecto Minimo de Test"
        assert len(request.quote.scope_blocks) == 1
        assert len(request.quote.items) == 1
        assert request.quote.client is None
        assert request.quote.roadmap_phases is None
        assert request.quote.team_members is None
        assert request.quote.conditions is None
        assert request.source is None

    def test_valid_quote_all_item_types(self) -> None:
        data = _load_fixture("quote_minimal.json")
        quote = _get_quote(data)
        quote["items"] = [
            {"type": "service", "name": "Servicio", "quantity": 1,
             "unit": "dia", "unit_price": 100},
            {"type": "product", "name": "Producto", "quantity": 2,
             "unit": "unidad", "unit_price": 50},
            {"type": "license", "name": "Licencia", "quantity": 1,
             "unit": "mes", "unit_price": 200},
        ]
        request = IngestRequest.model_validate(data)
        assert len(request.quote.items) == 3


class TestInvalidQuotes:
    def test_missing_items_fails(self) -> None:
        data = _load_fixture("quote_invalid_missing_items.json")
        with pytest.raises(ValidationError) as exc_info:
            IngestRequest.model_validate(data)
        errors = exc_info.value.errors()
        assert any("items" in str(e["loc"]) for e in errors)

    def test_missing_scope_blocks_fails(self) -> None:
        data = _load_fixture("quote_minimal.json")
        quote = _get_quote(data)
        quote["scope_blocks"] = []
        with pytest.raises(ValidationError) as exc_info:
            IngestRequest.model_validate(data)
        errors = exc_info.value.errors()
        assert any("scope_blocks" in str(e["loc"]) for e in errors)

    def test_negative_unit_price_fails(self) -> None:
        data = _load_fixture("quote_invalid_negative_price.json")
        with pytest.raises(ValidationError) as exc_info:
            IngestRequest.model_validate(data)
        errors = exc_info.value.errors()
        assert any("unit_price" in str(e["loc"]) for e in errors)

    def test_discount_percent_over_100_fails(self) -> None:
        data = _load_fixture("quote_minimal.json")
        quote = _get_quote(data)
        quote["items"][0]["discount_percent"] = 150
        with pytest.raises(ValidationError):
            IngestRequest.model_validate(data)

    def test_quantity_zero_fails(self) -> None:
        data = _load_fixture("quote_minimal.json")
        quote = _get_quote(data)
        quote["items"][0]["quantity"] = 0
        with pytest.raises(ValidationError):
            IngestRequest.model_validate(data)

    def test_invalid_currency_fails(self) -> None:
        data = _load_fixture("quote_minimal.json")
        quote = _get_quote(data)
        quote["currency"] = "EURO"
        with pytest.raises(ValidationError):
            IngestRequest.model_validate(data)

    def test_invalid_date_order_fails(self) -> None:
        data = _load_fixture("quote_minimal.json")
        quote = _get_quote(data)
        quote["dates"] = {"issue_date": "2026-03-01", "valid_until": "2026-02-01"}
        with pytest.raises(ValidationError) as exc_info:
            IngestRequest.model_validate(data)
        assert "issue_date" in str(exc_info.value)

    def test_invalid_phase_reference_fails(self) -> None:
        data = _load_fixture("quote_minimal.json")
        quote = _get_quote(data)
        quote["roadmap_phases"] = [{"name": "Fase 1"}]
        quote["items"][0]["phase"] = "Fase Inexistente"
        with pytest.raises(ValidationError) as exc_info:
            IngestRequest.model_validate(data)
        assert "Fase Inexistente" in str(exc_info.value)

    def test_invalid_email_format_fails(self) -> None:
        data = _load_fixture("quote_minimal.json")
        quote = _get_quote(data)
        quote["client"] = {"name": "Test", "email": "not-an-email"}
        with pytest.raises(ValidationError):
            IngestRequest.model_validate(data)

    def test_project_title_too_short_fails(self) -> None:
        data = _load_fixture("quote_minimal.json")
        quote = _get_quote(data)
        quote["project"]["title"] = "AB"
        with pytest.raises(ValidationError):
            IngestRequest.model_validate(data)
