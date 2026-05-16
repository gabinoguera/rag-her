"""TDD tests for app/core/generation.py — RAG-03 (Wave 2 Track B).

These tests are written BEFORE the new GenerationService implementation exists.
They are expected to FAIL until RAG-03 rewrites generation.py with google-genai.

Target implementation contract:
  class GenerationService:
      def __init__(self, api_key: str, model: str, max_output_tokens: int = 8192) -> None
      async def generate(self, prompt: str, system_instruction: str | None = None) -> str

Retry strategy (from spec):
  ResourceExhausted → 4 retries, exponential backoff 2s→4s→8s→16s
  DeadlineExceeded  → 1 retry
  Unauthenticated   → fail immediately (no retries)
  other GoogleAPICallError → fail immediately
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from google.api_core import exceptions as google_exceptions

from app.core.generation import GenerationError, GenerationService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_generate_response(text: str | None) -> MagicMock:
    """Construct a mock GenerateContentResponse with the given text."""
    response = MagicMock()
    response.text = text
    return response


def _make_service(mock_response: MagicMock | None = None) -> GenerationService:
    """Build a GenerationService with a mocked genai client.

    When *mock_response* is provided the async generate_content call is
    pre-wired to return it.  Callers that need side_effect behaviour should
    mutate service._client.aio.models.generate_content directly after calling
    this helper.
    """
    service = GenerationService(
        api_key="test-key",
        model="gemini-2.5-flash",
        max_output_tokens=8192,
    )
    service._client = MagicMock()
    service._client.aio = MagicMock()
    if mock_response is not None:
        service._client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )
    return service


# ---------------------------------------------------------------------------
# TestGenerationServiceInit
# ---------------------------------------------------------------------------


class TestGenerationServiceInit:
    """Verify that GenerationService initialises correctly."""

    def test_client_initialized_with_api_key(self) -> None:
        """GenerationService stores the api_key and creates a genai.Client."""
        with patch("app.core.generation.genai.Client") as mock_cls:
            GenerationService(
                api_key="my-secret-key",
                model="gemini-2.5-flash",
                max_output_tokens=8192,
            )
            mock_cls.assert_called_once_with(api_key="my-secret-key")

    def test_model_stored(self) -> None:
        """_model attribute reflects the model argument."""
        svc = GenerationService(
            api_key="k",
            model="gemini-2.5-flash",
            max_output_tokens=512,
        )
        assert svc._model == "gemini-2.5-flash"

    def test_max_output_tokens_stored(self) -> None:
        """_max_output_tokens attribute reflects the constructor argument."""
        svc = GenerationService(
            api_key="k",
            model="gemini-2.5-flash",
            max_output_tokens=1024,
        )
        assert svc._max_output_tokens == 1024

    def test_default_max_output_tokens_is_8192(self) -> None:
        """Default max_output_tokens is 8192 as per spec."""
        svc = GenerationService(api_key="k", model="gemini-2.5-flash")
        assert svc._max_output_tokens == 8192


# ---------------------------------------------------------------------------
# TestGenerate
# ---------------------------------------------------------------------------


class TestGenerate:
    """Happy-path and basic error tests for GenerationService.generate()."""

    async def test_returns_string(self) -> None:
        """generate(prompt) returns the text string from the model response."""
        service = _make_service(_make_mock_generate_response("Respuesta del modelo Gemini."))
        result = await service.generate("¿Cuánto tiempo toma esta tarea?")
        assert result == "Respuesta del modelo Gemini."

    async def test_returns_non_empty_string(self) -> None:
        """generate() result is a non-empty string."""
        service = _make_service(_make_mock_generate_response("Texto de respuesta."))
        result = await service.generate("prompt de prueba")
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_with_system_instruction(self) -> None:
        """system_instruction is forwarded in GenerateContentConfig."""
        service = _make_service(_make_mock_generate_response("ok"))
        await service.generate(
            "prompt de prueba",
            system_instruction="Responde en español.",
        )
        call_kwargs = service._client.aio.models.generate_content.call_args
        # config may be passed as positional or keyword argument
        config = call_kwargs.kwargs.get("config") or (
            call_kwargs.args[2] if len(call_kwargs.args) > 2 else None
        )
        assert config is not None, "config argument was not passed to generate_content"
        assert config.system_instruction == "Responde en español."

    async def test_none_system_instruction_is_valid(self) -> None:
        """Passing system_instruction=None does not raise and returns a string."""
        service = _make_service(_make_mock_generate_response("resultado"))
        result = await service.generate("consulta", system_instruction=None)
        assert isinstance(result, str)

    async def test_empty_response_text_raises_generation_error(self) -> None:
        """response.text == None raises GenerationError with a descriptive message."""
        service = _make_service(_make_mock_generate_response(None))
        with pytest.raises(GenerationError, match="[Ee]mpty|[Vv]acía|[Ee]rror"):
            await service.generate("consulta")

    async def test_empty_string_response_raises_generation_error(self) -> None:
        """response.text == '' (falsy) also raises GenerationError."""
        service = _make_service(_make_mock_generate_response(""))
        with pytest.raises(GenerationError):
            await service.generate("consulta")

    async def test_uses_gemini_25_flash_model(self) -> None:
        """The model name passed to generate_content matches the constructor argument."""
        service = _make_service(_make_mock_generate_response("respuesta"))
        await service.generate("test")
        call_kwargs = service._client.aio.models.generate_content.call_args
        # model may be positional or keyword
        model_arg = call_kwargs.kwargs.get("model") or (
            call_kwargs.args[0] if call_kwargs.args else None
        )
        assert model_arg == "gemini-2.5-flash"

    async def test_prompt_passed_as_contents(self) -> None:
        """The prompt string is forwarded as the *contents* argument."""
        service = _make_service(_make_mock_generate_response("respuesta"))
        await service.generate("mi consulta especial")
        call_kwargs = service._client.aio.models.generate_content.call_args
        contents_arg = call_kwargs.kwargs.get("contents") or (
            call_kwargs.args[1] if len(call_kwargs.args) > 1 else None
        )
        assert contents_arg == "mi consulta especial"

    async def test_uses_async_path_not_sync(self) -> None:
        """generate_content is called via client.aio.models (async path)."""
        service = _make_service(_make_mock_generate_response("ok"))
        await service.generate("prompt")
        # The async mock on the aio path must have been called
        service._client.aio.models.generate_content.assert_called_once()


# ---------------------------------------------------------------------------
# TestRetryStrategy
# ---------------------------------------------------------------------------


class TestRetryStrategy:
    """Verify retry behaviour for transient and permanent errors."""

    async def test_resource_exhausted_retries_and_raises(self) -> None:
        """ResourceExhausted is retried up to 4 times then raises GenerationError."""
        service = _make_service()
        service._client.aio.models.generate_content = AsyncMock(
            side_effect=google_exceptions.ResourceExhausted("quota exceeded")
        )

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(GenerationError):
                await service.generate("consulta que agota quota")

        # spec: 4 retries → 4 sleep calls (delays 2s, 4s, 8s, 16s)
        assert mock_sleep.call_count == 4

    async def test_resource_exhausted_uses_exponential_backoff(self) -> None:
        """ResourceExhausted retries use delays 2s → 4s → 8s → 16s."""
        service = _make_service()
        service._client.aio.models.generate_content = AsyncMock(
            side_effect=google_exceptions.ResourceExhausted("quota exceeded")
        )

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(GenerationError):
                await service.generate("prompt")

        sleep_delays = [c.args[0] for c in mock_sleep.call_args_list]
        assert sleep_delays == [2, 4, 8, 16]

    async def test_resource_exhausted_total_attempts_is_five(self) -> None:
        """ResourceExhausted: 1 initial attempt + 4 retries = 5 total calls."""
        service = _make_service()
        service._client.aio.models.generate_content = AsyncMock(
            side_effect=google_exceptions.ResourceExhausted("quota exceeded")
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(GenerationError):
                await service.generate("prompt")

        assert service._client.aio.models.generate_content.call_count == 5

    async def test_resource_exhausted_succeeds_on_retry(self) -> None:
        """If ResourceExhausted resolves on retry, generate() returns the text."""
        service = _make_service()
        success_response = _make_mock_generate_response("Éxito tras reintento")
        service._client.aio.models.generate_content = AsyncMock(
            side_effect=[
                google_exceptions.ResourceExhausted("quota"),
                success_response,
            ]
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await service.generate("prompt")

        assert result == "Éxito tras reintento"

    async def test_deadline_exceeded_retries_and_raises(self) -> None:
        """DeadlineExceeded is retried once then raises GenerationError."""
        service = _make_service()
        service._client.aio.models.generate_content = AsyncMock(
            side_effect=google_exceptions.DeadlineExceeded("timeout")
        )

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(GenerationError):
                await service.generate("consulta con timeout")

        # spec: 1 retry → at least 1 sleep call
        assert mock_sleep.call_count >= 1

    async def test_deadline_exceeded_total_attempts_is_two(self) -> None:
        """DeadlineExceeded: 1 initial attempt + 1 retry = 2 total calls."""
        service = _make_service()
        service._client.aio.models.generate_content = AsyncMock(
            side_effect=google_exceptions.DeadlineExceeded("timeout")
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(GenerationError):
                await service.generate("prompt")

        assert service._client.aio.models.generate_content.call_count == 2

    async def test_deadline_exceeded_succeeds_on_retry(self) -> None:
        """If DeadlineExceeded resolves on retry, generate() returns the text."""
        service = _make_service()
        success_response = _make_mock_generate_response("OK tras timeout")
        service._client.aio.models.generate_content = AsyncMock(
            side_effect=[
                google_exceptions.DeadlineExceeded("timeout"),
                success_response,
            ]
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await service.generate("prompt")

        assert result == "OK tras timeout"

    async def test_unauthenticated_raises_immediately(self) -> None:
        """Unauthenticated raises GenerationError without any retries."""
        service = _make_service()
        service._client.aio.models.generate_content = AsyncMock(
            side_effect=google_exceptions.Unauthenticated("invalid key")
        )

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(GenerationError):
                await service.generate("consulta")

        # No retries → no sleep calls
        mock_sleep.assert_not_called()

    async def test_unauthenticated_single_attempt_only(self) -> None:
        """Unauthenticated: exactly 1 call to generate_content (no retries)."""
        service = _make_service()
        service._client.aio.models.generate_content = AsyncMock(
            side_effect=google_exceptions.Unauthenticated("invalid key")
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(GenerationError):
                await service.generate("prompt")

        assert service._client.aio.models.generate_content.call_count == 1

    async def test_other_google_api_error_raises_immediately(self) -> None:
        """A generic GoogleAPICallError (not ResourceExhausted/DeadlineExceeded)
        raises GenerationError immediately without retries."""
        service = _make_service()
        service._client.aio.models.generate_content = AsyncMock(
            side_effect=google_exceptions.GoogleAPICallError("generic error")
        )

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(GenerationError):
                await service.generate("prompt")

        mock_sleep.assert_not_called()

    async def test_generation_error_wraps_google_exception(self) -> None:
        """GenerationError raised on Unauthenticated wraps or describes the cause."""
        service = _make_service()
        service._client.aio.models.generate_content = AsyncMock(
            side_effect=google_exceptions.Unauthenticated("bad api key")
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(GenerationError) as exc_info:
                await service.generate("prompt")

        # The GenerationError message should be non-empty
        assert str(exc_info.value)


# ---------------------------------------------------------------------------
# TestLegacyMethodsAbsent
# ---------------------------------------------------------------------------


class TestLegacyMethodsAbsent:
    """Verify that the legacy OpenAI methods no longer exist on GenerationService.

    These assertions document that the migration removed the old interface.
    They fail in TDD phase (current code has the old methods) and pass once
    RAG-03 is implemented.
    """

    def test_generate_estimation_not_present(self) -> None:
        """generate_estimation() must NOT exist on the new GenerationService."""
        svc = GenerationService(api_key="k", model="gemini-2.5-flash")
        assert not hasattr(svc, "generate_estimation"), (
            "generate_estimation() was not removed — legacy method still present"
        )

    def test_validate_estimation_not_present(self) -> None:
        """validate_estimation() must NOT exist on the new GenerationService."""
        svc = GenerationService(api_key="k", model="gemini-2.5-flash")
        assert not hasattr(svc, "validate_estimation"), (
            "validate_estimation() was not removed — legacy method still present"
        )

    def test_build_fallback_estimation_not_present(self) -> None:
        """build_fallback_estimation() must NOT exist on the new GenerationService."""
        svc = GenerationService(api_key="k", model="gemini-2.5-flash")
        assert not hasattr(svc, "build_fallback_estimation"), (
            "build_fallback_estimation() was not removed — legacy method still present"
        )

    def test_generate_method_is_present(self) -> None:
        """The new generate() method must exist and be callable."""
        svc = GenerationService(api_key="k", model="gemini-2.5-flash")
        assert callable(getattr(svc, "generate", None)), (
            "generate() method not found on GenerationService"
        )
