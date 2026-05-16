# HER PoC — Issues & Roadmap

**Proyecto:** HER (Inteligencia Operacional Conversacional)
**Repositorio base:** rag-estimation-service
**Stack objetivo:** FastAPI · PostgreSQL + pgvector · Gemini 2.5 Flash · Google Cloud STT/TTS · HTML/JS
**Última actualización:** 2026-05-16

---

## Nota sobre la librería de Google

La librería `google-generativeai` está **deprecada**. El SDK actual es:

```bash
pip install google-genai   # paquete: google-genai ≥ 2.3.0
```

```python
from google import genai
from google.genai import types

client = genai.Client(api_key="GEMINI_API_KEY")  # o lee env var automáticamente

# Generación
response = client.models.generate_content(model="gemini-2.5-flash", contents="...")

# Embeddings (768 dims)
response = client.models.embed_content(
    model="text-multilingual-embedding-002",
    contents="...",
    config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT", output_dimensionality=768),
)
```

Los servicios de voz son **independientes** del SDK de Gemini y usan credenciales GCP:

```bash
pip install google-cloud-speech google-cloud-texttospeech
# Auth: GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

---

## Herencia del repositorio legacy — Análisis de reutilización

Antes de ejecutar las epics, conviene tener claro qué se reutiliza, qué se adapta y qué se descarta del código existente.

### Chunking (`app/core/chunking.py`) — DESCARTAR

El chunker está 100% acoplado al dominio de presupuestos: opera sobre `QuoteInput` (scope_blocks, line_items, phases, team_members, costes). No hay nada aprovechable directamente. Para HER la estrategia de chunking es mucho más simple: **un chunk por par (pregunta, respuesta)**, con texto enriquecido:

```
Empleado: {name}
Fecha: {date}
Pregunta: {question_text}
Respuesta: {answer_text}
```

El patrón de construir texto estructurado antes de embeddear (en lugar de embeddear el raw text) sí es buena práctica heredada, pero el código se reescribe desde cero en `app/core/checkin_chunking.py`.

### Re-ranking (`app/core/ranking.py`) — ADAPTAR PARCIALMENTE

El re-ranking es **algorítmico puro**, sin modelo de ML. Usa una puntuación compuesta ponderada:

| Factor | Peso original | Para HER | Acción |
|--------|--------------|----------|--------|
| `similarity_score` (coseno pgvector) | 0.50 | **0.70** | Reutilizar, subir peso |
| `recency_score` (decaimiento exponencial) | 0.15 | **0.30** | Reutilizar sin cambios — info reciente es más valiosa para el CEO |
| `tech_match_score` (Jaccard de arrays) | 0.25 | — | Descartar, no aplica |
| `cost_range_score` (outlier MAD) | 0.10 | — | Descartar, no aplica |

Las funciones `recency_score()` y `deduplicate_results()` se copian tal cual. `calculate_final_score()` se adapta con los nuevos pesos. `deduplicate_results()` se adapta para deduplicar por `(employee_id, checkin_date)` en lugar de `(document_id, chunk_type)`.

### Confidence / grado de asertividad

No existe un "confidence score" formal ni un modelo de re-ranking externo (no hay cross-encoder, Cohere, etc.). Lo que hay es:
- `similarity_score` — similitud coseno cruda (0–1)
- `final_score` — compuesta ponderada (0–1)
- `top_score` / `avg_score` — logueados por búsqueda

Para HER se implementa un heurístico simple sobre `top_score` del primer resultado:

```python
if top_score >= 0.70: confidence = "alta"
elif top_score >= 0.45: confidence = "media"
else: confidence = "baja"  # Gemini debe indicar que no hay suficiente info
```

Además se instruye a Gemini en el system prompt para que comunique explícitamente cuando el contexto recuperado no es suficiente para responder con certeza.

### Pipeline de búsqueda (`app/core/retrieval.py`) — REUTILIZAR estructura

El patrón de `RetrievalService` es sólido y se migra casi íntegro:
- Query SQL con `1 - (embedding <=> :query_embedding) >= :min_similarity` → mantener
- `SET LOCAL hnsw.ef_search` antes de la búsqueda → mantener
- Timing (`time.monotonic()`) y logging estructurado → mantener
- `ScoredResult` dataclass → adaptar con los campos de HER

### Resumen de decisiones

| Módulo | Decisión | Nuevo nombre |
|--------|----------|--------------|
| `chunking.py` | Descartar | `checkin_chunking.py` (reescribir) |
| `ranking.py` | Adaptar | `ranking.py` (misma ubicación, nuevos pesos) |
| `retrieval.py` | Adaptar | `retrieval.py` (misma estructura, nuevo schema) |
| `embeddings.py` | Migrar a Gemini | `embeddings.py` |
| `generation.py` | Migrar a Gemini | `generation.py` |

---

## Epic 0 — Setup de Entorno

**Descripción:** Preparar el entorno local completo antes de tocar código de negocio. Incluye desvinculación del repositorio GitHub de origen, la adaptación del proyecto legacy (renombrado, limpieza de dependencias obsoletas), el workflow local de issues y el levantamiento de la base de datos con pgvector.

### Tareas

- [ ] **ENV-00** Desvincular el repositorio del remote GitHub de origen
  - El repositorio actual apunta a `https://github.com/LIDR-academy/rag-estimation-service.git`
  - Eliminar el remote para evitar pushes accidentales al repositorio legacy:
    ```bash
    git remote remove origin
    git remote -v  # debe devolver vacío
    ```
  - Opcional: inicializar un repositorio limpio si se quiere historial fresco:
    ```bash
    # Solo si se decide partir de cero en git
    rm -rf .git
    git init
    git add .
    git commit -m "feat: initial HER PoC from rag-estimation-service"
    ```

