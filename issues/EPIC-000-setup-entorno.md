# EPIC-000: Setup de Entorno

**Status:** open

## Descripción
Preparar el entorno local completo antes de tocar código de negocio. Desvinculación del remote GitHub de origen, creación del workflow local de issues, adaptación de dependencias y levantamiento de la base de datos con pgvector.

## Tareas
- ENV-00 — Desvincular remote GitHub (LIDR-academy)
- ENV-00b — Crear carpeta `issues/` con TEMPLATE
- ENV-01 — Renombrar proyecto en `pyproject.toml`
- ENV-02 — Actualizar dependencias (quitar openai/tiktoken, añadir google-genai/speech/tts)
- ENV-03 — Crear entorno virtual Python 3.11+
- ENV-04 — Actualizar `.env.example`
- ENV-05 — Actualizar `docker-compose.yml`
- ENV-06 — Verificar pgvector arranca correctamente
- ENV-07 — Configurar schema `her` en Alembic

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
