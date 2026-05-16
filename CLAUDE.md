# HER PoC — Instrucciones para Claude

## Proyecto
**HER** — Inteligencia operacional conversacional para AlmaWolf.
Agente conversacional que hace check-ins a empleados y permite al CEO consultar resúmenes RAG.

## Stack
- **Backend:** FastAPI + SQLAlchemy async + Alembic
- **DB:** PostgreSQL 16 + pgvector 0.8.2 — `localhost:5433` (puerto 5433, no 5432 — Homebrew ocupa el 5432)
- **Schema:** `her` (no `rag`, no `public`)
- **AI:** `google-genai>=2.3.0` — modelo `gemini-2.5-flash`, embeddings `text-multilingual-embedding-002` (768d)
- **Speech:** `google-cloud-speech` (STT) + `google-cloud-texttospeech` (TTS)
- **Frontend:** HTML/JS vanilla en `adapters/primary/web/`
- **Python:** 3.11 — venv en `.venv/`
- **Tests:** `pytest --asyncio-mode=auto` — DB de test en `localhost:5433/her_poc`

## Variables de entorno clave
```bash
DATABASE_URL=postgresql+asyncpg://dev:dev@localhost:5433/her_poc
DATABASE_SCHEMA=her
GEMINI_API_KEY=<en .env>
GOOGLE_APPLICATION_CREDENTIALS=<en .env>
```

## Workflow obligatorio por epic

**Cada epic debe seguir este ciclo completo sin saltarse pasos:**

```
1. /issue-spec {id}       → spec técnica con agentes especializados
2. /worktree-tdd {id}     → implementación TDD en worktree aislado
3. /review-spec {id}      → validar spec vs implementación (PR diff)
4. /update-feedback {id}  → QA con criterios de aceptación
                            (backend epics: via pytest + curl, no Playwright)
                            (frontend epics: via Playwright)
```

**Nunca empezar el paso N+1 sin completar el paso N.**

## Estado de las epics

| Epic | Status | PR |
|------|--------|----|
| EPIC-000 — Setup entorno | ✅ completed | — |
| EPIC-001 — Migración Gemini | ✅ in-review | [#1](https://github.com/gabinoguera/rag-her/pull/1) |
| EPIC-002 — Modelos DB | 🔄 open | — |
| EPIC-003 — Speech STT/TTS | ⏳ open (espera EPIC-002) | — |
| EPIC-004 — Check-in empleado | ⏳ open (espera EPIC-002) | — |
| EPIC-005 — Consulta CEO | ⏳ open (espera EPIC-002) | — |
| EPIC-006 — Frontend hexagonal | ⏳ open (espera 3+4+5) | — |
| EPIC-007 — Limpieza legacy | ⏳ open (paralelo desde EPIC-001) | — |

## Orden de ejecución

```
EPIC-002
  → EPIC-003 + EPIC-004 + EPIC-007  (paralelo, worktrees distintos)
      → EPIC-005
          → EPIC-006
```

## Reglas de worktree

- **SIEMPRE** usar rutas absolutas dentro del worktree: `.trees/feature-issue-{id}/`
- **NUNCA** editar ficheros en el directorio principal cuando hay un worktree activo
- El worktree se basa en `main` actualizado — hacer `git merge origin/main` si la rama base es antigua
- El venv siempre está en el raíz: `../../.venv/bin/` desde dentro del worktree

## Comandos de test (desde worktree)

```bash
# Tests unitarios (sin DB)
DATABASE_URL=postgresql+asyncpg://dev:dev@localhost:5433/her_poc DATABASE_SCHEMA=her GEMINI_API_KEY=test ../../.venv/bin/pytest tests/ --asyncio-mode=auto -q

# Migraciones
DATABASE_URL=postgresql+asyncpg://dev:dev@localhost:5433/her_poc DATABASE_SCHEMA=her ../../.venv/bin/alembic upgrade head

# Verificar cero referencias legacy
grep -r "from openai\|import openai\|from tiktoken" app/ | grep -v ".pyc"
```

## Notas técnicas importantes

- `client.aio.models.*` — siempre el path async en google-genai (no `client.models.*` que bloquea)
- Embeddings: `task_type="RETRIEVAL_DOCUMENT"` al indexar, `"RETRIEVAL_QUERY"` al buscar
- Puerto 5433: el Mac tiene PostgreSQL de Homebrew en 5432 — todos los clientes usan 5433
- `app/models/chunk.py` se mantiene hasta EPIC-002 (tiene Vector(1536) del schema legacy `rag`)
- Los 4 tests skipped en EPIC-001 se reactivan en EPIC-002 (rag.chunks → her.check_in_chunks)

## Issues y documentación

- Issues: `issues/EPIC-*.md` y `issues/*.md` — fuente de verdad local
- Spec técnica: dentro del mismo fichero de issue bajo `## Technical Spec`
- Roadmap completo: `docs/issues.md`
- Proposal original: `docs/proposal.md`