- [ ] **ENV-00b** Crear la carpeta `issues/` para el workflow local
  - Esta carpeta reemplaza GitHub Issues como fuente de verdad para el trabajo
  - El `project-coordinator` leerá ficheros de aquí en lugar de usar `gh` CLI
  - Crear el fichero plantilla `issues/TEMPLATE.md`:
    ```markdown
    # Issue {id}: {title}

    ## Description
    [Qué hay que construir o corregir]

    ## Acceptance Criteria
    [Cómo se ve el done]

    ## Notes
    [Contexto opcional, restricciones, referencias a docs/issues.md]
    ```
  - Ejemplo de primer issue real: `issues/001-epic0-setup.md`

- [ ] **ENV-01** Renombrar el proyecto en `pyproject.toml`
  - `name = "her-poc"`, `description = "HER - Conversational Intelligence PoC"`
  - `requires-python = ">=3.11"`

- [ ] **ENV-02** Actualizar dependencias en `pyproject.toml`
  - Eliminar: `openai`, `tiktoken`
  - Añadir: `google-genai>=2.3.0`, `google-cloud-speech>=2.28`, `google-cloud-texttospeech>=2.20`, `python-multipart>=0.0.9`
  - Mantener: `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `sqlalchemy[asyncio]`, `asyncpg`, `pgvector`, `alembic`, `structlog`, `httpx`

- [ ] **ENV-03** Crear entorno virtual Python 3.11+
  ```bash
  python3.11 -m venv .venv
  source .venv/bin/activate
  pip install -e ".[dev]"
  ```

- [ ] **ENV-04** Actualizar `.env.example` con las nuevas variables
  ```dotenv
  # Base de datos
  DATABASE_URL=postgresql+asyncpg://dev:dev@localhost:5432/her_poc
  DATABASE_SCHEMA=her

  # Servicio
  ENVIRONMENT=development
  LOG_LEVEL=DEBUG

  # Gemini (Developer API — local)
  GEMINI_API_KEY=your-gemini-api-key-here

  # Google Cloud (STT + TTS)
  GOOGLE_CLOUD_PROJECT=your-gcp-project-id
  GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

  # Embeddings
  EMBEDDING_MODEL=text-multilingual-embedding-002
  EMBEDDING_DIMENSIONS=768

  # LLM
  LLM_MODEL=gemini-2.5-flash
  LLM_MAX_OUTPUT_TOKENS=8192

  # Speech
  STT_LANGUAGE_CODE=es-ES
  TTS_LANGUAGE_CODE=es-ES
  TTS_VOICE_NAME=es-ES-Neural2-A
  ```

- [ ] **ENV-05** Actualizar `docker-compose.yml` para el nuevo proyecto
  - Renombrar DB: `estimations` → `her_poc`
  - Renombrar servicio: `rag-service` → `her-api`
  - Mantener imagen `pgvector/pgvector:pg16`
  - Montar volumen `pgdata_her` para no colisionar con datos legacy

- [ ] **ENV-06** Verificar que `pgvector` arranca correctamente
  ```bash
  docker compose up postgres -d
  docker exec -it <container> psql -U dev -d her_poc -c "CREATE EXTENSION IF NOT EXISTS vector;"
  ```

- [ ] **ENV-07** Crear el schema `her` en Alembic
  - Actualizar `alembic/env.py` para usar `DATABASE_SCHEMA=her`
  - Las migraciones 001–005 (schema `rag`) quedan archivadas sin ejecutarse; el punto de partida limpio es la migración 006

---

## Epic 1 — Migración del Núcleo RAG a Gemini

**Descripción:** Sustituir todas las dependencias de OpenAI por el nuevo SDK `google-genai`. Adaptar la capa de configuración y ajustar la dimensión de los vectores de 1536 → 768. Limpiar el código de estimación que ya no se usa.

### Tareas

- [ ] **RAG-01** Actualizar `app/config.py`
  - Eliminar: `OPENAI_API_KEY`, `EMBEDDING_MODEL` (valor openai), `LLM_MODEL` (valor o4-mini), `TASK_VALIDATION_*`
  - Añadir: `GEMINI_API_KEY`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS`, `STT_LANGUAGE_CODE`, `TTS_LANGUAGE_CODE`, `TTS_VOICE_NAME`
  - Cambiar: `EMBEDDING_DIMENSIONS = 768`, `LLM_MODEL = "gemini-2.5-flash"`, `DATABASE_SCHEMA = "her"`

