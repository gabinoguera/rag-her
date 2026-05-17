# HER — Arquitectura del Sistema

> Inteligencia operacional conversacional para AlmaWolf.
> Última actualización: Mayo 2026

---

## Visión

HER es un agente conversacional que realiza check-ins diarios con empleados y permite a la dirección consultar el estado operacional del equipo en lenguaje natural. La respuesta del CEO llega sintetizada por un modelo de lenguaje en ~80 palabras, fundamentada en los check-ins reales del día.

```
EMPLEADO                                          CEO
    │                                              │
    │ "¿Qué hiciste hoy?"                          │ "¿En qué está el equipo?"
    │ [graba voz]                                  │ [pregunta en texto o voz]
    ▼                                              ▼
 check-in                                     consulta RAG
 4 turnos                                     síntesis Gemini
 vectorizado                                  respuesta ~80 palabras
```

---

## Arquitectura hexagonal — estado actual

El sistema sigue los principios de arquitectura hexagonal (puertos y adaptadores). El dominio de negocio no conoce FastAPI, PostgreSQL ni Google Cloud; solo trabaja contra interfaces.

```
┌─────────────────────────────────────────────────────────────────┐
│                    ADAPTADORES PRIMARIOS                        │
│          (conducen la aplicación desde el exterior)             │
│                                                                 │
│  adapters/primary/web/          app/api/v1/                     │
│  ┌──────────────────────┐       ┌──────────────────────┐        │
│  │  Frontend HTML/JS    │──────▶│  REST API (FastAPI)  │        │
│  │  index.html          │       │  /checkin/*          │        │
│  │  employee.html       │       │  /ceo/*              │        │
│  │  ceo.html            │       │  /speech/*           │        │
│  └──────────────────────┘       │  /health             │        │
│                                 └──────────┬───────────┘        │
└──────────────────────────────────────────┬─┘────────────────────┘
                                           │
┌──────────────────────────────────────────▼────────────────────┐
│                      NÚCLEO DE LA APLICACIÓN                   │
│                                                                │
│  app/services/                  app/core/                      │
│  ┌──────────────────────┐       ┌──────────────────────┐       │
│  │  CheckInService      │──────▶│  checkin_flow.py     │       │
│  │  CeoService          │──────▶│  ceo_query.py        │       │
│  └──────────────────────┘       │  embeddings.py       │       │
│                                 │  generation.py       │       │
│  app/models/                    │  ranking.py          │       │
│  ┌──────────────────────┐       │  speech.py           │       │
│  │  Employee            │       │  tts.py              │       │
│  │  CheckIn             │       │  prompts.py          │       │
│  │  CheckInChunk        │       └──────────────────────┘       │
│  └──────────────────────┘                                      │
└──────────────────────────────────┬────────────────────────────┘
                                   │
┌──────────────────────────────────▼────────────────────────────┐
│                   ADAPTADORES SECUNDARIOS                      │
│           (conducidos por la aplicación hacia el exterior)     │
│                                                                │
│  PostgreSQL + pgvector        Google Cloud AI                  │
│  ┌──────────────────────┐     ┌──────────────────────┐         │
│  │  schema: her         │     │  Gemini 2.5 Flash    │         │
│  │  employees           │     │  (generación)        │         │
│  │  check_ins           │     │                      │         │
│  │  check_in_chunks     │     │  text-multilingual-  │         │
│  │  Vector(768) HNSW    │     │  embedding-002 (768d)│         │
│  └──────────────────────┘     │                      │         │
│                               │  Cloud STT (chirp_2) │         │
│                               │  Cloud TTS (Neural2) │         │
│                               └──────────────────────┘         │
└───────────────────────────────────────────────────────────────┘
```

> **Nota:** La refactorización al hexágono completo está en progreso. Actualmente `app/core/` contiene tanto lógica de dominio como adaptadores de infraestructura (Google Cloud clients). La separación formal de puertos se completará en la siguiente fase.

---

## Los tres flujos principales

### Flujo 1 — Check-in del empleado

El empleado responde 4 preguntas fijas. Al completar el cuarto turno, todas las respuestas se vectorizan y persisten para que el CEO las pueda consultar.

