# QA Report — EPIC-004: Flujo de Check-in del Empleado

**Fecha:** 2026-05-16
**QA Agent:** qa-acceptance
**Worktree:** `.trees/feature-issue-EPIC-004`
**Python:** 3.11.14
**pytest:** 9.0.3
**Veredicto final:** PASSED — Ready to merge

---

## Validation Report

### Passed

- TC-1 (test_checkin_flow.py): 12/12 tests passed
- TC-2 (test_checkin_service.py): 12/12 tests passed
- TC-3 (test_checkin.py): 9/9 tests passed
- TC-4 (test_full_flow_integration): PASSED — 4 turns start→answer×4→status=completed
- TC-5 (full suite): 147 passed, 3 skipped, 0 failures
- TC-6 (migration 010): head = `010 — Make her.check_ins.employee_id nullable`

### Warnings (non-blocking)

- `SAWarning: transaction already deassociated from connection` in `test_her_models.py::test_employee_name_not_null` and `test_checkin_session_id_unique` — pre-existing from EPIC-002, not introduced by this epic.

### Failed

None.

---

## TC Classification

| TC | Descripcion | Tipo | Motivo |
|----|-------------|------|--------|
| TC-1 | Unit tests checkin_flow.py | Paralelo | Sin DB, sin estado compartido |
| TC-2 | Service tests CheckInService | Paralelo | Mock EmbeddingService, DB limpiada por fixture |
| TC-3 | API endpoint tests | Paralelo | ASGI transport, DB limpiada por `client_for_checkin` fixture |
| TC-4 | Flujo completo 4 turnos | Secuencial | Subtset de TC-3, mismo fixture |
| TC-5 | Suite completa sin regresiones | Secuencial | Ejecutar tras TC-1/TC-2/TC-3 |
| TC-6 | Migracion 010 aplicada | Paralelo | Consulta de estado, sin escritura |

---

## Acceptance Criteria Coverage

| AC | Criterio | Test | Resultado |
|----|----------|------|-----------|
| AC-1 | `POST /start` devuelve `session_id` (UUID string) y `question_text` = pregunta 0 | `test_start_returns_session_id_and_question` | PASSED |
| AC-2 | 4 respuestas consecutivas completan la sesion (`is_complete=True`) | `test_full_flow_integration` | PASSED |
| AC-3 | La pregunta 1 incluye el nombre dado en la respuesta 0 | `test_answer_returns_next_question` | PASSED |
| AC-4 | Al completar, los 4 chunks tienen `embedding` != None en DB | `test_complete_session_generates_embeddings` | PASSED |
| AC-5 | `GET /status` con sesion completada devuelve `status="completed"` y `questions_answered=4` | `test_status_returns_questions_answered` | PASSED |
| AC-6 | `POST /{id}/answer` con session_id inexistente → HTTP 404 | `test_answer_unknown_session_returns_404` | PASSED |
| AC-7 | `POST /{id}/answer` en sesion ya completada → HTTP 409 | `test_answer_completed_session_returns_409` | PASSED |
| AC-8 | Suite completa `pytest tests/` pasa sin regresiones en search/health | 147 passed, 3 skipped | PASSED |

---

## Test Execution Evidence

### TC-1: Unit tests checkin_flow.py

```
tests/test_core/test_checkin_flow.py::test_get_question_index_0 PASSED
tests/test_core/test_checkin_flow.py::test_get_question_index_1_with_name PASSED
tests/test_core/test_checkin_flow.py::test_get_question_index_1_without_name PASSED
tests/test_core/test_checkin_flow.py::test_get_question_index_2 PASSED
tests/test_core/test_checkin_flow.py::test_get_question_index_3 PASSED
tests/test_core/test_checkin_flow.py::test_get_question_out_of_range_negative_raises PASSED
tests/test_core/test_checkin_flow.py::test_get_question_out_of_range_raises PASSED
tests/test_core/test_checkin_flow.py::test_get_question_out_of_range_high_raises PASSED
tests/test_core/test_checkin_flow.py::test_is_complete_false_at_3 PASSED
tests/test_core/test_checkin_flow.py::test_is_complete_true_at_4 PASSED
tests/test_core/test_checkin_flow.py::test_is_complete_true_above_4 PASSED
tests/test_core/test_checkin_flow.py::test_total_questions_is_4 PASSED
12 passed in 0.82s
```

