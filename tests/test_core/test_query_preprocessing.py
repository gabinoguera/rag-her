from app.core.query_preprocessing import preprocess_query


class TestAbbreviationExpansion:
    def test_expands_api(self) -> None:
        result = preprocess_query("Quiero una API REST")
        assert "API (Application Programming Interface)" in result.processed_text

    def test_expands_jwt(self) -> None:
        result = preprocess_query("Autenticacion JWT")
        assert "JWT (JSON Web Token)" in result.processed_text

    def test_no_double_expansion(self) -> None:
        result = preprocess_query("Uso JWT (JSON Web Token) en la API")
        # JWT should not be expanded again since expansion already present
        assert result.processed_text.count("JSON Web Token") == 1

    def test_preserves_original_text(self) -> None:
        result = preprocess_query("Quiero una API REST")
        assert result.original_text == "Quiero una API REST"
        assert result.original_text != result.processed_text


class TestTechnologyDetection:
    def test_detects_react_and_postgresql(self) -> None:
        result = preprocess_query("Proyecto con React y PostgreSQL")
        assert "React" in result.detected_technologies
        assert "PostgreSQL" in result.detected_technologies

    def test_detects_aliases_k8s(self) -> None:
        result = preprocess_query("Despliegue con k8s y docker")
        assert "Kubernetes" in result.detected_technologies
        assert "Docker" in result.detected_technologies

    def test_detects_nodejs_alias(self) -> None:
        result = preprocess_query("Backend con nodejs")
        assert "Node.js" in result.detected_technologies

    def test_no_false_positives(self) -> None:
        result = preprocess_query("Quiero un presupuesto barato")
        assert len(result.detected_technologies) == 0


class TestChunkTypeSuggestion:
    def test_fase_suggests_phase(self) -> None:
        result = preprocess_query("Cuanto dura la fase de diseno?")
        assert "phase" in result.suggested_chunk_types

    def test_coste_suggests_cost_related(self) -> None:
        result = preprocess_query("Cual es el coste del backend?")
        assert "scope_block" in result.suggested_chunk_types
        assert "line_item" in result.suggested_chunk_types

    def test_generic_query_suggests_all(self) -> None:
        result = preprocess_query("Dame informacion del sistema")
        assert len(result.suggested_chunk_types) == 5