```
Browser                  FastAPI              PostgreSQL        Google Cloud
   │                        │                     │                  │
   │── POST /checkin/start ─▶│                     │                  │
   │                        │── INSERT CheckIn ──▶│                  │
   │◀─ {session_id, q0} ────│                     │                  │
   │                        │                     │                  │
   │  [usuario habla]        │                     │                  │
   │── POST /speech/         │                     │                  │
   │     transcribe ────────▶│── asyncio.to_thread(SpeechClient) ──▶│
   │◀─ {transcript} ─────────│◀─────────────────────────────────────│
   │                        │                     │                  │
   │── POST /checkin/        │                     │                  │
   │   {session_id}/answer ─▶│                     │                  │
   │                        │── INSERT Chunk ─────▶│                  │
   │                        │   (sin embedding aún)│                  │
   │◀─ {next_question} ──────│                     │                  │
   │                        │                     │                  │
   │   [×4 turnos]           │                     │                  │
   │                        │                     │                  │
   │── POST /answer [4º] ───▶│                     │                  │
   │                        │── batch embed ───────────────────────▶│
   │                        │◀─ 4 vectores 768d ──────────────────── │
   │                        │── UPDATE chunks.embedding ──────────▶ │
   │                        │── UPDATE checkin.status=completed ──▶ │
   │◀─ {is_complete: true} ──│                     │                  │
```

**Preguntas fijas:**
1. `"¡Hola! Soy HER. ¿Cómo te llamas?"` — captura el nombre del empleado
2. `"¿En qué trabajaste hoy, {name}?"`
3. `"¿Tuviste algún bloqueo o necesitas ayuda?"`
4. `"¿Qué planeas hacer mañana?"`

---

### Flujo 2 — Consulta del CEO (RAG)

```
Browser              FastAPI          pgvector          Gemini
   │                    │                 │                │
   │── POST /ceo/query ─▶│                 │                │
   │   {question}        │                 │                │
   │                    │── embed question ─────────────────▶│
   │                    │◀─ vector 768d (RETRIEVAL_QUERY) ───│
   │                    │                 │                │
   │                    │── SQL coseno ──▶│                │
   │                    │   JOIN employees│                │
   │                    │   WHERE status  │                │
   │                    │   = 'completed' │                │
   │                    │◀─ top-10 chunks │                │
   │                    │                 │                │
   │                    │── re-ranking    │                │
   │                    │   sim×0.70 +    │                │
   │                    │   recency×0.30  │                │
   │                    │                 │                │
   │                    │── confidence ─▶ │                │
   │                    │   top_score     │                │
   │                    │   ≥0.70 = alta  │                │
   │                    │   ≥0.45 = media │                │
   │                    │   <0.45 = baja  │                │
   │                    │                 │                │
   │                    │── prompt CEO ──────────────────▶ │
   │                    │   max 80 palabras               │
   │                    │◀─ respuesta ──────────────────── │
   │                    │                 │                │
   │                    │── POST /speech/ │                │
   │                    │   synthesize ──────────────────▶ │
   │                    │◀─ audio MP3 ──────────────────── │
   │◀─ {answer,         │                 │                │
   │    confidence,     │                 │                │
   │    sources,        │                 │                │
   │    audio} ─────────│                 │                │
```

---

### Flujo 3 — Speech (STT / TTS)

Ambos servicios son **síncronos** por parte del SDK de Google Cloud y se envuelven en `asyncio.to_thread()` para no bloquear el event loop de FastAPI.

```
Frontend              FastAPI             Google Cloud
   │                     │                     │
   │  [MediaRecorder]     │                     │
   │── POST /speech/      │                     │
   │   transcribe ───────▶│── asyncio.to_thread │
   │   audio/webm         │   (SpeechClient     │
   │                      │    .recognize())   ▶│
   │                      │◀─ transcript ────── │
   │◀─ {transcript,       │                     │
   │    confidence} ───── │                     │
   │                      │                     │
   │── POST /speech/       │                     │
   │   synthesize ────────▶│── asyncio.to_thread │
   │   {text}              │   (TTS.synthesize  ▶│
   │                       │    _speech())       │
   │                       │◀─ bytes MP3 ─────── │
   │◀─ audio/mpeg ─────────│                     │
```

**Configuración STT:** modelo `chirp_2`, `AutoDetectDecodingConfig` (acepta `audio/webm;codecs=opus` del navegador), idioma `es-ES`.

**Configuración TTS:** voz `es-ES-Neural2-A`, encoding `MP3`.

---

## Modelo de datos