- [ ] **RAG-02** Reescribir `app/core/embeddings.py` para `google-genai`
  - Inicializar `genai.Client(api_key=settings.GEMINI_API_KEY)`
  - Usar `client.models.embed_content(model="text-multilingual-embedding-002", ...)`
  - `task_type="RETRIEVAL_DOCUMENT"` para indexar, `task_type="RETRIEVAL_QUERY"` para consultas
  - Mantener la firma pública: `async def embed_text(text: str) -> list[float]`
  - Mantener soporte de batch: `async def embed_texts(texts: list[str]) -> list[list[float]]`

- [ ] **RAG-03** Reescribir `app/core/generation.py` para `google-genai`
  - Inicializar `genai.Client(api_key=settings.GEMINI_API_KEY)`
  - Usar `client.models.generate_content(model="gemini-2.5-flash", contents=..., config=types.GenerateContentConfig(...))`
  - Mantener firma: `async def generate(prompt: str, system_instruction: str | None = None) -> str`
  - Configurar `max_output_tokens`, `temperature` desde settings

- [ ] **RAG-04** Adaptar `app/core/retrieval.py`
  - Cambiar dimensión del vector en las queries de 1536 → 768
  - Eliminar lógica de filtrado por `chunk_type` de quotes (scope_block, line_item, phase, etc.)
  - Simplificar: búsqueda por similitud coseno + filtro opcional por `employee_id` o rango de fechas

