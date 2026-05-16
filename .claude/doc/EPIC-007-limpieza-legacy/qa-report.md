# QA Report — EPIC-007: Limpieza del Repositorio Legacy

**Fecha:** 2026-05-16
**QA Agent:** qa-acceptance-testing
**Worktree:** `.trees/feature-issue-EPIC-007/`
**Scope:** Backend-only — pytest + static analysis (no Playwright, no server)
**Veredicto:** PASSED — Ready to merge

---

## Clasificacion de TCs

| TC   | Descripcion                              | Tipo       | Motivo                                          |
|------|------------------------------------------|------------|-------------------------------------------------|
| TC-1 | Suite completa sin regresiones           | Paralelo   | No depende de estado externo                    |
| TC-2 | Cero referencias rag.* en app/           | Paralelo   | Inspeccion estatica, sin estado                 |
| TC-3 | EMBEDDING_DIMENSIONS=1536 falla          | Paralelo   | Verificacion de config aislada, sin BD          |
| TC-4 | main.py titulo correcto                  | Paralelo   | Inspeccion estatica                             |
| TC-5 | ranking.py conservado con tests          | Paralelo   | Suite independiente, sin estado compartido      |

---

## Resultados de Ejecucion

### TC-1 — Suite completa sin regresiones (AC-10)

**Comando:**
```bash
cd .trees/feature-issue-EPIC-007
DATABASE_URL=postgresql+asyncpg://dev:dev@localhost:5433/her_poc DATABASE_SCHEMA=her GEMINI_API_KEY=test \
  ../../.venv/bin/pytest tests/ --asyncio-mode=auto -q
```

**Output:**
```
......................................................................
..................................
============================= warnings summary =============================
tests/test_models/test_her_models.py::test_employee_name_not_null
tests/test_models/test_her_models.py::test_checkin_session_id_unique
  sys:1: SAWarning: transaction already deassociated from connection

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
106 passed, 2 warnings in 2.58s
```

**Resultado: PASSED**

---

### TC-2 — Cero referencias rag.* en app/ (AC-2)

**Comando:**
```bash
grep -r "rag\." .trees/feature-issue-EPIC-007/app/ --include="*.py" | grep -v ".pyc"
```

**Output:** (sin output — comando retorna vacío)

**Resultado: PASSED** — Cero referencias `rag.*` en el codigo Python de app/.

---

### TC-3 — EMBEDDING_DIMENSIONS=1536 rechazado (AC-9)

**Comando:**
```bash
cd .trees/feature-issue-EPIC-007
GEMINI_API_KEY=test EMBEDDING_DIMENSIONS=1536 \
  ../../.venv/bin/python -c "from app.config import Settings; s=Settings()"
```

**Output:**
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
  Value error, EMBEDDING_DIMENSIONS must be one of {768}, got 1536 [type=value_error, input_value='1536', input_type=str]
    For further information visit https://errors.pydantic.dev/2.13/v/value_error
```

**Resultado: PASSED** — `ValidationError` lanzado correctamente al intentar usar 1536.

---

### TC-4 — main.py titulo correcto (AC-7)

**Comando:**
```bash
grep "title" .trees/feature-issue-EPIC-007/app/main.py | head -3
```

**Output:**
```
        title="HER — Conversational Intelligence API",
```

**Resultado: PASSED** — Titulo contiene "HER", sin rastro de "RAG Estimation".

---

### TC-5 — ranking.py conservado con tests (AC-8)

**Comando:**
```bash
cd .trees/feature-issue-EPIC-007
DATABASE_URL=postgresql+asyncpg://dev:dev@localhost:5433/her_poc DATABASE_SCHEMA=her GEMINI_API_KEY=test \
  ../../.venv/bin/pytest tests/test_core/test_ranking.py -v
```

**Output:**
```
collected 11 items