```
her.employees
┌──────────────────────────────────────┐
│ id          UUID  PK                 │
│ name        TEXT  NOT NULL           │
│ created_at  TIMESTAMPTZ              │
└──────────────┬───────────────────────┘
               │ 1:N
               ▼
her.check_ins
┌──────────────────────────────────────┐
│ id           UUID  PK                │
│ employee_id  UUID  FK (nullable*)    │
│ session_id   TEXT  UNIQUE            │
│ status       TEXT  in_progress|      │
│                    completed|failed  │
│ started_at   TIMESTAMPTZ             │
│ completed_at TIMESTAMPTZ nullable    │
└──────────────┬───────────────────────┘
               │ 1:4
               ▼
her.check_in_chunks
┌──────────────────────────────────────┐
│ id              UUID  PK             │
│ checkin_id      UUID  FK CASCADE     │
│ question_index  INT   0-3            │
│ question_text   TEXT                 │
│ answer_text     TEXT                 │
│ embedding       Vector(768) nullable │ ◀── HNSW (coseno)
│ created_at      TIMESTAMPTZ          │     m=16, ef=200
└──────────────────────────────────────┘
```

> *`employee_id` es nullable por diseño: la sesión se crea antes de conocer el nombre del empleado (el nombre se captura en el primer turno de la conversación).

**Índice HNSW:**
```sql
CREATE INDEX idx_check_in_chunks_embedding
    ON her.check_in_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m=16, ef_construction=200);
```

---

## Sistema de embeddings y re-ranking

### Embeddings

| Contexto | task_type | Cuándo |
|---|---|---|
| Indexar respuestas del empleado | `RETRIEVAL_DOCUMENT` | Al completar el check-in |
| Vectorizar pregunta del CEO | `RETRIEVAL_QUERY` | En cada consulta |

Modelo: `text-multilingual-embedding-002` · 768 dimensiones · multilingüe

### Re-ranking

```
final_score = 0.70 × similarity   (distancia coseno pgvector)
            + 0.30 × recency      (exp(-0.03 × edad_en_meses))
```

La ponderación favorece respuestas recientes con alta relevancia semántica. El campo `recency_score` decae lentamente: un check-in de 3 meses aún puntúa ~0.91.

### Confianza de la respuesta

```
top_score ≥ 0.70  →  "alta"    (contexto sólido, respuesta fiable)
top_score ≥ 0.45  →  "media"   (contexto parcial, respuesta orientativa)
top_score < 0.45  →  "baja"    (pocos datos relevantes, declarado al CEO)
sin chunks        →  "sin_datos" (Gemini no se invoca)
```

---

## Decisiones arquitectónicas clave

### ADR-001: Un schema `her` para HER, preservar `rag` legacy
Las migraciones 001-005 que crean el schema `rag` (tablas del sistema de estimaciones) se conservan en la cadena `down_revision` de Alembic para integridad histórica, pero no se ejecutan en entornos HER puros. El schema operativo de HER es `her`.

### ADR-002: Embeddings en batch al completar, no turno a turno
Vectorizar cada respuesta inmediatamente tras recibirla generaría 4 llamadas a la API de embeddings por sesión. Vectorizar en batch al completar genera 1 llamada (con `contents=[texto1, texto2, ...]`). La penalización es que los chunks no son buscables hasta que el check-in termina — aceptable para el caso de uso.

### ADR-003: `asyncio.to_thread()` para clientes síncronos de Google Cloud
Los clientes de `google-cloud-speech` y `google-cloud-texttospeech` son síncronos. Envolverlos en `asyncio.to_thread()` permite mantener el event loop de FastAPI libre durante las llamadas de red. El cliente de `google-genai` ofrece el path async nativo (`client.aio.models.*`) que se usa directamente.

### ADR-004: Frontend vanilla sin bundler
El frontend (HTML/JS) en `adapters/primary/web/` no usa frameworks ni bundlers. La decisión reduce la complejidad operacional del PoC. La migración a un SPA (React, Vue) es trivial: basta con cambiar el contenido del directorio `adapters/primary/web/` sin tocar el backend.

### ADR-005: `session.begin()` en el factory de sesiones
SQLAlchemy async no hace auto-commit. Sin `async with session.begin()`, los `flush()` del servicio se revierten al cerrar la sesión. El factory `get_db_session()` abre la transacción explícitamente, auto-commitea al salir limpiamente y hace rollback en excepciones.

---

## Stack tecnológico

| Capa | Tecnología | Versión / Detalle |
|---|---|---|
| API | FastAPI + Uvicorn | Python 3.11 async |
| ORM | SQLAlchemy | 2.0 async + asyncpg |
| Migraciones | Alembic | Schema `her` |
| Vectores | pgvector | 0.8.2, Vector(768) |
| Base de datos | PostgreSQL | 16 (Docker local: puerto 5433) |
| LLM | Gemini 2.5 Flash | `google-genai>=2.3.0`, path `client.aio.models.*` |
| Embeddings | text-multilingual-embedding-002 | 768d, multilingüe |
| STT | Google Cloud Speech-to-Text v2 | `chirp_2`, es-ES |
| TTS | Google Cloud Text-to-Speech | `es-ES-Neural2-A`, MP3 |
| Auth GCP | Application Default Credentials | service account JSON |
| Frontend | HTML5 + CSS3 + JS vanilla | Sin frameworks ni bundlers |
| Logging | structlog | Structured JSON |
| Validación | Pydantic v2 | Schemas request/response |

