# Arquitectura del Sistema RAG Estimation

> Documento de arquitectura completo y actualizado del sistema de generacion de estimaciones
> de software asistido por RAG (Retrieval-Augmented Generation).
>
> Ultima actualizacion: Marzo 2026

---

## Tabla de contenidos

1. [Vision general](#1-vision-general)
2. [Diagrama de arquitectura](#2-diagrama-de-arquitectura)
3. [Plataforma Web — Rails 8](#3-plataforma-web--rails-8)
4. [Servicio RAG — FastAPI](#4-servicio-rag--fastapi)
5. [Base de datos compartida — PostgreSQL + pgvector](#5-base-de-datos-compartida--postgresql--pgvector)
6. [Flujos de datos principales](#6-flujos-de-datos-principales)
7. [Comunicacion entre servicios](#7-comunicacion-entre-servicios)
8. [Infraestructura y despliegue](#8-infraestructura-y-despliegue)
9. [Integraciones externas](#9-integraciones-externas)

---

## 1. Vision general

El sistema **RAG Estimation** permite generar estimaciones de esfuerzo, coste y planificacion
para proyectos de software a partir de transcripciones de reuniones y notas. Utiliza
Retrieval-Augmented Generation (RAG) sobre un corpus de presupuestos historicos vectorizados
para fundamentar las estimaciones en datos reales.

### Componentes principales

| Componente | Repositorio | Stack | Puerto |
|---|---|---|---|
| **Plataforma Web** | `rag-estimation-platform` | Rails 8.0.4, Hotwire, Tailwind CSS | 3000 |
| **Servicio RAG** | `rag-estimation-service` | Python 3.11, FastAPI, SQLAlchemy 2.0 async | 8000 |

Ambos comparten una instancia de **PostgreSQL 16 con pgvector**, cada uno en su propio schema
(`app` para Rails, `rag` para FastAPI).

### Stack tecnologico resumido

```
Plataforma Web (Rails 8)          Servicio RAG (FastAPI)
-------------------------------   --------------------------------
Ruby 3.4.4                        Python 3.11+
Rails 8.0.4                       FastAPI + Uvicorn
PostgreSQL 16                     SQLAlchemy 2.0 (asyncpg)
Hotwire (Turbo 2.0 + Stimulus)   OpenAI SDK (Responses API)
Tailwind CSS 3.3                  pgvector (Vector 1536)
Faraday 2.9                       Alembic (migraciones)
Solid Queue (jobs)                Pydantic v2 (schemas)
Propshaft (assets)                structlog (logging)
bcrypt (auth)                     o4-mini (LLM)
Pagy (paginacion)                 text-embedding-3-small (embeddings)
```

---

## 2. Diagrama de arquitectura

### Vista general del sistema

```
+------------------------------------------------------------------+
|                         USUARIO (Browser)                        |
+------------------------------------------------------------------+
          |                                          ^
          | HTTP (Turbo Drive/Frames/Streams)        | HTML + Turbo Streams
          v                                          |
+------------------------------------------------------------------+
|                  PLATAFORMA WEB (Rails 8)                        |
|                     localhost:3000                               |
|                                                                  |
|  +------------------+  +------------------+  +-----------------+ |
|  |   Controllers    |  |    Services      |  |     Jobs        | |
|  |  - Dashboard     |  | - RagService     |  | - Estimation    | |
|  |  - Estimates     |  |   Client         |  |   Job           | |
|  |  - Ingest        |  | - RagResponse    |  | - Ingestion     | |
|  |  - Documents     |  |   Parser         |  |   StatusJob     | |
|  |  - Searches      |  |                  |  |                 | |
|  +------------------+  +------------------+  +-----------------+ |
|           |                    |                     |           |
|           v                    v                     v           |
|  +------------------+  +------------------+  +-----------------+ |
|  |    Models        |  |  Turbo Streams   |  |  Solid Queue    | |
|  | - User           |  |  (broadcasts)    |  |  (async jobs)   | |
|  | - Estimation     |  |                  |  |                 | |
|  | - Document       |  |                  |  |                 | |
|  | - FunctionalBlock|  |                  |  |                 | |
|  | - Task           |  |                  |  |                 | |
|  | - Reference      |  |                  |  |                 | |
|  +------------------+  +------------------+  +-----------------+ |
+------------------------------------------------------------------+
          |                                          ^
          | REST/JSON (Faraday, 60s timeout)         | JSON Response
          v                                          |
+------------------------------------------------------------------+
|                   SERVICIO RAG/CAG (FastAPI)                     |
|                     localhost:8000                               |
|                                                                  |
|  +------------------+  +------------------+  +-----------------+ |
|  |   API Endpoints  |  |  Core Services   |  |  Pipeline       | |
|  |  - /health       |  | - Embedding      |  | - Estimation    | |
|  |  - /ingest       |  | - Retrieval      |  |   Pipeline      | |
|  |  - /search       |  | - Generation     |  | - Quote Gen     | |
|  |  - /estimate     |  | - Ranking        |  |   Pipeline      | |
|  |  - /stats        |  | - Confidence     |  |                 | |
|  |  - /generate-    |  | - Chunking       |  |                 | |
|  |     quote        |  | - Reasoning      |  |                 | |
|  +------------------+  +------------------+  +-----------------+ |
+------------------------------------------------------------------+
          |                          |
          v                          v
+--------------------+   +---------------------+
|  PostgreSQL 16     |   |      OpenAI API     |
|  + pgvector        |   |                     |
|                    |   | - text-embedding-   |
| Schema: app        |   |   3-small (1536d)   |
| Schema: rag        |   | - o4-mini (LLM)     |
| HNSW indices       |   |                     |
+--------------------+   +---------------------+
```

### Flujo de estimacion asincrono

```
Browser           Rails                Solid Queue           FastAPI           OpenAI
  |                 |                      |                    |                 |
  |-- POST /estimates (transcripciones) -->|                    |                 |
  |                 |-- enqueue ---------->|                    |                 |
  |<-- 302 redirect |  EstimationJob       |                    |                 |
  |                 |                      |                    |                 |
  |-- GET /estimates/:id ----------------->|                    |                 |
  |<-- HTML (status: processing) ----------|                    |                 |
  |                 |                      |                    |                 |
  |                 |                      |-- POST /estimate ->|                 |
  |                 |                      |                    |-- embed ------->|
  |                 |                      |                    |<-- vector ------|
  |                 |                      |                    |                 |
  |                 |                      |                    |-- HNSW search   |
  |                 |                      |                    |   (pgvector)    |
  |                 |                      |                    |                 |
  |                 |                      |                    |-- generate ---->|
  |                 |                      |                    |<-- estimation --|
  |                 |                      |<-- JSON response --|                 |
  |                 |                      |                    |                 |
  |                 |<-- Turbo Stream -----|                    |                 |
  |<== broadcast (replace estimation_content) ==================|                 |
  |    (status: structuring, blocks + tareas visibles)          |                 |
```

---

## 3. Plataforma Web — Rails 8

### 3.1 Stack

| Tecnologia | Version | Uso |
|---|---|---|
| Ruby | 3.4.4 | Runtime |
| Rails | 8.0.4 | Framework web |
| PostgreSQL | 16 | Base de datos principal |
| Turbo | 2.0.23 | Navegacion SPA y actualizaciones en tiempo real |
| Stimulus | 1.3.4 | Controladores JavaScript ligeros |
| Tailwind CSS | 3.3.2 | Framework CSS utility-first |
| Faraday | 2.9+ | Cliente HTTP para el servicio RAG |
| Solid Queue | — | Cola de jobs con base de datos |
| Solid Cache | — | Cache con base de datos |
| Solid Cable | — | ActionCable con base de datos |
| Propshaft | — | Asset pipeline |
| Importmap | 2.2.3 | ES modules sin bundler |
| Pagy | ~9.0 | Paginacion |
| bcrypt | 3.1.7 | Hash de passwords |
| Kamal | 2.10.1 | Deployment |

### 3.2 Modelos

```
User
 |-- has_many :documents
 |-- has_many :estimations
 |
 |-- email (string, unique, NOT NULL)
 |-- name (string, NOT NULL)
 |-- password_digest (string, NOT NULL)

Document
 |-- belongs_to :user
 |-- has_one :chunks_breakdown
 |
 |-- external_document_id (uuid, unique) --> referencia al servicio RAG
 |-- title (string, NOT NULL)
 |-- description (text)
 |-- status (string: pending | processing | completed | failed)
 |-- chunks_count (integer, default: 0)
 |-- budget (decimal 12,2)
 |-- currency (string, default: 'EUR')
 |-- technologies (jsonb, default: [])
 |-- duration (string)
 |-- raw_json (text)
 |-- ingested_at (timestamp)

ChunksBreakdown
 |-- belongs_to :document
 |
 |-- project_overview (integer)
 |-- scope_block (integer)
 |-- line_item (integer)
 |-- phase (integer)
 |-- team_conditions (integer)

Estimation
 |-- belongs_to :user
 |-- has_many :functional_blocks (ordered by position)
 |-- has_many :tasks (through functional_blocks)
 |-- has_many :references
 |
 |-- title (string, NOT NULL)
 |-- description (text)
 |-- status (string: draft | processing | structuring | completed | failed)
 |-- global_rate (decimal 10,2, default: 150.0)
 |-- currency (string: EUR | USD | GBP)
 |-- confidence_score (float, 0..1)
 |-- confidence_level (string)
 |-- technologies (jsonb, default: [])
 |-- total_hours_optimistic / expected / pessimistic (decimal 10,2)
 |-- total_cost_optimistic / expected / pessimistic (decimal 12,2)
 |-- raw_transcriptions (jsonb, default: [])
 |-- error_message (text)

FunctionalBlock
 |-- belongs_to :estimation
 |-- has_many :tasks (ordered by position)
 |
 |-- name (string, NOT NULL)
 |-- position (integer, default: 0)

Task
 |-- belongs_to :functional_block
 |
 |-- name (string, NOT NULL)
 |-- hours_optimistic / expected / pessimistic (decimal 8,2)
 |-- rate (decimal 10,2, nullable) --> si null usa estimation.global_rate
 |-- position (integer, default: 0)

Reference
 |-- belongs_to :estimation
 |
 |-- title (string)
 |-- similarity_score (float, 0..1)
 |-- cost (decimal 12,2)
 |-- technologies (jsonb, default: [])
 |-- chunk_id (uuid) --> referencia al chunk del servicio RAG
 |-- chunk_type (string)
 |-- content_preview (text)
 |-- currency (string, default: 'EUR')
```

### 3.3 Controladores

| Controlador | Acciones | Responsabilidad |
|---|---|---|
| `ApplicationController` | — | Base: autenticacion, paginacion, manejo de RecordNotFound |
| `PagesController` | `landing` | Pagina publica de inicio (layout: public) |
| `SessionsController` | `new`, `create`, `destroy` | Login / Logout (bcrypt + session) |
| `RegistrationsController` | `new`, `create` | Registro de usuarios |
| `DashboardController` | `index` | Metricas: documentos, chunks, health del RAG, estadisticas |
| `IngestController` | `index`, `create` | Subida de JSON → ingesta al servicio RAG |
| `DocumentsController` | `index`, `show`, `destroy` | CRUD de documentos con paginacion y busqueda |
| `EstimatesController` | `index`, `new`, `create`, `show`, `retry_estimation`, `update_structure`, `update_estimation` | Flujo completo de estimaciones: crear, procesar, estructurar, editar |
| `EstimationsController` | `index`, `edit`, `update`, `destroy` | Gestion y edicion avanzada de estimaciones |
| `SearchesController` | `index` | Busqueda semantica con filtros por chunk_type |

### 3.4 Concerns

| Concern | Incluido en | Funcionalidad |
|---|---|---|
| `Authentication` | `ApplicationController` | `current_user`, `logged_in?`, `authenticate_user!` via `session[:user_id]` |
| `RagErrorHandling` | `EstimatesController`, `SearchesController` | Rescue de `ServiceUnavailableError`, `TimeoutError`, `Error` del RAG con mensajes i18n (ES) |
| `EstimationCalculations` | `EstimatesController`, `EstimationsController` | `recalculate_totals!`: calcula las 6 variantes de horas/coste desde bloques y tareas |

### 3.5 Servicios

#### RagServiceClient

Cliente HTTP basado en Faraday para comunicarse con el servicio RAG.

```
Configuracion:
  - base_url: ENV["RAG_SERVICE_BASE_URL"] || "http://localhost:8000"
  - timeout: 60 segundos
  - open_timeout: 10 segundos
  - middleware: request JSON, response JSON, logger (dev)

Metodos publicos:
  health()                                    GET  /api/v1/health
  ingest(quote_payload)                       POST /api/v1/ingest
  ingest_status(document_id)                  GET  /api/v1/ingest/{id}/status
  delete_document(document_id)                DELETE /api/v1/ingest/{id}
  search(query:, filters:, top_k:, min_sim:)  POST /api/v1/search
  estimate(query:, context:, options:)        POST /api/v1/estimate
  estimate_batch(queries:, context:, opts:)   POST /api/v1/estimate/batch
  stats()                                     GET  /api/v1/stats

Excepciones:
  RagServiceClient::Error                (base)
  RagServiceClient::TimeoutError         (Faraday::TimeoutError)
  RagServiceClient::ServiceUnavailableError (503 / ConnectionFailed)
  RagServiceClient::NotFoundError        (404)
```

#### RagResponseParser

Parsea las respuestas JSON del servicio RAG a estructuras que Rails puede persistir.

```
Metodos estaticos:
  parse_ingest(response)        -> { external_document_id, status }
  parse_ingest_status(response) -> { document: {status, chunks_count}, breakdown: {...} }
  parse_search(response)        -> { results[], total, processing_time_ms, ... }
  parse_estimate(response, est) -> { estimation: {...}, blocks: [...], references: [...] }
```

El metodo `parse_estimate` transforma la respuesta del LLM en:
- Datos de la estimacion (horas, costes, confianza, tecnologias)
- Bloques funcionales con tareas anidadas (calcula horas optimista/pesimista desde ratios)
- Referencias con scores de similitud

### 3.6 Background Jobs

#### EstimationJob

Procesa estimaciones de forma asincrona tras el envio de transcripciones.

```
Cola: default
Reintentos:
  - TimeoutError: 3 intentos, espera 10s
  - ServiceUnavailableError: 3 intentos, espera 15s
  - RecordNotFound: descarta

Flujo:
  1. Concatena raw_transcriptions en query string
  2. Valida longitud minima (10 chars)
  3. Llama a RAG estimate(query, options: {currency})
  4. Parsea respuesta con RagResponseParser
  5. Actualiza Estimation (status: "structuring") con datos parseados
  6. Crea FunctionalBlocks con Tasks anidados
  7. Crea References
  8. Broadcast via Turbo Stream:
     - Reemplaza estimation_{id}_content
     - Reemplaza estimation_{id}_stepper
```

#### IngestionStatusJob

Monitorea el progreso de ingesta de documentos con polling.

```
Cola: default
Reintentos:
  - NotFoundError: descarta (marca documento como failed)
  - TimeoutError: 5 intentos, espera 10s
  - Error: 3 intentos, espera 15s

Flujo:
  1. Consulta RAG ingest_status(external_document_id)
  2. Actualiza Document (status, chunks_count)
  3. Si status == "completed": crea ChunksBreakdown, set ingested_at
  4. Si status == "processing": re-encola con delay de 5 segundos
  5. Broadcast via Turbo Stream:
     - Reemplaza document_{id} row
```

### 3.7 Frontend: Stimulus Controllers

14 controladores JavaScript gestionan la interactividad del lado del cliente:

| Controlador | Responsabilidad |
|---|---|
| `sidebar_controller` | Colapsar/expandir sidebar, soporte movil, persistencia en localStorage |
| `cost_calculator_controller` | Calculos en tiempo real de horas y costes en formularios de estimacion |
| `nested_form_controller` | Gestion dinamica de formularios anidados (bloques + tareas) |
| `transcription_controller` | Lista de transcripciones: agregar, eliminar, upload de archivos |
| `file_upload_controller` | Drag-and-drop de archivos JSON con preview en textarea |
| `collapsible_controller` | Secciones colapsables con iconos animados |
| `search_filter_controller` | Filtros de busqueda por tipo de chunk con toggle visual |
| `estimate_type_controller` | Alternar entre vistas optimista / esperada / pesimista |
| `auto_dismiss_controller` | Auto-cierre de flash messages (default 5s) |
| `password_toggle_controller` | Mostrar/ocultar password en inputs |
| `hello_controller` | Placeholder de Stimulus |
| `application.js` | Configuracion principal de Stimulus |
| `index.js` | Registro de controladores |

### 3.8 Rutas principales

```
Autenticacion:
  GET/POST    /login                       sessions#new/create
  DELETE      /logout                      sessions#destroy
  GET/POST    /register                    registrations#new/create

Dashboard:
  GET         /dashboard                   dashboard#index

Ingesta:
  GET         /ingest                      ingest#index
  POST        /ingest                      ingest#create

Estimaciones (flujo):
  GET         /estimate                    estimates#index
  GET/POST    /estimates/new               estimates#new/create
  GET         /estimates/:id               estimates#show
  POST        /estimates/:id/retry         estimates#retry_estimation
  PATCH       /estimates/:id/structure     estimates#update_structure
  PATCH       /estimates/:id/estimation    estimates#update_estimation

Estimaciones (CRUD):
  GET         /estimaciones                estimations#index
  GET         /estimaciones/:id/edit       estimations#edit
  PATCH       /estimaciones/:id            estimations#update
  DELETE      /estimaciones/:id            estimations#destroy

Documentos:
  GET         /documents                   documents#index
  GET         /documents/:id               documents#show
  DELETE      /documents/:id               documents#destroy

Busqueda:
  GET         /search                      searches#index

Landing:
  GET         /                            pages#landing
```

---

## 4. Servicio RAG — FastAPI

### 4.1 Stack

| Tecnologia | Version / Detalle | Uso                                   |
|------------|-------------------|---------------------------------------|
| Python.    | 3.11+             | Runtime                               |
| FastAPI    | —                 | Framework API asincrono               |
| Uvicorn    | —                 | Servidor ASGI                         |
| SQLAlchemy | 2.0 (async)       | ORM con asyncpg                       |
| asyncpg    | —                 | Driver PostgreSQL asincrono           |
| pgvector   | —                 | Extension de vectores para PostgreSQL |
| OpenAI SDK | —                 | Embeddings y generacion LLM           | 
| Pydantic   | v2                | Validacion de schemas                 |
| Alembic    | —                 | Migraciones de base de datos          |
| structlog  | —                 | Logging estructurado                  |

### 4.2 Estructura del proyecto

```
app/
+-- main.py                          # App factory y lifespan
+-- config.py                        # Settings (Pydantic BaseSettings)
+-- db.py                            # Engine async SQLAlchemy
+-- dependencies.py                  # Inyeccion de dependencias FastAPI
+-- api/
|   +-- v1/
|   |   +-- router.py               # Agregador de rutas
|   |   +-- health.py               # Health check
|   |   +-- ingest.py               # Ingesta de presupuestos
|   |   +-- search.py               # Busqueda semantica
|   |   +-- estimate.py             # Estimaciones (single + batch)
|   |   +-- stats.py                # Estadisticas del sistema
|   |   +-- quote_generator.py      # Generacion de presupuestos
|   +-- schemas/                     # DTOs Pydantic
|       +-- estimate_request.py
|       +-- estimate_response.py
|       +-- search_request.py
|       +-- search_response.py
|       +-- quote_input.py          # Schema de ingesta
|       +-- quote_output.py         # Schema de presupuesto generado
|       +-- quote_generation.py     # Request/response generacion
|       +-- transcription_analysis.py
|       +-- common.py
+-- core/                            # Logica de negocio
|   +-- embeddings.py               # Servicio de embeddings OpenAI
|   +-- retrieval.py                # Busqueda vectorial + re-ranking
|   +-- ranking.py                  # Algoritmo de re-ranking
|   +-- confidence.py               # Calculo de confianza
|   +-- generation.py               # Generacion LLM (estimaciones)
|   +-- pipeline.py                 # Pipeline de estimacion
|   +-- chunking.py                 # Conversion presupuesto → chunks
|   +-- anonymization.py            # Anonimizacion de PII
|   +-- query_preprocessing.py      # Normalizacion y deteccion de tech
|   +-- prompt_builder.py           # Prompts para estimaciones
|   +-- response_parser.py          # Parseo de respuestas LLM
|   +-- reasoning_service.py        # OpenAI Structured Output (o4-mini)
|   +-- quote_generation_pipeline.py # Pipeline de generacion de presupuestos
|   +-- quote_prompt_builder.py     # Prompts para generacion de presupuestos
+-- models/                          # SQLAlchemy ORM
|   +-- base.py                     # Modelo base (UUID + timestamps)
|   +-- document.py
|   +-- chunk.py                    # Incluye Vector(1536)
|   +-- ingestion_log.py
|   +-- search_log.py
+-- services/
|   +-- ingest_service.py           # Orquestacion de ingesta
+-- utils/
    +-- logging.py                  # Configuracion structlog
    +-- text_processing.py          # Utilidades de texto
```

### 4.3 Endpoints

Todos los endpoints usan el prefijo `/api/v1`.

| Metodo   | Path       | Descripcion |
|----------|------------|---|
| `GET`    | `/health`   | Estado del servicio, version, conectividad DB y pgvector |
| `POST`   | `/ingest`   | Ingestar un presupuesto JSON (chunking + embedding) |
| `GET`    | `/ingest/{document_id}/status` | Estado de ingesta de un documento |
| `DELETE` | `/ingest/{document_id}` | Eliminar documento y sus chunks |
| `POST`   | `/search`   | Busqueda semantica vectorial con filtros |
| `POST`   | `/estimate` | Estimacion individual a partir de query |
| `POST`   | `/estimate/batch` | Estimacion por lotes (hasta 20 queries) |
| `GET`    | `/stats` | Estadisticas: documentos, chunks, metricas de busqueda |
| `POST`   | `/generate-quote` | Generar presupuesto completo desde transcripcion (3 pasos) |

### 4.4 Core Services

#### EmbeddingService

Genera embeddings vectoriales via la API de OpenAI.

```
Modelo:   text-embedding-3-small
Dims:     1536
Metodos:  generate_embeddings(texts[]) -> list[list[float]]
          generate_single_embedding(text) -> list[float]
```

#### RetrievalService

Ejecuta busqueda semantica con re-ranking compuesto.

```
Flujo:
  1. Preprocesar query (expandir abreviaturas, detectar tecnologias)
  2. Generar embedding del query
  3. Busqueda HNSW en pgvector (cosine distance)
  4. Re-ranking con scoring compuesto (4 factores)
  5. Deduplicacion por (document_id, chunk_type)
  6. Registro en search_logs

Configuracion:
  top_k:            10 (default), max 50
  min_similarity:   0.6 (default)
  HNSW ef_search:   100
```

#### GenerationService

Genera estimaciones usando el LLM de OpenAI.

```
Modelo:            o4-mini (OpenAI Responses API)
Max tokens:        16384
Timeout:           120 segundos
API:               client.responses.create(instructions, input)
Reintentos:        Rate limits: 3x (2s, 4s, 8s)
                   Timeouts: 1x
                   Server errors: 2x
Fallback:          Estimacion estadistica desde chunks si el LLM falla
```

#### ReasoningService

Servicio de razonamiento con Structured Output de OpenAI.

```
Modelo:            o4-mini
API:               client.responses.parse(text_format=<PydanticModel>)
Timeout:           120 segundos

Metodos:
  analyze_transcription(text, context) -> TranscriptionAnalysis
  generate_quote(analysis, chunks, currency, context) -> QuoteOutput
```

#### EstimationPipeline

Orquesta el flujo completo de estimacion.

```
Flujo (single):
  1. Construir SearchRequest desde EstimateRequest
  2. Ejecutar retrieval.search()
  3. Validar que existen resultados (NoRelevantChunksError si no)
  4. Detectar tecnologias del query
  5. Llamar generation.generate_estimation()
  6. Calcular confidence score
  7. Construir referencias
  8. Retornar EstimateResponse

Flujo (batch):
  - Hasta 20 queries concurrentes
  - Agrega resultados con totales y confianza promedio
```

#### QuoteGenerationPipeline

Pipeline de 3 pasos para generar presupuestos completos.

```
Paso 1 - Analisis de transcripcion:
  reasoning_service.analyze_transcription()
  -> TranscriptionAnalysis (titulo, modulos, integraciones, search_queries)

Paso 2 - Busqueda RAG:
  Ejecutar 3-5 search_queries contra la base vectorial (concurrente)
  Deduplicar por chunk_id, ordenar por final_score
  Retornar top 15 chunks

Paso 3 - Generacion de presupuesto:
  reasoning_service.generate_quote(analysis, chunks, currency)
  -> QuoteOutput (scope_blocks, roadmap, items, team, condiciones)
```

### 4.5 Estrategia de chunking

Cada presupuesto ingestado se divide en 5 tipos de chunks:

| Tipo | Cantidad | Contenido | Uso |
|---|---|---|---|
| `project_overview` | 1 por presupuesto | Titulo, objetivos, tecnologias, duracion, equipo, presupuesto total | Contexto general del proyecto |
| `scope_block` | N por presupuesto | Bloque funcional: titulo, descripcion, features, tecnologias, items vinculados | Matching de requisitos funcionales |
| `line_item` | N por presupuesto | Tarea: nombre, tipo, cantidad, unidad, precio unitario, coste total, fase | Matching de tareas y costes especificos |
| `phase` | M por presupuesto | Fase: nombre, duracion, entregables, modulos, items incluidos | Matching de planificacion temporal |
| `team_conditions` | 0-1 por presupuesto | Equipo, condiciones de pago, servicios incluidos/adicionales | Matching de equipo y condiciones |

**Algoritmo de vinculacion items-bloques:**
1. Matching por fase-modulo (nombre del bloque mencionado en los modulos de la fase)
2. Matching por keywords (tokenizacion y overlap entre item y bloque)

### 4.6 Re-ranking compuesto

Scoring final con 4 factores ponderados:

```
final_score = 0.50 * similarity
            + 0.25 * tech_match
            + 0.15 * recency
            + 0.10 * cost_rangere

Donde:
  similarity  (0-1): Similitud coseno directa del vector
  tech_match  (0-1): Jaccard(tecnologias_query, tecnologias_chunk)
                      0.5 si query no tiene tecnologias (neutral)
  recency     (0-1): exp(-0.03 * edad_en_meses)
  cost_range  (0-1): Deteccion de outliers via MAD
                      1.0 normal, 0.6 outlier leve, 0.2 outlier severo
```

### 4.7 Calculo de confianza

Score de confianza multi-factor:

```
confidence = 0.35 * references_factor
           + 0.30 * similarity_factor
           + 0.20 * technology_factor
           + 0.15 * variance_factor

Factores:
  references:  0 refs -> 0.0 | 1-2 -> 0.3 | 3-5 -> 0.6 | 6-10 -> 0.8 | 10+ -> 1.0
  similarity:  max(0, (avg_similarity - 0.5) / 0.5)
  technology:  |query_techs ∩ chunk_techs| / |query_techs|
  variance:    max(0, 1.0 - coef_variacion_costes)

Niveles:
  very_low  < 0.30
  low       < 0.50
  medium    < 0.70
  high      < 0.85
  very_high >= 0.85
```

### 4.8 Configuracion

Principales variables de entorno (Pydantic BaseSettings):

```
# Base de datos
DATABASE_URL              = postgresql+asyncpg://dev:dev@localhost:5432/estimations
DATABASE_SCHEMA           = rag

# Servicio
SERVICE_HOST              = 0.0.0.0
SERVICE_PORT              = 8000
ENVIRONMENT               = development
API_KEY                   = dev-api-key

# OpenAI
OPENAI_API_KEY            = (requerido)
EMBEDDING_MODEL           = text-embedding-3-small
EMBEDDING_DIMENSIONS      = 1536
LLM_MODEL                 = o4-mini
LLM_MAX_OUTPUT_TOKENS     = 16384
LLM_TIMEOUT               = 120

# Busqueda
DEFAULT_TOP_K             = 10
DEFAULT_MIN_SIMILARITY    = 0.6
MAX_TOP_K                 = 50
HNSW_EF_SEARCH            = 100
```

---

## 5. Base de datos compartida — PostgreSQL + pgvector

Ambos servicios comparten la misma instancia de PostgreSQL 16 con pgvector,
pero usan schemas separados para aislamiento logico.

### 5.1 Schema `app` (Rails)

```
+-------------------+       +-------------------+
|      users        |       |    documents      |
+-------------------+       +-------------------+
| id (PK)           |<---+  | id (PK)           |
| email (unique)    |    |  | user_id (FK)------+
| name              |    |  | external_doc_id   |----> rag.documents.id
| password_digest   |    |  | title             |
| created_at        |    |  | status            |
| updated_at        |    |  | chunks_count      |
+-------------------+    |  | budget            |
                         |  | currency          |
                         |  | technologies      |
                         |  | raw_json          |
                         |  | ingested_at       |
                         |  +-------------------+
                         |          |
                         |          | has_one
                         |          v
                         |  +-------------------+
                         |  | chunks_breakdowns |
                         |  +-------------------+
                         |  | id (PK)           |
                         |  | document_id (FK)  |
                         |  | project_overview  |
                         |  | scope_block       |
                         |  | line_item         |
                         |  | phase             |
                         |  | team_conditions   |
                         |  +-------------------+
                         |
                         |  +-------------------+       +--------------------+
                         |  |   estimations     |       | functional_blocks  |
                         |  +-------------------+       +--------------------+
                         +--| user_id (FK)      |<------| estimation_id (FK) |
                            | id (PK)           |       | id (PK)            |
                            | title             |       | name               |
                            | description       |       | position           |
                            | status            |       +--------------------+
                            | global_rate       |               |
                            | currency          |               | has_many
                            | confidence_score  |               v
                            | confidence_level  |       +--------------------+
                            | technologies      |       |      tasks         |
                            | total_hours_*     |       +--------------------+
                            | total_cost_*      |       | id (PK)            |
                            | raw_transcriptions|       | functional_block_id|
                            | error_message     |       | name               |
                            +-------------------+       | hours_optimistic   |
                                    |                   | hours_expected     |
                                    | has_many          | hours_pessimistic  |
                                    v                   | rate               |
                            +-------------------+       | position           |
                            |   references      |       +--------------------+
                            +-------------------+
                            | id (PK)           |
                            | estimation_id(FK) |
                            | title             |
                            | similarity_score  |
                            | cost              |
                            | technologies      |
                            | chunk_id (uuid)   |----> rag.chunks.id
                            | chunk_type        |
                            | content_preview   |
                            | currency          |
                            +-------------------+
```

### 5.2 Schema `rag` (FastAPI)

```
+---------------------+        +-------------------------+
|     documents       |        |         chunks          |
+---------------------+        +-------------------------+
| id (UUID, PK)       |<-------| document_id (FK, CASCADE)|
| project_title       |        | id (UUID, PK)           |
| project_subtitle    |        | chunk_type (VARCHAR 30)  |
| total_budget (12,2) |        |   CHECK: project_overview|
| currency (3)        |        |   scope_block, line_item |
| total_duration_weeks|        |   phase, team_conditions |
| team_size           |        | content_text (TEXT)      |
| technologies (TEXT[])|       | embedding Vector(1536)   |  <-- HNSW index
| client_company_hash |        | metadata (JSONB)         |
| client_sector       |        | embedding_model          |
| ingestion_status    |        | project_title            |
|   CHECK: pending,   |        | technologies (TEXT[])    |
|   processing,       |        | total_cost (12,2)        |
|   completed, failed |        | currency (3)             |
| ingestion_error     |        +-------------------------+
| chunks_count        |
| raw_json (JSONB)    |        +-------------------------+
| source              |        |      search_logs        |
| ingested_by         |        +-------------------------+
+---------------------+        | id (UUID, PK)           |
                               | query_text              |
+---------------------+        | query_embedding (1536)  |
|   ingestion_logs    |        | chunk_types_filter      |
+---------------------+        | technologies_filter     |
| id (UUID, PK)       |        | results_count           |
| document_id (FK)    |        | top_score (FLOAT)       |
| action (VARCHAR 50) |        | avg_score (FLOAT)       |
| status (VARCHAR 20) |        | response_time_ms        |
| details (JSONB)     |        | feedback_score (1-5)    |
| duration_ms         |        | feedback_notes          |
| error_message       |        +-------------------------+
+---------------------+

Indices destacados:
  - chunks.embedding: HNSW (vector_cosine_ops, m=16, ef_construction=200)
  - chunks.technologies: GIN
  - chunks.metadata: GIN (jsonb_path_ops)
  - documents.technologies: GIN
```

### 5.3 Referencia cruzada entre schemas

Los schemas se conectan logicamente mediante UUIDs:

- `app.documents.external_document_id` --> `rag.documents.id`
- `app.references.chunk_id` --> `rag.chunks.id`

No existen foreign keys fisicas entre schemas; la integridad se mantiene a nivel de aplicacion.

---

## 6. Flujos de datos principales

### 6.1 Flujo de ingesta

```
Usuario                Rails                  FastAPI               PostgreSQL        OpenAI
  |                      |                      |                      |                |
  |-- Upload JSON ------>|                      |                      |                |
  |                      |-- Parsear JSON       |                      |                |
  |                      |-- Crear Document     |                      |                |
  |                      |   (status: pending)  |                      |                |
  |                      |                      |                      |                |
  |                      |-- POST /ingest ----->|                      |                |
  |                      |                      |-- Validar QuoteInput |                |
  |                      |                      |-- Detectar duplicado |                |
  |                      |                      |-- Anonimizar PII     |                |
  |                      |                      |-- Generar chunks     |                |
  |                      |                      |   (5 tipos)          |                |
  |                      |                      |                      |                |
  |                      |                      |-- Embed chunks ------|--------------->|
  |                      |                      |<-- Vectores (1536d) -|----------------|
  |                      |                      |                      |                |
  |                      |                      |-- INSERT document -->|                |
  |                      |                      |-- INSERT chunks ---->|                |
  |                      |                      |   (con embeddings)   |                |
  |                      |                      |                      |                |
  |                      |<-- 202 Accepted -----|                      |                |
  |                      |   {document_id}      |                      |                |
  |                      |                      |                      |                |
  |                      |-- Enqueue            |                      |                |
  |                      |   IngestionStatusJob |                      |                |
  |                      |       |              |                      |                |
  |                      |       |-- GET /ingest/{id}/status -------->|                |
  |                      |       |<-- {status, chunks_count} --------|                |
  |                      |       |              |                      |                |
  |                      |       |-- Si processing: re-enqueue (5s)   |                |
  |                      |       |-- Si completed: crear breakdown    |                |
  |                      |       |              |                      |                |
  |<== Turbo Stream ==== |       |              |                      |                |
  |    (document row     |                      |                      |                |
  |     actualizado)     |                      |                      |                |
```

### 6.2 Flujo de estimacion (3 pasos en la UI)

```
PASO 1: Envio de transcripciones
+--------------------------------------------------------------+
| Usuario escribe/sube transcripciones de reuniones             |
| Rails crea Estimation (status: "processing")                  |
| Enqueue EstimationJob                                         |
+--------------------------------------------------------------+
                              |
                              v
PASO 2: Procesamiento RAG (asincrono)
+--------------------------------------------------------------+
| EstimationJob:                                                |
|   1. Concatena transcripciones en query                       |
|   2. POST /estimate al servicio RAG                           |
|      a. Embed query -> vector 1536d                           |
|      b. HNSW search en pgvector                               |
|      c. Re-ranking (similarity + tech + recency + cost)       |
|      d. Generar estimacion con o4-mini                        |
|      e. Calcular confidence score                             |
|   3. Parsear respuesta -> bloques, tareas, referencias        |
|   4. Crear FunctionalBlocks + Tasks + References              |
|   5. Estimation.status = "structuring"                        |
|   6. Broadcast via Turbo Stream                               |
+--------------------------------------------------------------+
                              |
                              v
PASO 3: Revision y ajuste (usuario)
+--------------------------------------------------------------+
| El usuario ve la estimacion estructurada:                     |
|   - Bloques funcionales con tareas                            |
|   - Horas optimista / esperada / pesimista                    |
|   - Coste calculado (horas x tarifa)                          |
|   - Score de confianza y nivel                                |
|   - Referencias a presupuestos historicos                     |
|                                                               |
| Puede:                                                        |
|   - Reorganizar bloques y tareas (drag & drop)                |
|   - Editar horas de cada tarea                                |
|   - Cambiar tarifa global o por tarea                         |
|   - Cambiar moneda (EUR/USD/GBP)                              |
|   - Alternar vista optimista/esperada/pesimista               |
|   - Marcar como completada                                    |
+--------------------------------------------------------------+
```

### 6.3 Flujo de generacion de presupuesto

```
Transcripcion
     |
     v
+-------------------------------+
| Paso 1: Analisis              |
| reasoning_service             |
| .analyze_transcription()      |
|                               |
| Input:  texto transcripcion   |
| Output: TranscriptionAnalysis |
|   - titulo, descripcion       |
|   - modulos funcionales       |
|   - integraciones             |
|   - tecnologias               |
|   - complejidad estimada      |
|   - 3-5 search_queries        |
+-------------------------------+
     |
     v
+-------------------------------+
| Paso 2: Busqueda RAG          |
| retrieval_service.search()    |
|                               |
| Ejecutar N search_queries     |
| concurrentemente              |
| Deduplicar por chunk_id       |
| Ordenar por final_score       |
| Retornar top 15 chunks        |
+-------------------------------+
     |
     v
+-------------------------------+
| Paso 3: Generacion            |
| reasoning_service             |
| .generate_quote()             |
|                               |
| Input:  analysis + chunks     |
| Output: QuoteOutput           |
|   - scope_blocks              |
|   - roadmap_phases            |
|   - items (con costes)        |
|   - team_members              |
|   - condiciones               |
+-------------------------------+
     |
     v
  Presupuesto completo
  estructurado (JSON)
```

### 6.4 Flujo de busqueda semantica

```
Query del usuario
     |
     v
+-- Preprocesamiento ----------------+
| 1. Normalizacion Unicode           |
| 2. Expansion de abreviaturas       |
|    (JWT, API, REST, CI/CD, ...)    |
| 3. Deteccion de tecnologias        |
|    (50+ aliases -> nombres canon.) |
| 4. Sugerencia de chunk_types       |
|    (keywords -> tipos relevantes)  |
+------------------------------------+
     |
     v
+-- Embedding ------------------------+
| text-embedding-3-small              |
| -> Vector 1536 dimensiones          |
+-------------------------------------+
     |
     v
+-- Busqueda HNSW --------------------+
| pgvector cosine distance            |
| ef_search = 100                     |
| Filtros opcionales:                 |
|   - chunk_types[]                   |
|   - technologies[]                  |
|   - min_cost / max_cost             |
| Minimo: min_similarity (0.6)        |
+-------------------------------------+
     |
     v
+-- Re-ranking compuesto -------------+
| 0.50 * similarity (coseno)          |
| 0.25 * tech_match (Jaccard)         |
| 0.15 * recency (decay exponencial)  |
| 0.10 * cost_range (outlier MAD)     |
+-------------------------------------+
     |
     v
+-- Deduplicacion ---------------------+
| Mejor score por (document_id,        |
|                   chunk_type)         |
+--------------------------------------+
     |
     v
  Resultados ordenados por final_score
  (max top_k, default 10)
```

---

## 7. Comunicacion entre servicios

### 7.1 Protocolo

- **Transporte:** HTTP/REST
- **Formato:** JSON
- **Cliente:** Faraday 2.9+ (Ruby) con middleware de request/response JSON

### 7.2 Configuracion de conexion

| Parametro | Valor |
|---|---|
| Base URL | `ENV["RAG_SERVICE_BASE_URL"]` (default: `http://localhost:8000`) |
| Timeout | 60 segundos |
| Open timeout | 10 segundos |
| Prefijo API | `/api/v1` |

### 7.3 Autenticacion entre servicios

- **Mecanismo:** API Key via header o configuracion
- **Variable:** `API_KEY` en el servicio RAG (default: `dev-api-key`)

### 7.4 Manejo de errores

```
Faraday::TimeoutError       -> RagServiceClient::TimeoutError
Faraday::ConnectionFailed   -> RagServiceClient::ServiceUnavailableError
HTTP 404                    -> RagServiceClient::NotFoundError
HTTP 503                    -> RagServiceClient::ServiceUnavailableError
HTTP otros                  -> RagServiceClient::Error (con status code)
```

El concern `RagErrorHandling` intercepta estas excepciones en los controllers:

- **GET requests:** renderiza la vista actual con status 503
- **POST/PATCH/DELETE:** redirect_back con mensaje de error flash

Los jobs implementan reintentos automaticos:

| Job | Error | Reintentos | Espera |
|---|---|---|---|
| `EstimationJob` | TimeoutError | 3 | 10s |
| `EstimationJob` | ServiceUnavailableError | 3 | 15s |
| `IngestionStatusJob` | TimeoutError | 5 | 10s |
| `IngestionStatusJob` | Error | 3 | 15s |

---

## 8. Infraestructura y despliegue

### 8.1 Servicio RAG — Docker

**Dockerfile** (multi-stage build):

```
Etapa 1 (Builder):
  Base: python:3.11-slim
  Instala: build-essential, libpq-dev
  Instala dependencias desde pyproject.toml

Etapa 2 (Runtime):
  Base: python:3.11-slim
  Copia dependencias del builder
  Copia: app/, alembic/, alembic.ini, entrypoint.sh
  Usuario: appuser (no-root)
  Puerto: 8000
  Entrypoint: ./entrypoint.sh (ejecuta migraciones Alembic + uvicorn)
```

### 8.2 Plataforma Web — Docker

**Dockerfile** (multi-stage build):

```
Etapa 1 (Builder):
  Base: ruby:3.4.4-slim
  Bundle install
  Precompila assets

Etapa 2 (Runtime):
  Usuario: rails (UID 1000, no-root)
  Puerto: 80
  Entrypoint: /rails/bin/docker-entrypoint
  Comando: ./bin/thrust ./bin/rails server (Thruster para HTTP caching)
```

### 8.3 Docker Compose (desarrollo)

```yaml
# docker-compose.yml (servicio RAG)
services:
  postgres:
    image: pgvector/pgvector:pg16
    ports: 5432:5432
    environment:
      POSTGRES_DB: estimations
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev
    healthcheck: pg_isready
    volumes: pgdata

  rag-service:
    build: .
    ports: 8000:8000
    depends_on: postgres (healthy)
    command: uvicorn app.main:app --reload
    volumes: ./app:/app/app (hot reload)

# docker-compose.dev.yml (plataforma Rails)
services:
  postgres:
    image: postgres:16-alpine
    ports: 5433:5432

  web:
    ports: 3000:3000
    environment:
      RAG_SERVICE_BASE_URL: http://host.docker.internal:8000
```

### 8.4 Migraciones

| Servicio | Herramienta | Schema | Migraciones |
|---|---|---|---|
| **RAG** | Alembic | `rag` | 5 migraciones: extensions, documents, chunks (HNSW), ingestion_logs, search_logs |
| **Rails** | ActiveRecord | `public` (app) | Estandar Rails: users, documents, estimations, functional_blocks, tasks, references, chunks_breakdowns |

Las migraciones de Alembic se ejecutan automaticamente al iniciar el contenedor
(via `entrypoint.sh`).

---

## 9. Integraciones externas

### 9.1 OpenAI

El sistema utiliza dos modelos de OpenAI para funciones distintas:

| Modelo | Uso | API | Dimensiones / Tokens |
|---|---|---|---|
| `text-embedding-3-small` | Generacion de embeddings vectoriales | Embeddings API | 1536 dimensiones |
| `o4-mini` | Estimaciones, analisis de transcripciones, generacion de presupuestos | Responses API | Max 16384 output tokens |

**Uso del modelo o4-mini:**
- **Estimaciones:** `client.responses.create()` con system prompt experto en estimacion
- **Analisis y generacion:** `client.responses.parse()` con Structured Output (Pydantic models)
- **Timeout:** 120 segundos para cadena de razonamiento interna

**Politica de reintentos:**

| Error | Reintentos | Backoff |
|---|---|---|
| Rate limit (429) | 3 | 2s, 4s, 8s (exponencial) |
| Timeout | 1 | inmediato |
| Server error (5xx) | 2 | 2s, 4s |
| Auth error (401) | 0 | fallo inmediato |

### 9.2 PostgreSQL + pgvector

| Caracteristica | Configuracion |
|---|---|
| Extension | pgvector |
| Imagen Docker | `pgvector/pgvector:pg16` |
| Tipo de indice | HNSW (Hierarchical Navigable Small World) |
| Distancia | Coseno (`vector_cosine_ops`) |
| Parametros HNSW | `m=16`, `ef_construction=200` |
| Parametro busqueda | `ef_search=100` |
| Dimension vectores | 1536 |
| Indices adicionales | GIN en `technologies[]`, GIN en `metadata` (jsonb_path_ops) |

---

## Resumen de metricas clave

| Metrica | Valor |
|---|---|
| Modelo de embeddings | text-embedding-3-small |
| Dimensiones del vector | 1536 |
| Modelo LLM | o4-mini |
| Max output tokens LLM | 16384 |
| Timeout LLM | 120s |
| Top-K default / max | 10 / 50 |
| Min similarity default | 0.6 |
| Tipos de chunk | 5 |
| HNSW m / ef_construction / ef_search | 16 / 200 / 100 |
| Pesos re-ranking | Similarity 50%, Tech 25%, Recency 15%, Cost 10% |
| Pesos confianza | References 35%, Similarity 30%, Tech 20%, Variance 15% |
| Max queries batch | 20 |
| Timeout Faraday (Rails→RAG) | 60s |
| Monedas soportadas | EUR, USD, GBP |