- [ ] **RAG-05** Eliminar módulos legacy de estimación
  - Borrar: `app/core/chunking.py`, `app/core/ranking.py`, `app/core/quote_generation_pipeline.py`, `app/core/query_preprocessing.py`, `app/core/reasoning_service.py`, `app/core/prompt_builder.py`
  - Borrar: `app/api/v1/estimate.py`, `app/api/v1/quote_generator.py`, `app/api/v1/ingest.py`, `app/api/v1/stats.py`
  - Actualizar `app/api/v1/router.py` eliminando las rutas borradas

---

## Epic 2 — Modelos de Datos y Migraciones

**Descripción:** Definir el nuevo modelo de datos para el proyecto HER. Tres tablas principales: empleados, sesiones de check-in y los chunks vectorizados de cada sesión. El índice HNSW se crea sobre vectores de 768 dimensiones (Gemini).

### Tareas

- [ ] **DB-01** Crear modelo `app/models/employee.py`
  ```python
  # Schema: her
  # Columnas: id (UUID PK), name (str), created_at (timestamp)
  ```

- [ ] **DB-02** Crear modelo `app/models/checkin.py`
  ```python
  # Schema: her
  # Columnas:
  #   id (UUID PK)
  #   employee_id (FK → employees.id)
  #   session_id (str, único — token de sesión para la API stateless)
  #   status: "in_progress" | "completed"
  #   started_at (timestamp)
  #   completed_at (timestamp, nullable)
  ```

- [ ] **DB-03** Crear modelo `app/models/checkin_chunk.py`
  ```python
  # Schema: her
  # Columnas:
  #   id (UUID PK)
  #   checkin_id (FK → check_ins.id)
  #   question_index (int: 0=nombre, 1=hoy, 2=bloqueos, 3=mañana)
  #   question_text (str)
  #   answer_text (str)
  #   embedding (Vector(768))
  #   created_at (timestamp)
  ```

- [ ] **DB-04** Crear migración `006_create_her_schema.py`
  - `CREATE SCHEMA IF NOT EXISTS her`
  - `CREATE EXTENSION IF NOT EXISTS vector`

- [ ] **DB-05** Crear migración `007_create_employees.py`
  - Tabla `her.employees`

- [ ] **DB-06** Crear migración `008_create_checkins.py`
  - Tabla `her.check_ins`
  - Índice en `session_id`, `employee_id`

- [ ] **DB-07** Crear migración `009_create_checkin_chunks.py`
  - Tabla `her.check_in_chunks`
  - Índice HNSW: `CREATE INDEX ON her.check_in_chunks USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=200)`
  - Índice en `checkin_id`

- [ ] **DB-08** Verificar el ciclo completo de migraciones
  ```bash
  alembic upgrade head
  alembic current  # debe mostrar 009
  ```

---

## Epic 3 — Servicio de Voz (STT / TTS)

**Descripción:** Integrar Google Cloud Speech-to-Text v2 para transcripción de audio y Google Cloud Text-to-Speech para síntesis de voz. Exponer ambos como endpoints HTTP que el frontend consume directamente.

### Tareas

- [ ] **SPEECH-01** Crear `app/core/speech.py` — cliente STT
  - Usar `google.cloud.speech_v2.SpeechClient`
  - Método: `async def transcribe(audio_bytes: bytes, language_code: str) -> str`
  - Configurar `RecognitionConfig` con `auto_decoding_config` (acepta webm/ogg del navegador)
  - Recognizer inline: `projects/{project}/locations/global/recognizers/_`
  - Model: `"chirp_2"` (mejor calidad para español, disponible en `global`)

- [ ] **SPEECH-02** Crear `app/core/tts.py` — cliente TTS
  - Usar `google.cloud.texttospeech.TextToSpeechClient`
  - Método: `async def synthesize(text: str, language_code: str, voice_name: str) -> bytes`
  - Encoding: `MP3` (compatible con `<audio>` HTML nativo)
  - Voice tier: `Neural2` (calidad/coste equilibrado para PoC)