---

## Estructura del proyecto

```
/
├── adapters/
│   └── primary/
│       └── web/                 ← Adaptador primario: Frontend
│           ├── index.html       ← Selector de rol (landing)
│           ├── employee.html    ← Flujo check-in (4 turnos, voz)
│           ├── ceo.html         ← Consulta CEO (RAG + TTS)
│           ├── style.css        ← Design system (dark theme)
│           └── js/
│               ├── employee.js
│               └── ceo.js
│
├── app/                         ← Backend FastAPI
│   ├── main.py                  ← App factory, lifespan, StaticFiles
│   ├── config.py                ← Settings (pydantic-settings)
│   ├── db.py                    ← Engine async, session factory
│   ├── dependencies.py          ← Inyección de dependencias
│   │
│   ├── api/v1/                  ← Adaptadores primarios REST
│   │   ├── checkin.py           ← POST /start, /answer, GET /status
│   │   ├── ceo.py               ← POST /query, GET /summary
│   │   ├── speech.py            ← POST /transcribe, /synthesize
│   │   └── health.py
│   │
│   ├── core/                    ← Dominio y casos de uso
│   │   ├── checkin_flow.py      ← Lógica pura: 4 preguntas
│   │   ├── ceo_query.py         ← Pipeline RAG: embed→search→rank→generate
│   │   ├── embeddings.py        ← EmbeddingService (google-genai)
│   │   ├── generation.py        ← GenerationService (gemini-2.5-flash)
│   │   ├── ranking.py           ← recency_score, calculate_final_score
│   │   ├── speech.py            ← STTService (Google Cloud)
│   │   ├── tts.py               ← TTSService (Google Cloud)
│   │   └── prompts.py           ← Constantes de prompts (CEO + RAG)
│   │
│   ├── models/                  ← SQLAlchemy ORM (schema: her)
│   │   ├── employee.py
│   │   ├── checkin.py
│   │   └── checkin_chunk.py     ← Vector(768)
│   │
│   └── services/                ← Orquestación de casos de uso
│       ├── checkin_service.py   ← create_session, process_answer, complete
│       └── ceo_service.py       ← query, daily_summary
│
├── alembic/
│   └── versions/
│       ├── 001-005_*.py         ← [LEGACY] schema rag
│       ├── 006_create_her_schema.py
│       ├── 007_create_employees.py
│       ├── 008_create_check_ins.py
│       ├── 009_create_check_in_chunks.py  ← índice HNSW
│       └── 010_make_checkin_employee_id_nullable.py
│
└── tests/                       ← pytest-asyncio, 213 tests
    ├── test_core/
    ├── test_services/
    ├── test_api/
    └── test_models/
```

---

## Entorno local

```bash
# PostgreSQL + pgvector en Docker (puerto 5433 — el 5432 está ocupado por Homebrew)
docker compose up postgres -d

# Aplicar migraciones
DATABASE_URL=postgresql+asyncpg://dev:dev@localhost:5433/her_poc \
DATABASE_SCHEMA=her \
alembic upgrade head

# Levantar API
uvicorn app.main:app --reload --port 8000

# Frontend disponible en http://localhost:8000 (StaticFiles montado si adapters/primary/web/ existe)
```

**Variables de entorno requeridas (`.env`):**

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://dev:dev@localhost:5433/her_poc` |
| `GEMINI_API_KEY` | API key de Google AI Studio |
| `GOOGLE_CLOUD_PROJECT` | ID del proyecto GCP (para STT/TTS) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Ruta al JSON del service account |

---

## Próximos pasos arquitectónicos

1. **Separar puertos formales** — definir interfaces `EmbeddingPort`, `GenerationPort`, `SpeechPort` en `app/core/ports/` para que el dominio no importe directamente las implementaciones de Google Cloud
2. **Migraciones de UI** — cuando la complejidad del frontend justifique un framework, reemplazar `adapters/primary/web/` por una SPA compilada sin cambios en el backend
3. **Contexto compartido entre managers** — ampliar la búsqueda RAG para cruzar empleados de la misma empresa (necesita campo `company_id` en `Employee`)
4. **Persistencia de audio** — opcionalmente almacenar los audio de check-in en Cloud Storage antes de transcribir, para auditoría
