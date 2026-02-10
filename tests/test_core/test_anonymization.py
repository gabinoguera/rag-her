from app.api.schemas.quote_input import ClientInput, ItemInput, QuoteInput, ScopeBlockInput
from app.core.anonymization import anonymize_quote, detect_sector, generate_company_hash


def _make_minimal_quote(**kwargs) -> QuoteInput:  # type: ignore[no-untyped-def]
    defaults = {
        "scope_blocks": [ScopeBlockInput(title="Test", short_description="Test")],
        "items": [ItemInput(type="service", name="Test", quantity=1, unit="dia", unit_price=100)],
    }
    defaults.update(kwargs)
    return QuoteInput(**defaults)


class TestDetectSector:
    def test_tech_sector(self) -> None:
        assert detect_sector("Empresa Tecnologica SL") == "tech"

    def test_finance_sector(self) -> None:
        assert detect_sector("Banco Nacional de Finanzas") == "finance"

    def test_health_sector(self) -> None:
        assert detect_sector("Clinica Salud Integral") == "health"

    def test_retail_sector(self) -> None:
        assert detect_sector("Tienda Ecommerce Global") == "retail"

    def test_education_sector(self) -> None:
        assert detect_sector("Universidad de Formacion") == "education"

    def test_unknown_sector_returns_none(self) -> None:
        assert detect_sector("Acme Corporation") is None

    def test_case_insensitive(self) -> None:
        assert detect_sector("SOFTWARE SOLUTIONS") == "tech"


class TestGenerateCompanyHash:
    def test_deterministic_hash(self) -> None:
        hash1 = generate_company_hash("Empresa SL")
        hash2 = generate_company_hash("Empresa SL")
        assert hash1 == hash2

    def test_case_insensitive_hash(self) -> None:
        hash1 = generate_company_hash("Empresa SL")
        hash2 = generate_company_hash("empresa sl")
        assert hash1 == hash2

    def test_strip_whitespace_hash(self) -> None:
        hash1 = generate_company_hash("Empresa SL")
        hash2 = generate_company_hash("  Empresa SL  ")
        assert hash1 == hash2

    def test_hash_is_hex_string(self) -> None:
        h = generate_company_hash("Test")
        assert len(h) == 64  # SHA-256 hex length
        assert all(c in "0123456789abcdef" for c in h)


class TestAnonymizeQuote:
    def test_removes_client_name(self) -> None:
        quote = _make_minimal_quote(
            client=ClientInput(name="Juan Garcia", email="juan@test.com", company="Tech SL")
        )
        anon, _, _ = anonymize_quote(quote)
        assert anon.client is not None
        assert anon.client.name is None

    def test_removes_client_email(self) -> None:
        quote = _make_minimal_quote(
            client=ClientInput(name="Juan", email="juan@test.com", company="Tech SL")
        )
        anon, _, _ = anonymize_quote(quote)
        assert anon.client is not None
        assert anon.client.email is None

    def test_replaces_company_with_sector(self) -> None:
        quote = _make_minimal_quote(
            client=ClientInput(company="Empresa Tecnologica SL")
        )
        anon, _, sector = anonymize_quote(quote)
        assert anon.client is not None
        assert anon.client.company == "tech"
        assert sector == "tech"

    def test_returns_company_hash(self) -> None:
        quote = _make_minimal_quote(
            client=ClientInput(company="Empresa SL")
        )
        _, company_hash, _ = anonymize_quote(quote)
        assert company_hash is not None
        assert len(company_hash) == 64

    def test_no_client_returns_none_hash(self) -> None:
        quote = _make_minimal_quote()
        _, company_hash, sector = anonymize_quote(quote)
        assert company_hash is None
        assert sector is None

    def test_does_not_mutate_original(self) -> None:
        quote = _make_minimal_quote(
            client=ClientInput(name="Juan", email="juan@test.com", company="Tech SL")
        )
        anonymize_quote(quote)
        assert quote.client is not None
        assert quote.client.name == "Juan"
        assert quote.client.email == "juan@test.com"