### TC-2: Service tests CheckInService

```
tests/test_services/test_checkin_service.py::test_create_session_returns_checkin_and_question PASSED
tests/test_services/test_checkin_service.py::test_create_session_employee_has_empty_name PASSED
tests/test_services/test_checkin_service.py::test_process_answer_saves_chunk PASSED
tests/test_services/test_checkin_service.py::test_process_answer_sets_employee_name_on_first_turn PASSED
tests/test_services/test_checkin_service.py::test_process_answer_returns_next_question PASSED
tests/test_services/test_checkin_service.py::test_process_answer_completes_on_fourth_answer PASSED
tests/test_services/test_checkin_service.py::test_process_answer_raises_on_completed_session PASSED
tests/test_services/test_checkin_service.py::test_process_answer_not_found_raises PASSED
tests/test_services/test_checkin_service.py::test_complete_session_calls_embed_and_updates_status PASSED
tests/test_services/test_checkin_service.py::test_complete_session_generates_embeddings PASSED
tests/test_services/test_checkin_service.py::test_get_session_status_returns_checkin PASSED
tests/test_services/test_checkin_service.py::test_get_session_status_not_found_raises PASSED
12 passed in 1.94s
```

### TC-3: API endpoint tests

```
tests/test_api/test_checkin.py::test_start_returns_session_id_and_question PASSED
tests/test_api/test_checkin.py::test_start_returns_unique_session_ids PASSED
tests/test_api/test_checkin.py::test_answer_returns_next_question PASSED
tests/test_api/test_checkin.py::test_full_flow_integration PASSED
tests/test_api/test_checkin.py::test_answer_unknown_session_returns_404 PASSED
tests/test_api/test_checkin.py::test_answer_completed_session_returns_409 PASSED
tests/test_api/test_checkin.py::test_status_in_progress PASSED
tests/test_api/test_checkin.py::test_status_returns_questions_answered PASSED
tests/test_api/test_checkin.py::test_status_unknown_session_returns_404 PASSED
9 passed in 2.34s
```

### TC-4: Full e2e flow (4 turns)

```
tests/test_api/test_checkin.py::test_full_flow_integration PASSED
1 passed in 1.68s
```

### TC-5: Full suite without regressions

```
147 passed, 3 skipped, 2 warnings in 3.82s
```

The 3 skipped tests are pre-existing marks from EPIC-002 (`test_her_models.py`).
The 2 warnings are pre-existing `SAWarning` from the same EPIC-002 tests.

### TC-6: Migration 010 applied

```
alembic heads:
  010 (head)

alembic history (tail):
  009 -> 010 (head), Make her.check_ins.employee_id nullable.
  008 -> 009, Create her.check_in_chunks table with HNSW index.
  007 -> 008, Create her.check_ins table.
  006 -> 007, Create her.employees table.
```

Note: `alembic current` does not display the revision number interactively in this environment because the test fixture runs `alembic downgrade base` + `alembic upgrade head` per session and leaves `her.alembic_version` empty after teardown. The migration tree and the fact that 147 DB-backed tests pass confirm the migration is correctly applied during test execution.

---

## Observaciones

1. The `SAWarning: transaction already deassociated from connection` warning appears in two pre-existing model tests from EPIC-002. It does not affect EPIC-004 functionality and is not a regression.

2. The `alembic current` command shows no output because `her.alembic_version` is emptied by the test session fixture teardown. This is expected behavior for the test harness and does not indicate a problem.

3. The 3 skipped tests are `pytest.mark.skip`-decorated tests from `test_her_models.py` (EPIC-002). They are not related to EPIC-004 and do not represent regressions.

4. All 8 defined Acceptance Criteria from §7 of the Technical Spec are covered by the test suite and pass.
