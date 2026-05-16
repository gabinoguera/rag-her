"""Pydantic schemas for speech endpoints (EPIC-003)."""

from pydantic import BaseModel, Field


class TranscribeResponse(BaseModel):
    """Response for POST /api/v1/speech/transcribe."""

    transcript: str = Field(
        description="Recognised text from the uploaded audio.",
        examples=["Hola, ¿cómo estás?"],
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Confidence score in [0.0, 1.0].  chirp_2 may return 0.0 when "
            "confidence information is unavailable."
        ),
        examples=[0.95],
    )


class SynthesizeRequest(BaseModel):
    """Request body for POST /api/v1/speech/synthesize.

    Validation of empty text and length limits is enforced in the endpoint
    handler (returning HTTP 400) rather than here (which would return 422).
    """

    text: str = Field(
        description="Plain text to synthesise (no SSML).  Max 5 000 characters.",
        examples=["Hola, soy HER."],
    )
