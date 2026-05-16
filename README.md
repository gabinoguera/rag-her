# HER — Conversational Intelligence API

Backend conversacional para check-ins de empleados con análisis semántico vía Gemini. Parte de la plataforma AlmaWolf HER.

## Stack

- **Backend:** FastAPI + SQLAlchemy async + Alembic
- **DB:** PostgreSQL 16 + pgvector 0.8.2 — `localhost:5433` (schema `her`)
- **AI:** `google-genai>=2.3.0` — modelo `gemini-2.5-flash`, embeddings `text-multilingual-embedding-002` (768d)
- **Speech:** `google-cloud-speech` (STT v2) + `google-cloud-texttospeech` (TTS)
- **Python:** 3.11 — venv en `.venv/`

## Prerequisitos

- **Python 3.11+**
- **Docker y Docker Compose** (para PostgreSQL con pgvector)
- **Gemini API key** (`GEMINI_API_KEY`)
- **Google Cloud service account** con permisos Speech-to-Text y Text-to-Speech (`GOOGLE_APPLICATION_CREDENTIALS`)

## Instalación y desarrollo local

1. Clonar el repositorio:
   ```bash
   git clone <repo-url>
   cd rag-estimation-service
   ```

2. Crear y activar entorno virtual:
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   ```

3. Instalar dependencias:
   ```bash
   pip install -e ".[dev]"
   ```

4. Levantar PostgreSQL con pgvector:
   ```bash
   docker compose up -d postgres
   ```

5. Configurar variables de entorno:
   ```bash
   cp .env.example .env
   # Editar .env: añadir GEMINI_API_KEY y GOOGLE_APPLICATION_CREDENTIALS
   ```

6. Ejecutar migraciones:
   ```bash
   DATABASE_URL=postgresql+asyncpg://dev:dev@localhost:5433/her_poc DATABASE_SCHEMA=her alembic upgrade head
   ```

7. Iniciar el servidor de desarrollo:
   ```bash
   DATABASE_URL=postgresql+asyncpg://dev:dev@localhost:5433/her_poc DATABASE_SCHEMA=her uvicorn app.main:app --reload
   ```

La API estará disponible en:
- API: http://localhost:8000/api/v1/health
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Variables de entorno

| Variable | Por defecto | Descripción |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://dev:dev@localhost:5432/estimations` | Conexión PostgreSQL |
| `DATABASE_SCHEMA` | `her` | Schema de base de datos |
| `GEMINI_API_KEY` | *(requerido)* | API key de Google Gemini |
| `GOOGLE_APPLICATION_CREDENTIALS` | *(requerido en producción)* | Path al service account JSON para STT/TTS |
| `EMBEDDING_MODEL` | `text-multilingual-embedding-002` | Modelo de embeddings Gemini (768d) |
| `EMBEDDING_DIMENSIONS` | `768` | Dimensiones del vector de embedding |
| `LLM_MODEL` | `gemini-2.5-flash` | Modelo LLM para generación de texto |
| `SERVICE_PORT` | `8000` | Puerto HTTP |
| `ENVIRONMENT` | `development` | `development` / `staging` / `production` |
| `LOG_LEVEL` | `DEBUG` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

## Tests

```bash
DATABASE_URL=postgresql+asyncpg://dev:dev@localhost:5433/her_poc DATABASE_SCHEMA=her GEMINI_API_KEY=test pytest tests/ --asyncio-mode=auto -q
```

## Estructura del proyecto

```
rag-estimation-service/
├── app/
│   ├── main.py             # FastAPI app, lifespan, middleware
│   ├── config.py           # Settings (Pydantic BaseSettings)
│   ├── dependencies.py     # Inyección de dependencias
│   ├── api/v1/             # Endpoints API (versionados)
│   │   ├── health.py       # GET /api/v1/health
│   │   └── router.py       # Registro de routers
│   ├── api/schemas/        # Schemas Pydantic de request/response
│   ├── core/               # Lógica de dominio
│   │   ├── embeddings.py   # EmbeddingService — Gemini 768d
│   │   ├── generation.py   # GenerationService — gemini-2.5-flash
│   │   ├── prompts.py      # Constantes de prompts
│   │   └── ranking.py      # Re-ranking por similitud + recencia
│   ├── models/             # Modelos SQLAlchemy
│   │   ├── employee.py     # Employee (her.employees)
│   │   ├── checkin.py      # CheckIn (her.check_ins)
│   │   └── checkin_chunk.py # CheckInChunk con Vector(768)
│   ├── services/           # Orquestación de casos de uso
│   └── utils/              # Logging, helpers
├── alembic/                # Migraciones (006-009 activas para her.*)
├── adapters/primary/web/   # Frontend HTML/JS (si existe)
├── tests/                  # Suite de tests
├── Dockerfile
└── docker-compose.yml
```

## Endpoints disponibles

### `GET /api/v1/health`

Health check del servicio y sus dependencias (base de datos, pgvector).

**Respuesta:**
```json
{
  "status": "healthy",
  "version": "0.2.0",
  "environment": "development",
  "dependencies": {
    "database": { "status": "healthy", "latency_ms": 1.23 },
    "pgvector": { "status": "healthy", "version": "0.8.2" }
  }
}
```

Estado `"healthy"` cuando todas las dependencias están activas, `"degraded"` en caso contrario.

---

## Documentación interactiva

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
