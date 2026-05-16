"""Unit tests for app.core.checkin_flow — no DB, no external services."""

import pytest

from app.core.checkin_flow import TOTAL_QUESTIONS, get_question, is_complete


def test_get_question_index_0() -> None:
    question = get_question(0)
    assert question == "¡Hola! Soy HER. ¿Cómo te llamas?"


def test_get_question_index_1_with_name() -> None:
    question = get_question(1, name="Ana")
    assert "Ana" in question


def test_get_question_index_1_without_name() -> None:
    question = get_question(1)
    assert "compañero" in question or "?" in question


def test_get_question_index_2() -> None:
    question = get_question(2)
    assert "bloqueo" in question or "ayuda" in question


def test_get_question_index_3() -> None:
    question = get_question(3)
    assert "mañana" in question


def test_get_question_out_of_range_negative_raises() -> None:
    with pytest.raises(IndexError):
        get_question(-1)


def test_get_question_out_of_range_raises() -> None:
    with pytest.raises(IndexError):
        get_question(TOTAL_QUESTIONS)


def test_get_question_out_of_range_high_raises() -> None:
    with pytest.raises(IndexError):
        get_question(99)


def test_is_complete_false_at_3() -> None:
    assert is_complete(3) is False


def test_is_complete_true_at_4() -> None:
    assert is_complete(4) is True


def test_is_complete_true_above_4() -> None:
    assert is_complete(5) is True


def test_total_questions_is_4() -> None:
    assert TOTAL_QUESTIONS == 4