- [ ] **SPEECH-03** Crear endpoint `POST /api/v1/speech/transcribe`
  - Recibe: `multipart/form-data` con campo `audio` (archivo de audio, ≤ 60s)
  - Devuelve: `{ "transcript": "texto transcrito", "confidence": 0.95 }`

- [ ] **SPEECH-04** Crear endpoint `POST /api/v1/speech/synthesize`
  - Recibe: `{ "text": "...", "language_code": "es-ES" }`
  - Devuelve: respuesta con `Content-Type: audio/mpeg` (bytes MP3 directos)
  - El frontend hace `new Audio(URL.createObjectURL(blob)).play()`

- [ ] **SPEECH-05** Manejo de credenciales
  - En local: `GOOGLE_APPLICATION_CREDENTIALS` apunta a un service account JSON
  - Documentar los permisos necesarios: `roles/speech.client`, `roles/texttospeech.client`
  - Añadir instrucciones en `README.md` para crear el service account

---

## Epic 4 — Flujo de Check-in del Empleado

**Descripción:** El empleado inicia una sesión, el agente conduce 4 turnos de conversación (presentación + 3 preguntas), y al finalizar se vectorizan y persisten todas las respuestas. El estado de sesión es gestionado por la API (stateless por token de sesión).

### Preguntas fijas del agente

| Index | Pregunta |
|-------|----------|
| 0 | *(presentación)* "¡Hola! Soy HER, tu asistente de check-in. ¿Cómo te llamas?" |
| 1 | "¿En qué trabajaste hoy, {nombre}?" |
| 2 | "¿Tuviste algún bloqueo o necesitas ayuda con algo?" |
| 3 | "¿Qué planeas hacer mañana?" |

### Tareas

- [ ] **CHECKIN-01** Crear `app/core/checkin_flow.py`
  - Clase `CheckInSession` con el estado: `session_id`, `employee_name`, `current_question_index`, respuestas acumuladas
  - Método `get_next_question(name: str | None) -> str` — devuelve la pregunta textual interpolada
  - Método `is_complete() -> bool` — True cuando `question_index == 4`

- [ ] **CHECKIN-02** Crear `app/services/checkin_service.py`
  - `create_session() -> CheckIn` — genera `session_id` (UUID), persiste en DB con status `in_progress`
  - `process_answer(session_id, answer_text) -> str | None` — guarda respuesta, devuelve siguiente pregunta o None si completo
  - `complete_session(session_id)` — genera embeddings de todos los chunks, persiste `CheckInChunk` para cada par (pregunta, respuesta), marca `status = "completed"`

- [ ] **CHECKIN-03** Crear endpoint `POST /api/v1/checkin/start`
  - Request: `{}` (sin body)
  - Response: `{ "session_id": "uuid", "question_text": "...", "question_audio_url": "/api/v1/speech/synthesize" }`
  - Nota: el audio de la primera pregunta se sintetiza y devuelve como referencia; el frontend lo reproduce

- [ ] **CHECKIN-04** Crear endpoint `POST /api/v1/checkin/{session_id}/answer`
  - Request: `{ "answer_text": "..." }` (el frontend ya transcribió el audio antes de llamar a este endpoint)
  - Response: `{ "next_question_text": "...", "is_complete": false }` o `{ "is_complete": true, "employee_name": "..." }`
  - Si `is_complete == true`: disparar `complete_session()` asíncronamente (o await, depende de tiempos)

- [ ] **CHECKIN-05** Crear endpoint `GET /api/v1/checkin/{session_id}/status`
  - Response: `{ "session_id": "...", "status": "in_progress|completed", "employee_name": "...", "questions_answered": 2 }`

---

## Epic 5 — Consulta del CEO (RAG)