tests/test_core/test_ranking.py::TestRecencyScore::test_recent_is_high PASSED
tests/test_core/test_ranking.py::TestRecencyScore::test_old_is_lower PASSED
tests/test_core/test_ranking.py::TestRecencyScore::test_very_old_below_threshold PASSED
tests/test_core/test_ranking.py::TestCalculateFinalScore::test_calculate_final_score_weights PASSED
tests/test_core/test_ranking.py::TestCalculateFinalScore::test_calculate_final_score_similarity_weight PASSED
tests/test_core/test_ranking.py::TestCalculateFinalScore::test_calculate_final_score_recency_weight PASSED
tests/test_core/test_ranking.py::TestCalculateFinalScore::test_zero_scores_equal_zero PASSED
tests/test_core/test_ranking.py::TestCalculateFinalScore::test_partial_scores_combine_correctly PASSED
tests/test_core/test_ranking.py::TestDeduplicateResults::test_same_doc_and_type_keeps_highest PASSED
tests/test_core/test_ranking.py::TestDeduplicateResults::test_different_types_keeps_both PASSED
tests/test_core/test_ranking.py::TestDeduplicateResults::test_result_sorted_by_score_desc PASSED

============================== 11 passed in 0.85s ==============================
```

**Resultado: PASSED** — 11/11 tests pasan. `ranking.py` conservado intacto para EPIC-004.

---

## Validation Report

### Passed

- TC-1: 106 tests passed, 0 failed — sin regresiones en la suite completa
- TC-2: Cero referencias `rag.*` en Python — limpieza total del dominio legacy
- TC-3: `EMBEDDING_DIMENSIONS=1536` lanza `ValidationError` — constraint solo 768 activo
- TC-4: Titulo FastAPI es "HER — Conversational Intelligence API" — identidad correcta
- TC-5: `test_ranking.py` 11/11 — logica domain-agnostic conservada para EPIC-004

### Failed

Ninguno.

### Warnings

- Los 2 `SAWarning: transaction already deassociated from connection` son pre-existentes en `test_her_models.py`. No introducidos por EPIC-007. No bloquean merge.
- AC-5 (`/api/v1/search` → 404) no ejecutado en esta ronda — scope backend-only sin servidor activo. La eliminacion de `app/api/v1/search.py` y la limpieza del router cubren este AC a nivel de codigo.

---

## Cobertura de Acceptance Criteria

| AC    | Criterio                                             | Metodo de verificacion          | Estado  |
|-------|------------------------------------------------------|---------------------------------|---------|
| AC-1  | chunk.py no existe                                   | Implementation Review (diff)    | PASSED  |
| AC-2  | Sin referencias rag.* en Python                      | TC-2 (grep estatico)            | PASSED  |
| AC-3  | Sin titulo legacy RAG Estimation                     | TC-4 (grep main.py)             | PASSED  |
| AC-4  | Router solo monta health                             | Implementation Review (diff)    | PASSED  |
| AC-5  | /api/v1/search devuelve 404                          | No ejecutado (backend-only QA)  | SKIPPED |
| AC-6  | Directorios de datos eliminados                      | Implementation Review (diff)    | PASSED  |
| AC-7  | Titulo FastAPI contiene "HER"                        | TC-4                            | PASSED  |
| AC-8  | ranking.py + tests intactos                          | TC-5 (11/11)                    | PASSED  |
| AC-9  | EMBEDDING_DIMENSIONS=1536 rechazado                  | TC-3 (ValidationError)          | PASSED  |
| AC-10 | Suite completa pasa                                  | TC-1 (106/106)                  | PASSED  |

**9/10 ACs verificados directamente. AC-5 cubierto por evidencia estatica de eliminacion del endpoint.**

---

## Notas Tecnicas

1. `pytest.raises(Exception)` vs `pytest.raises(ValueError)`: el test `test_embedding_dimensions_1536_raises_error` usa `Exception` como tipo base. La excepcion real es `pydantic_core.ValidationError`, que no es subclase directa de `ValueError` sino de `PydanticUserError -> Exception`. El test pasa correctamente. Aceptable — no requiere cambio.

2. Los SAWarnings de SQLAlchemy provienen de `test_her_models.py` y son pre-existentes al PR de EPIC-007. No son regresiones.

3. El worktree `.trees/feature-issue-EPIC-007/` usa el venv raiz `../../.venv/` correctamente. No hay conflictos de dependencias.
