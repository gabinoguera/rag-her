# RAG Estimation Service

AI-powered software estimation service using Retrieval-Augmented Generation. Ingests historical software quotes, vectorizes them with pgvector, and generates data-driven estimations via LLM.

## Requirements

- Docker and Docker Compose

## Setup

```bash
cp .env.example .env
docker compose up --build
```

The service will be available at:
- API: http://localhost:8000/api/v1/health
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Tests

```bash
# Install dev dependencies locally
pip install -e ".[dev]"

# Run tests
pytest
```

## Project Structure

```
rag-estimation-service/
├── app/
│   ├── main.py             # FastAPI app, lifespan, middleware
│   ├── config.py           # Settings (Pydantic BaseSettings)
│   ├── dependencies.py     # Dependency injection
│   ├── api/v1/             # API endpoints (versioned)
│   ├── core/               # RAG pipeline (chunking, embeddings, retrieval)
│   ├── models/             # SQLAlchemy models
│   ├── services/           # Business logic
│   └── utils/              # Logging, helpers
├── alembic/                # Database migrations
├── tests/                  # Test suite
├── Dockerfile              # Multi-stage build
└── docker-compose.yml      # Dev environment (postgres + service)
```