**Descripción:** El CEO formula una pregunta en lenguaje natural. El sistema vectoriza la pregunta, recupera los chunks de check-in más relevantes, y Gemini 2.5 Flash sintetiza un resumen conversacional de ~30 segundos de lectura (~80 palabras) que también se entrega como audio TTS.

### Tareas

- [ ] **CEO-01** Crear `app/core/ceo_query.py`
  - Método `async def query(question: str) -> str`
  - Pipeline: embed pregunta (task_type=RETRIEVAL_QUERY) → búsqueda semántica en `check_in_chunks` (top_k=8, min_similarity=0.4) → construir contexto con los chunks recuperados → prompt a Gemini 2.5 Flash → devolver resumen

- [ ] **CEO-02** Diseñar el prompt del CEO
  ```
  Eres HER, asistente de inteligencia operacional para la dirección de AlmaWolf.
  Basándote SOLO en los siguientes reportes de empleados, responde la pregunta del CEO
  en un resumen directo y conversacional de máximo 80 palabras.
  Si no hay información suficiente, dilo con claridad.

  REPORTES:
  {contexto_recuperado}

  PREGUNTA: {pregunta_ceo}
  ```

- [ ] **CEO-03** Crear endpoint `POST /api/v1/ceo/query`
  - Request: `{ "question": "¿En qué está trabajando el equipo de Sagitaz?" }`
  - Response: `{ "answer": "...", "sources": [{ "employee_name": "...", "date": "...", "excerpt": "..." }] }`
  - Incluir `sources` para transparencia (qué check-ins se usaron)

- [ ] **CEO-04** Crear endpoint `GET /api/v1/ceo/summary`
  - Sin parámetros: devuelve un briefing automático de los check-ins de las últimas 24h
  - Gemini genera el resumen sin pregunta específica: "¿Qué pasó hoy en el equipo?"
  - Response: `{ "summary": "...", "checkins_count": 5, "period": "2026-05-16" }`

- [ ] **CEO-05** Garantizar respuesta con audio TTS
  - Ambos endpoints (`/query` y `/summary`) aceptan header `Accept: audio/mpeg`
  - Si presente, devuelven el audio sintetizado en lugar de JSON
  - Alternativa más simple para el PoC: el frontend llama a `/speech/synthesize` con el texto recibido

---

## Epic 6 — Frontend Web (Adaptador Primario Hexagonal)

**Descripción:** Interfaz HTML/JS vanilla ubicada en `adapters/primary/web/` — adaptador primario en arquitectura hexagonal. Selector de rol en landing, vista empleado con voz, vista CEO con consulta voz/texto. Design system extraído del frontend legacy.

**Issues hijas:** `006-01`, `006-02`, `006-03`

### Estructura objetivo

```
adapters/
└── primary/
    └── web/
        ├── index.html
        ├── employee.html
        ├── ceo.html
        ├── style.css        ← design tokens del legacy
        └── js/
            ├── employee.js
            └── ceo.js
```

### Tareas

- [ ] **006-01** Actualizar docs y agentes al path `adapters/primary/web/`

- [ ] **006-02** Extraer design system del legacy → `adapters/primary/web/style.css`
  - Variables CSS: colores HSL, tipografía Inter + JetBrains Mono, radius
  - Utilities: `.glow-sm`, `.glow-md`, `.glass`, `.animate-fade-in-up`, `.stagger-children`
  - Source: `rag-estimation-platform/config/tailwind.config.js` + `application.tailwind.css`

- [ ] **006-03** Crear estructura base HTML + JS (depende de `006-02`)

- [ ] **FE-01** Configurar `StaticFiles` en `app/main.py`
  - `app.mount("/", StaticFiles(directory="adapters/primary/web", html=True), name="web")`

- [ ] **FE-02** Crear `adapters/primary/web/index.html` — Landing con selector de rol

