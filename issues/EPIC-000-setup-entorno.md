# EPIC-000: Setup de Entorno

**Status:** completed
**Completado:** 2026-05-16

## Descripción
Preparar el entorno local completo antes de tocar código de negocio. Desvinculación del remote GitHub de origen, creación del workflow local de issues, adaptación de dependencias y levantamiento de la base de datos con pgvector.

## Tareas
- [x] **ENV-00** — Remote cambiado de `LIDR-academy/rag-estimation-service` → `gabinoguera/rag-her`
- [x] **ENV-00b** — Carpeta `issues/` creada con `TEMPLATE.md` y EPIC-000 a EPIC-007
- [x] **ENV-01** — Proyecto renombrado a `her-poc` en `pyproject.toml`
- [x] **ENV-02** — Dependencias actualizadas: eliminados `openai>=1.0`, `tiktoken>=0.7`; añadidos `google-genai>=2.3.0`, `google-cloud-speech>=2.28.0`, `google-cloud-texttospeech>=2.20.0`, `python-multipart>=0.0.9`
- [x] **ENV-03** — `.venv` creado con Python 3.11.14 (`/opt/homebrew/bin/python3.11`), dependencias instaladas con `pip install -e ".[dev]"`
- [x] **ENV-04** — `.env` creado (no `.env.example`) con todas las variables HER. `GOOGLE_APPLICATION_CREDENTIALS` apunta a `almawolf-7bbb108314b5.json`
- [x] **ENV-05** — `docker-compose.yml` actualizado: DB `her_poc`, volumen `pgdata_her`, servicio `her-api`, **puerto 5433** (5432 ocupado por PostgreSQL de Homebrew local)
- [x] **ENV-06** — PostgreSQL 16 + pgvector 0.8.2 corriendo en Docker (`localhost:5433`)
- [x] **ENV-07** — `alembic.ini` y `alembic/env.py` actualizados: DB `her_poc`, puerto `5433`, schema `her`, `version_table_schema` dinámico vía env var

## Notas de implementación

- **Puerto 5433:** El Mac tiene un PostgreSQL de Homebrew corriendo en el puerto 5432 (PID 983). Docker expone en 5433 para evitar el conflicto. Todos los clientes deben usar `localhost:5433`.
- **Credenciales GCP:** Service account `her-poc-speech` creada en proyecto `Almawolf-AIOps` con roles `Cliente de Cloud Speech` y `Cliente de Cloud Text-to-Speech`. JSON en `almawolf-7bbb108314b5.json` (ignorado por git).
- **`.gitignore`:** Añadidos patrones `*service-account*.json` y `*credentials*.json`.
- **Commit:** `60caa05` — 66 ficheros subidos a `gabinoguera/rag-her`.

## Paralelización interna

| Tarea | Paralelo con | Espera a |
|-------|-------------|---------|
| ENV-00 | ENV-00b | — |
| ENV-00b | ENV-00 | — |
| ENV-01 | ENV-02, ENV-05 | ENV-00 |
| ENV-02 | ENV-01, ENV-05 | ENV-00 |
| ENV-03 | ENV-05 | ENV-02 |
| ENV-04 | ENV-05 | ENV-01, ENV-02 |
| ENV-05 | ENV-01, ENV-02 | ENV-00 |
| ENV-06 | — | ENV-05 |
| ENV-07 | — | ENV-06 |
