from pydantic import BaseModel


class ValidationErrorDetail(BaseModel):
    field: str
    message: str


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: list[ValidationErrorDetail] | None = None
