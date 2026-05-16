# QA Report: EPIC-001 — Migración del Núcleo RAG a Gemini

**Fecha:** 2026-05-16
**Agente:** @qa-criteria-validator
**Estado:** Criterios definidos — pendiente validacion post-implementacion

---

## Resumen

Esta epic es una migración de infraestructura backend pura (OpenAI → Gemini). No hay cambios de UI ni endpoints nuevos. Las verificaciones son tests de integración API via curl/httpx y tests unitarios via pytest. No se requiere Playwright E2E.

---

## Acceptance Criteria — Resumen por RAG task

### RAG-01: Configuración

| Criterio | Tipo | Verificación |
|---|---|---|
| GEMINI_API_KEY presente en settings | Unitario | `assert settings.GEMINI_API_KEY != ""` |
| EMBEDDING_DIMENSIONS == 768 | Unitario | `assert settings.EMBEDDING_DIMENSIONS == 768` |
| EMBEDDING_MODEL == "text-multilingual-embedding-002" | Unitario | `assert settings.EMBEDDING_MODEL == "text-multilingual-embedding-002"` |
| LLM_MODEL == "gemini-2.5-flash" | Unitario | `assert settings.LLM_MODEL == "gemini-2.5-flash"` |
| No existe OPENAI_API_KEY ni LLM_TIMEOUT | Unitario | `assert not hasattr(settings, "OPENAI_API_KEY")` |
| openai y tiktoken eliminados de deps | Shell | `pip show openai` devuelve not found |
| google-genai >= 2.3.0 instalado | Shell | `pip show google-genai` muestra version >= 2.3.0 |

### RAG-02: Embeddings

| Criterio | Tipo | Verificación |
|---|---|---|
| generate_single_embedding devuelve 768 floats | Unitario | `assert len(result) == 768` |
| task_type RETRIEVAL_DOCUMENT por defecto | Unitario | verificar call_args del mock |
| task_type RETRIEVAL_QUERY cuando se especifica | Unitario | verificar call_args del mock |
| generate_embeddings batch devuelve N listas de 768 | Unitario | `assert all(len(e) == 768 for e in result)` |
| generate_embeddings([]) retorna [] sin llamar al SDK | Unitario | mock no invocado |
| ResourceExhausted → EmbeddingError | Unitario | pytest.raises(EmbeddingError) |
| Unauthenticated → EmbeddingError | Unitario | pytest.raises(EmbeddingError) |

### RAG-03: Generación

| Criterio | Tipo | Verificación |
|---|---|---|
| generate(prompt) devuelve string no vacío | Unitario | `assert isinstance(result, str) and result` |
| system_instruction se pasa en GenerateContentConfig | Unitario | verificar call_args del mock |
| response.text == None → GenerationError | Unitario | pytest.raises(GenerationError) |
| Unauthenticated → GenerationError inmediato (sin retry) | Unitario | mock invocado solo 1 vez |
| ResourceExhausted → GenerationError tras 4 reintentos | Unitario | mock invocado 4+ veces |

### RAG-04: Re-ranking

| Criterio | Tipo | Verificación |
|---|---|---|
| calculate_final_score(1.0, 0.0) == 0.70 | Unitario | `abs(score - 0.70) < 1e-9` |
| calculate_final_score(0.0, 1.0) == 0.30 | Unitario | `abs(score - 0.30) < 1e-9` |
| calculate_final_score(0.8, 0.9) == 0.83 | Unitario | `abs(score - 0.83) < 1e-9` |
| technology_match_score no existe en ranking.py | Unitario | ImportError o NameError |
| cost_range_score no existe en ranking.py | Unitario | ImportError o NameError |
| SQL query sin filtros chunk_type/technologies/cost | Unitario / integracion | revisar la query construida en retrieval.py |

### RAG-05a: Endpoints legacy eliminados

| Endpoint | HTTP Method | Esperado | Verificación |
|---|---|---|---|
| /api/v1/estimate | POST | 404 | `curl -s -o /dev/null -w "%{http_code}"` |
| /api/v1/ingest | POST | 404 | `curl -s -o /dev/null -w "%{http_code}"` |
| /api/v1/stats | GET | 404 | `curl -s -o /dev/null -w "%{http_code}"` |
| /api/v1/quote-generator | POST | 404 | `curl -s -o /dev/null -w "%{http_code}"` |

### RAG-05b: Health y arranque

| Criterio | Tipo | Verificación |
|---|---|---|
| GET /health → 200 | Integracion | `curl -s http://127.0.0.1:8000/health` |
| Arranque sin ImportError | Manual | revisar logs de uvicorn al iniciar |
| Arranque sin ModuleNotFoundError | Manual | revisar logs de uvicorn al iniciar |

---

## TC Classification Table

