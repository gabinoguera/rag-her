import re
import unicodedata

CHUNK_TYPE_PREFIXES: dict[str, str] = {
    "project_overview": "project: ",
    "scope_block": "scope: ",
    "line_item": "task: ",
    "phase": "phase: ",
    "team_conditions": "team: ",
}

# Common mojibake patterns: UTF-8 bytes misinterpreted as Latin-1
_ENCODING_FIXES: dict[str, str] = {
    "Ã¡": "á",
    "Ã©": "é",
    "Ã­": "í",
    "Ã³": "ó",
    "Ãº": "ú",
    "Ã±": "ñ",
    "Ã\x81": "Á",
    "Ã\x89": "É",
    "Ã\x8d": "Í",
    "Ã\x93": "Ó",
    "Ã\x9a": "Ú",
    "Ã\x91": "Ñ",
    "Ã¼": "ü",
    "Ã\x9c": "Ü",
    "\u00e2\u0080\u0094": "—",  # em dash
    "\u00e2\u0080\u0093": "–",  # en dash
    "\u00e2\u0080\u009c": "\u201c",  # left double quote
    "\u00e2\u0080\u009d": "\u201d",  # right double quote
}


def normalize_unicode(text: str) -> str:
    """Normalize text to NFC Unicode form."""
    return unicodedata.normalize("NFC", text)


def fix_encoding_artifacts(text: str) -> str:
    """Fix common mojibake patterns from UTF-8/Latin-1 confusion."""
    for broken, fixed in _ENCODING_FIXES.items():
        text = text.replace(broken, fixed)

    # Try to detect and fix broader mojibake: if the text contains
    # sequences that look like latin-1 misinterpretation of utf-8,
    # attempt to re-encode and decode
    try:
        if "Ã" in text or "Â" in text:
            recovered = text.encode("latin-1").decode("utf-8")
            if recovered != text:
                text = recovered
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass

    return text


def clean_whitespace(text: str) -> str:
    """Collapse multiple whitespace, normalize line endings."""
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse multiple blank lines to max one
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse multiple spaces/tabs to single space (within lines)
    text = re.sub(r"[^\S\n]+", " ", text)

    # Strip leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)

    # Strip overall
    return text.strip()


def add_type_prefix(text: str, chunk_type: str) -> str:
    """Add semantic type prefix to chunk text."""
    prefix = CHUNK_TYPE_PREFIXES.get(chunk_type, "")
    return f"{prefix}{text}" if prefix else text


def preprocess_chunk_text(text: str, chunk_type: str) -> str:
    """Full preprocessing pipeline for chunk text before embedding."""
    text = normalize_unicode(text)
    text = fix_encoding_artifacts(text)
    text = clean_whitespace(text)
    text = add_type_prefix(text, chunk_type)
    return text


def parse_duration_weeks(duration_str: str) -> int | None:
    """Extract weeks from duration strings like '4 semanas' or '2 weeks'."""
    match = re.search(r"(\d+)\s*(?:semanas?|weeks?)", duration_str, re.IGNORECASE)
    return int(match.group(1)) if match else None
