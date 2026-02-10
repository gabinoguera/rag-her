from app.utils.text_processing import (
    add_type_prefix,
    clean_whitespace,
    fix_encoding_artifacts,
    normalize_unicode,
    parse_duration_weeks,
    preprocess_chunk_text,
)


class TestNormalizeUnicode:
    def test_nfc_normalization(self) -> None:
        # Decomposed 'ñ' (n + combining tilde) should become composed 'ñ'
        decomposed = "n\u0303"  # n + combining tilde
        result = normalize_unicode(decomposed)
        assert result == "\u00f1"  # ñ composed form

    def test_already_nfc_unchanged(self) -> None:
        text = "Diseño de interfaz"
        assert normalize_unicode(text) == text


class TestFixEncodingArtifacts:
    def test_common_mojibake_fix(self) -> None:
        # Ã± is a common mojibake for ñ
        assert "ñ" in fix_encoding_artifacts("Ã±")

    def test_no_artifacts_unchanged(self) -> None:
        text = "Normal text without artifacts"
        assert fix_encoding_artifacts(text) == text


class TestCleanWhitespace:
    def test_collapse_multiple_spaces(self) -> None:
        assert clean_whitespace("hello   world") == "hello world"

    def test_collapse_tabs(self) -> None:
        assert clean_whitespace("hello\t\tworld") == "hello world"

    def test_collapse_multiple_blank_lines(self) -> None:
        result = clean_whitespace("line1\n\n\n\nline2")
        assert result == "line1\n\nline2"

    def test_strip_line_whitespace(self) -> None:
        result = clean_whitespace("  hello  \n  world  ")
        assert result == "hello\nworld"

    def test_normalize_line_endings(self) -> None:
        result = clean_whitespace("hello\r\nworld\rtest")
        assert "\r" not in result
        assert "hello\nworld\ntest" == result


class TestAddTypePrefix:
    def test_project_overview_prefix(self) -> None:
        result = add_type_prefix("Proyecto: Test", "project_overview")
        assert result == "project: Proyecto: Test"

    def test_scope_block_prefix(self) -> None:
        result = add_type_prefix("Bloque: Backend", "scope_block")
        assert result == "scope: Bloque: Backend"

    def test_line_item_prefix(self) -> None:
        result = add_type_prefix("Tarea: API", "line_item")
        assert result == "task: Tarea: API"

    def test_phase_prefix(self) -> None:
        result = add_type_prefix("Fase 1", "phase")
        assert result == "phase: Fase 1"

    def test_team_conditions_prefix(self) -> None:
        result = add_type_prefix("Equipo", "team_conditions")
        assert result == "team: Equipo"

    def test_unknown_type_no_prefix(self) -> None:
        result = add_type_prefix("text", "unknown_type")
        assert result == "text"


class TestPreprocessChunkText:
    def test_full_pipeline(self) -> None:
        text = "  Proyecto:   Test   Project  \n\n\n\n  Con detalles  "
        result = preprocess_chunk_text(text, "project_overview")
        assert result.startswith("project: ")
        assert "   " not in result
        assert "\n\n\n" not in result

    def test_preserves_technical_terms(self) -> None:
        text = "API REST con JWT, OAuth, PostgreSQL, FastAPI y Redis"
        result = preprocess_chunk_text(text, "line_item")
        assert "JWT" in result
        assert "OAuth" in result
        assert "PostgreSQL" in result
        assert "FastAPI" in result
        assert "Redis" in result


class TestParseDurationWeeks:
    def test_semanas_singular(self) -> None:
        assert parse_duration_weeks("1 semana") == 1

    def test_semanas_plural(self) -> None:
        assert parse_duration_weeks("4 semanas") == 4

    def test_weeks_english(self) -> None:
        assert parse_duration_weeks("2 weeks") == 2

    def test_week_singular(self) -> None:
        assert parse_duration_weeks("1 week") == 1

    def test_with_extra_text(self) -> None:
        assert parse_duration_weeks("Duracion: 3 semanas aprox") == 3

    def test_no_match_returns_none(self) -> None:
        assert parse_duration_weeks("2 meses") is None

    def test_empty_string_returns_none(self) -> None:
        assert parse_duration_weeks("") is None
