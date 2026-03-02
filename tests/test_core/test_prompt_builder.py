from dataclasses import dataclass, field

from app.core.prompt_builder import (
    MAX_PROMPT_TOKENS,
    RESPONSE_JSON_SCHEMA,
    SYSTEM_PROMPT,
    build_estimation_prompt,
)


@dataclass
class FakeContext:
    project_type: str | None = "SaaS Platform"
    technologies_preferred: list[str] | None = None
    team_size: int | None = 3
    complexity: str | None = "medium"


@dataclass
class FakeChunk:
    chunk_type: str = "scope_block"
    similarity_score: float = 0.85
    final_score: float = 0.80
    content_text: str = "Desarrollo del módulo de autenticación con OAuth2"
    metadata: dict | None = None
    project_title: str | None = "Plataforma IA"
    technologies: list[str] | None = None
    total_cost: float | None = 5000.0
    currency: str | None = "EUR"

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {"related_items": ["Login", "Registro", "2FA"]}
        if self.technologies is None:
            self.technologies = ["React", "Node.js"]


class TestSystemPrompt:
    def test_system_prompt_contains_rules(self) -> None:
        for i in range(1, 10):
            assert f"{i}." in SYSTEM_PROMPT


class TestUserPrompt:
    def test_user_prompt_contains_query(self) -> None:
        chunks = [FakeChunk()]
        _, user, _ = build_estimation_prompt(
            "Desarrollo de módulo de pagos", FakeContext(), chunks
        )
        assert "Desarrollo de módulo de pagos" in user

    def test_user_prompt_contains_context(self) -> None:
        ctx = FakeContext(project_type="E-commerce", team_size=5)
        chunks = [FakeChunk()]
        _, user, _ = build_estimation_prompt("Estimación backend", ctx, chunks)
        assert "E-commerce" in user
        assert "5" in user

    def test_user_prompt_contains_chunks(self) -> None:
        chunks = [FakeChunk(similarity_score=0.92)]
        _, user, _ = build_estimation_prompt("Query de prueba larga", FakeContext(), chunks)
        assert "0.92" in user
        assert "Plataforma IA" in user

    def test_user_prompt_contains_schema(self) -> None:
        chunks = [FakeChunk()]
        _, user, _ = build_estimation_prompt("Query de prueba larga", None, chunks)
        assert "estimated_effort" in user
        assert "suggested_breakdown" in user


class TestChunkFormatting:
    def test_chunk_formatting_scope_block(self) -> None:
        chunk = FakeChunk(
            chunk_type="scope_block",
            metadata={"related_items": ["Login", "Registro"]},
            total_cost=5000.0,
        )
        _, user, _ = build_estimation_prompt("Estimación módulo auth", None, [chunk])
        assert "Bloque funcional" in user
        assert "Login" in user
        assert "5000" in user

    def test_chunk_formatting_line_item(self) -> None:
        chunk = FakeChunk(
            chunk_type="line_item",
            metadata={
                "item_name": "Diseño de base de datos",
                "quantity": 3,
                "unit": "días",
                "unit_price": 350,
                "total_price": 1050,
            },
            content_text="Diseño y modelado de la base de datos PostgreSQL",
        )
        _, user, _ = build_estimation_prompt("Estimación diseño DB", None, [chunk])
        assert "Tarea individual" in user
        assert "Diseño de base de datos" in user
        assert "350" in user


class TestPromptSize:
    def test_prompt_size_limit(self) -> None:
        chunks = [
            FakeChunk(content_text="x" * 2000, final_score=0.9 - i * 0.01)
            for i in range(50)
        ]
        sys_prompt, user_prompt, chunks_used = build_estimation_prompt(
            "Query de prueba para verificar límites del prompt", None, chunks
        )
        total_tokens = (len(sys_prompt) + len(user_prompt)) // 4
        assert total_tokens <= MAX_PROMPT_TOKENS + 500  # some tolerance

    def test_chunks_reduced_on_overflow(self) -> None:
        # scope_block truncates to 500 chars, so each formatted chunk is ~170 tokens
        # Budget ~9500 tokens -> need >56 chunks to overflow
        chunks = [
            FakeChunk(content_text="x" * 3000, final_score=0.9 - i * 0.001)
            for i in range(200)
        ]
        _, _, chunks_used = build_estimation_prompt(
            "Query para verificar reducción de chunks", None, chunks
        )
        assert chunks_used < 200
        assert chunks_used >= 1