- [ ] **FE-03** Crear `adapters/primary/web/employee.html` — Vista de check-in
  - Indicador de progreso: 1/3, 2/3, 3/3
  - Botón de grabación (MediaRecorder API, `audio/webm;codecs=opus`)
  - STT → transcripción → envío a check-in API

- [ ] **FE-04** Crear `adapters/primary/web/ceo.html` — Vista CEO
  - Input texto + grabación, respuesta + TTS, fuentes colapsables, briefing del día

- [ ] **FE-05** Manejo de errores
  - Fallback texto si MediaRecorder no disponible
  - Toast no bloqueante si API no responde

---

## Epic 7 — Limpieza del Repositorio Legacy

**Descripción:** Eliminar todo el código de generación de presupuestos que ya no tiene lugar en el nuevo proyecto. Dejar el repositorio limpio y coherente con el nuevo dominio.

### Tareas

- [ ] **CLEAN-01** Archivar/eliminar módulos de estimación
  - Borrar: `app/core/chunking.py`, `app/core/ranking.py`, `app/core/quote_generation_pipeline.py`
  - Borrar: `app/core/query_preprocessing.py`, `app/core/reasoning_service.py`, `app/core/prompt_builder.py`
  - Borrar: `app/api/v1/estimate.py`, `app/api/v1/quote_generator.py`, `app/api/v1/ingest.py`, `app/api/v1/stats.py`

- [ ] **CLEAN-02** Eliminar modelos de datos legacy
  - Borrar: `app/models/document.py`, `app/models/ingestion_log.py`, `app/models/search_log.py`
  - Borrar: `app/models/chunk.py` (sustituido por `checkin_chunk.py`)

- [ ] **CLEAN-03** Eliminar datos de ejemplo legacy
  - Borrar directorio `estimation_samples/`
  - Borrar directorio `transcriptions/` (si no se reutiliza para pruebas del nuevo flujo)

- [ ] **CLEAN-04** Actualizar `app/api/v1/router.py`
  - Dejar solo: `health`, `checkin`, `ceo`, `speech`

- [ ] **CLEAN-05** Actualizar `app/main.py`
  - Limpiar imports obsoletos
  - Actualizar título/descripción de la app FastAPI: `"HER — Conversational Intelligence API"`

- [ ] **CLEAN-06** Actualizar `README.md`
  - Documentar el nuevo propósito, el setup del entorno y cómo levantar el proyecto
  - Incluir instrucciones para el service account de GCP

---

## Paralelización entre Epics

| Epic | Paralelo con | Espera a |
|------|-------------|---------|
| Epic 0 — Setup | — | — |
| Epic 1 — Migración Gemini | — | Epic 0 |
| Epic 2 — Modelos DB | — | Epic 1 |
| Epic 3 — Speech STT/TTS | Epic 4, Epic 5, Epic 7 | Epic 2 |
| Epic 4 — Check-in | Epic 3, Epic 5, Epic 7 | Epic 2 |
| Epic 5 — CEO Query | Epic 3, Epic 4, Epic 7 | Epic 2 |
| Epic 6 — Frontend | Epic 7 | Epics 3 + 4 + 5 |
| Epic 7 — Limpieza | Epics 3, 4, 5, 6 | Epic 1 |

> Los worktrees paralelos posibles: **3 + 4 + 7** simultáneos tras Epic 2, luego **5 + 7** si aún no terminó, finalmente **6** cuando cierren 3+4+5.

## Orden de implementación sugerido para el PoC

1. **Epic 0** — Setup completo antes de escribir una línea
2. **Epic 1** — Migrar embeddings y generation a Gemini
3. **Epic 2** — Migraciones y modelos
4. **Worktrees paralelos:** Epic 3 + Epic 4 + Epic 7 simultáneos
5. **Epic 5** — Query CEO (puede solaparse con el final de 3/4)
6. **Epic 6** — Frontend (últimas horas, con backend funcional)
