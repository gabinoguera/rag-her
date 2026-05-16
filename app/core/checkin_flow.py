"""Pure check-in flow logic — no DB, no external services.

Defines the 4-turn conversational structure:
  0 → greeting / name capture
  1 → work done today (interpolated with employee name)
  2 → blockers / help needed
  3 → plans for tomorrow
"""

QUESTIONS: list[str] = [
    "¡Hola! Soy HER. ¿Cómo te llamas?",
    "¿En qué trabajaste hoy, {name}?",
    "¿Tuviste algún bloqueo o necesitas ayuda?",
    "¿Qué planeas hacer mañana?",
]

TOTAL_QUESTIONS: int = 4


def get_question(index: int, name: str = "") -> str:
    """Return the question at *index*, interpolating ``{name}`` where applicable.

    Uses ``"compañero"`` as a fallback when *name* is empty.

    Raises:
        IndexError: if *index* is out of ``[0, TOTAL_QUESTIONS)``.
    """
    if index < 0 or index >= TOTAL_QUESTIONS:
        raise IndexError(
            f"Question index {index} out of range [0, {TOTAL_QUESTIONS})"
        )
    return QUESTIONS[index].format(name=name or "compañero")


def is_complete(index: int) -> bool:
    """Return ``True`` when *index* has reached or passed ``TOTAL_QUESTIONS``.

    Call with ``current_index + 1`` after persisting the latest answer.
    """
    return index >= TOTAL_QUESTIONS
