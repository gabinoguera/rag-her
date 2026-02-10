import hashlib

from app.api.schemas.quote_input import ClientInput, QuoteInput

SECTOR_KEYWORDS: dict[str, list[str]] = {
    "tech": ["software", "tecnolog", "digital", "IT", "tech", "informatic", "sistema"],
    "finance": ["banco", "bank", "financ", "seguro", "insurance", "inversion", "invest"],
    "health": ["salud", "health", "clinic", "hospital", "medic", "pharma", "farmac"],
    "retail": ["comercio", "tienda", "ecommerce", "retail", "shop", "store"],
    "education": ["educaci", "formaci", "universidad", "escuela", "school", "universit"],
    "consulting": ["consult", "asesor", "advisory"],
    "manufacturing": ["fabric", "manufactur", "industrial", "producci"],
    "media": ["media", "comunicaci", "editorial", "prensa", "press"],
}


def detect_sector(company_name: str) -> str | None:
    """Detect business sector from company name using keyword matching."""
    lower = company_name.lower()
    for sector, keywords in SECTOR_KEYWORDS.items():
        if any(kw.lower() in lower for kw in keywords):
            return sector
    return None


def generate_company_hash(company_name: str) -> str:
    """Generate a SHA-256 hash of the company name for deduplication."""
    return hashlib.sha256(company_name.lower().strip().encode("utf-8")).hexdigest()


def anonymize_quote(
    quote: QuoteInput,
) -> tuple[QuoteInput, str | None, str | None]:
    """Anonymize client data in a quote for chunk generation.

    Returns:
        - Anonymized copy of the quote (client name/email removed, company replaced by sector)
        - client_company_hash (or None if no company)
        - client_sector (or None if undetectable)
    """
    quote_copy = quote.model_copy(deep=True)

    client_company_hash: str | None = None
    client_sector: str | None = None

    if quote_copy.client:
        if quote_copy.client.company:
            client_company_hash = generate_company_hash(quote_copy.client.company)
            client_sector = detect_sector(quote_copy.client.company)

        # Replace client with anonymized version
        quote_copy.client = ClientInput(
            name=None,
            email=None,
            company=client_sector,
        )

    return quote_copy, client_company_hash, client_sector