| TC   | Descripcion                                              | Tipo       | Motivo                                                        |
|------|----------------------------------------------------------|------------|---------------------------------------------------------------|
| TC-1 | Health check GET /health → 200                          | Paralelo   | Ruta independiente, sin estado, sin dependencias externas     |
| TC-2 | POST /api/v1/search → 200 sin 500 (embeddings 768d)     | Secuencial | Requiere GEMINI_API_KEY valida; TC-4 depende del estado       |
| TC-3 | Endpoints legacy (estimate/ingest/stats) → 404          | Paralelo   | Solo verifica ausencia de rutas; sin estado compartido        |
| TC-4 | Busqueda semantica con re-ranking 0.70/0.30 verificado  | Secuencial | Depende de datos/estado creados en TC-2                       |

TC-1 y TC-3 pueden ejecutarse en paralelo entre si y de forma independiente.
TC-2 debe ejecutarse antes que TC-4.

---

## Manual Testing Checklist (para ejecutar tras implementacion)

```bash
# 1. Verificar dependencias
pip show openai 2>&1 | grep -c "not found"   # debe ser 1
pip show tiktoken 2>&1 | grep -c "not found" # debe ser 1
pip show google-genai | grep Version         # debe mostrar >= 2.3.0

# 2. Verificar ausencia de referencias openai/tiktoken en codigo
grep -r "openai\|tiktoken" app/ --include="*.py"
# Debe devolver 0 lineas

# 3. Verificar config (EMBEDDING_DIMENSIONS=768 como default)
grep "EMBEDDING_DIMENSIONS" app/config.py
grep "GEMINI_API_KEY" app/config.py

# 4. TC-1: Health check
curl -s http://127.0.0.1:8000/health
# Esperado: {"status": "ok"} con HTTP 200

# 5. TC-3: Endpoints legacy
curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:8000/api/v1/estimate -H "Content-Type: application/json" -d '{}'
# Esperado: 404

curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:8000/api/v1/ingest -H "Content-Type: application/json" -d '{}'
# Esperado: 404

curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/v1/stats
# Esperado: 404

# 6. TC-2: Search sin 500
curl -s -X POST http://127.0.0.1:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "estimacion de proyecto backend API REST", "top_k": 5, "min_similarity": 0.4}'
# Esperado: HTTP 200, body con "results": [...] (puede estar vacia)

# 7. Verificar tests unitarios
pytest tests/ --asyncio-mode=auto -x
# Esperado: exit code 0, todos los tests pasan
```

---

## Success Criteria — Checklist final

### Funcionales
- [ ] `pytest tests/ --asyncio-mode=auto -x` sale con exit code 0
- [ ] test_embeddings.py: generate_single_embedding → 768 floats
- [ ] test_ranking.py: calculate_final_score usa pesos 0.70/0.30
- [ ] test_generation.py: GenerationService.generate() devuelve string no vacio
- [ ] GET /health → HTTP 200
- [ ] POST /api/v1/estimate → HTTP 404
- [ ] POST /api/v1/ingest → HTTP 404
- [ ] GET /api/v1/stats → HTTP 404
- [ ] POST /api/v1/search (query valida) → HTTP 200 sin 500
- [ ] Logs de arranque: sin ImportError ni ModuleNotFoundError de modulos legacy

### No-funcionales
- [ ] `grep -r "openai\|tiktoken" app/` devuelve 0 resultados
- [ ] `pip show openai` → not found
- [ ] `pip show tiktoken` → not found
- [ ] `pip show google-genai` → version >= 2.3.0
- [ ] EMBEDDING_DIMENSIONS default = 768 en app/config.py
- [ ] GEMINI_API_KEY (no OPENAI_API_KEY) en app/config.py
- [ ] 17 archivos legacy eliminados (chunk.py diferido a EPIC-002)
- [ ] `ruff check app/` sale limpio

---

## Notas importantes

1. **No usar Playwright** para esta epic. No hay UI. Los TCs son verificaciones via curl y pytest.

2. **Tests con skip marker**: los tests que insertan en rag.chunks con schema actual (Vector(1536)) deben llevar `@pytest.mark.skip(reason="Pendiente EPIC-002: columna embedding es Vector(1536)")`. Estos tests fallarian por mismatch de dimensiones aunque la implementacion sea correcta.

3. **Search con lista vacia es OK**: POST /api/v1/search puede devolver `{"results": [], "total_results": 0, ...}` si la DB esta vacia. Eso es comportamiento correcto, no un fallo.

4. **chunk.py NO se elimina en esta epic**: `app/models/chunk.py` se mantiene hasta EPIC-002 porque el endpoint de search todavia lee de `rag.chunks` con schema Vector(1536). Eliminarlo ahora romperia el search endpoint.

5. **Orden de implementacion afecta testing**: TC-2 debe ejecutarse antes que TC-4 para que haya datos en DB que permitan verificar el re-ranking.

---

## Archivos de referencia

- Issue completa: `issues/EPIC-001-migracion-gemini.md`
- Session context: `.claude/sessions/context_session_EPIC-001-migracion-gemini.md`
- Backend plan: `.claude/doc/EPIC-001-migracion-gemini/backend.md`
- Vertex AI plan: `.claude/doc/EPIC-001-migracion-gemini/vertex-ai-plan.md`
