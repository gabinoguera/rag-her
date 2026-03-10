# Estrategia de Chunking y Vectorización — Servicio RAG de Estimaciones

**Versión:** 1.0  
**Fecha:** 2026-02-10  
**Documento complementario al PRD del Servicio RAG de Estimaciones de Software**

---

## 1. Introducción

Este documento describe en detalle la estrategia de fragmentación (chunking) y vectorización del Servicio RAG de Estimaciones de Software. La estrategia define cómo se transforman los presupuestos JSON en unidades de conocimiento vectorizadas que permiten la búsqueda semántica.

La decisión de chunking es el factor que más influye en la calidad de un sistema RAG. Un chunking inadecuado produce resultados irrelevantes, contexto insuficiente o ruido en la generación. Este documento justifica cada decisión de diseño.

---

## 2. Principios de Diseño

### 2.1 Chunking semántico, no mecánico

Los presupuestos de software son documentos altamente estructurados. Aplicar fragmentación mecánica (por número de tokens, por párrafos o por separadores arbitrarios) destruye la estructura semántica del documento. Un chunk que corta a mitad de un scope_block o que mezcla items de dos fases distintas produce embeddings de baja calidad.

La estrategia adoptada es **chunking semántico basado en la estructura del JSON**: cada chunk corresponde a una unidad de conocimiento autónoma definida por la propia estructura del presupuesto.

### 2.2 Un embedding, texto compuesto

El sistema utiliza **una única columna de embedding** por chunk, pero el texto que se vectoriza no es un campo individual del JSON sino una composición de múltiples campos relacionados. Esto permite que el vector capture la semántica completa de la unidad de conocimiento.

Alternativas descartadas:

- **Vectorizar campos individuales:** Pierde contexto. El embedding de `"API REST robusta y escalable"` no captura que usa JWT, Rails y PostgreSQL.
- **Múltiples embeddings por chunk:** Multiplica el almacenamiento y complica las queries sin ganancia proporcional en calidad. Los modelos de embedding modernos capturan las relaciones entre conceptos co-presentes en el texto.
- **Vectorizar el JSON completo:** Demasiado largo y ruidoso. Los embeddings pierden precisión con textos largos porque promedian la semántica de todo el contenido.

### 2.3 Metadata estructurada separada

Los datos numéricos y categóricos (costes, duraciones, tecnologías) se almacenan como metadata estructurada en columnas JSONB y campos desnormalizados. Estos datos **no se vectorizan** sino que se usan para filtrado pre y post búsqueda vectorial.

La razón es que los embeddings no son buenos representando valores numéricos precisos. El embedding no distinguirá bien entre "500 EUR/día" y "450 EUR/día", pero una query SQL sí. La combinación de búsqueda vectorial (semántica) con filtrado relacional (exacto) produce los mejores resultados.

### 2.4 Prefijos de tipo

Cada texto compuesto incluye un prefijo que indica el tipo de chunk:

| Tipo de chunk | Prefijo |
|---|---|
| Project Overview | `project:` |
| Scope Block | `scope:` |
| Line Item | `task:` |
| Phase | `phase:` |
| Team & Conditions | `team:` |

El prefijo ayuda al modelo de embeddings a discriminar entre tipos de información. Sin prefijo, un texto que describe una fase y uno que describe una tarea podrían producir embeddings demasiado similares. El prefijo actúa como una señal semántica adicional que mejora la separación en el espacio vectorial.

Los prefijos se añaden **solo al texto de los chunks**, no a las queries de búsqueda. Esto permite que una query como "desarrollo de chatbot" busque indistintamente entre scope_blocks, line_items y phases, encontrando la información relevante independientemente de su tipo.

---

## 3. Tipos de Chunks

Se generan **5 tipos de chunks** a partir de cada presupuesto JSON. Cada tipo representa un nivel distinto de granularidad y responde a diferentes tipos de consulta.

### 3.1 Visión general de tipos

```
                    ┌─────────────────────────-┐
                    │   Presupuesto JSON       │
                    │   (documento completo)   │
                    └───────────┬─────────────-┘
                                │
           ┌────────────────────┼────────────────────┐
           │                    │                    │
           ▼                    ▼                    ▼
   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
   │   1 chunk     │   │  N chunks     │   │   1 chunk     │
   │   Project     │   │  (uno por     │   │   Team &      │
   │   Overview    │   │  sección)     │   │   Conditions  │
   └───────────────┘   └───────┬───────┘   └───────────────┘
                               │
                    ┌──────────┼──────────┐
                    │          │          │
                    ▼          ▼          ▼
             ┌──────────┐ ┌────────┐ ┌────────┐
             │ Scope    │ │ Line   │ │ Phase  │
             │ Block    │ │ Item   │ │        │
             │ chunks   │ │ chunks │ │ chunks │
             └──────────┘ └────────┘ └────────┘
```

### 3.2 Cantidad de chunks por presupuesto

La cantidad total de chunks depende de la estructura del presupuesto:

| Tipo.             | Cantidad | Origen                   |
|-------------------|----------|--------------------------|
| Project Overview  | 1        | Fijo por presupuesto     |
| Scope Block       | Variable | 1 por `scope_blocks[]`   |
| Line Item         | Variable | 1 por `items[]`          |
| Phase             | Variable | 1 por `roadmap_phases[]` |
| Team & Conditions | 1        | Fijo por presupuesto     |

Para el presupuesto de ejemplo (3 scope_blocks, 10 items, 5 fases): **1 + 3 + 10 + 5 + 1 = 20 chunks**.

---

## 4. Detalle de Cada Tipo de Chunk

### 4.1 Project Overview

**Propósito:** Capturar la visión global del proyecto para responder consultas como "¿Cuánto cuesta un proyecto de plataforma SaaS con IA?" o "Proyectos similares con equipo de 4 personas".

**Campos del JSON utilizados:**

```
quote.project.title
quote.project.subtitle
quote.objectives[].title + quote.objectives[].description
quote.scope_blocks[].technologies  (agregados y deduplicados)
quote.roadmap_phases[].duration    (sumados)
quote.team_members[].profile_type + quantity + dedication
quote.items[].quantity * quote.items[].unit_price  (suma total)
quote.currency
```

**Plantilla de composición del texto:**

```
project: Proyecto: {project.title}
Descripción: {project.subtitle}
Objetivos del proyecto:
- {objectives[0].title}: {objectives[0].description}
- {objectives[1].title}: {objectives[1].description}
[...]
Tecnologías principales: {technologies_deduplicadas, separadas por coma}
Duración total estimada: {suma_duraciones} semanas
Composición del equipo:
- {team_members[0].quantity} {team_members[0].profile_type} ({team_members[0].dedication})
- {team_members[1].quantity} {team_members[1].profile_type} ({team_members[1].dedication})
[...]
Presupuesto total: {suma_items} {currency}
```

**Ejemplo con datos reales del presupuesto de ejemplo:**

```
project: Proyecto: Plataforma de Gestión con IA
Descripción: Sistema integral de automatización empresarial con inteligencia artificial
Objetivos del proyecto:
- Automatización: Reducir tareas manuales en un 70% mediante automatización inteligente
- Analítica Avanzada: Dashboard en tiempo real con métricas clave del negocio
- Seguridad: Cumplimiento GDPR y cifrado de datos sensibles
- Eficiencia: Reducción del tiempo de procesamiento de 3 días a 2 horas
Tecnologías principales: Ruby on Rails, PostgreSQL, Redis, Sidekiq, React, TypeScript, Tailwind CSS, Chart.js, OpenAI API, LangChain, Python, FastAPI
Duración total estimada: 12 semanas
Composición del equipo:
- 1 Tech Lead (full_time)
- 2 Full Stack Developer (full_time)
- 1 UX/UI Designer (part_time)
- 1 QA Engineer (part_time)
- 1 Project Manager (part_time)
Presupuesto total: 30300 EUR
```

**Metadata estructurada (JSONB):**

```json
{
  "chunk_type": "project_overview",
  "project_title": "Plataforma de Gestión con IA",
  "total_budget": 30300,
  "currency": "EUR",
  "total_duration_weeks": 12,
  "team_size": 6,
  "team_ft_count": 3,
  "team_pt_count": 3,
  "technologies": [
    "Ruby on Rails", "PostgreSQL", "Redis", "Sidekiq",
    "React", "TypeScript", "Tailwind CSS", "Chart.js",
    "OpenAI API", "LangChain", "Python", "FastAPI"
  ],
  "scope_blocks_count": 3,
  "items_count": 10,
  "phases_count": 5,
  "objectives_count": 4,
  "source_quote_id": "uuid"
}
```

**Consultas típicas que resuelve:**

- "¿Cuánto cuesta un proyecto full-stack con módulo de IA?"
- "Proyectos similares con equipo de 3-5 personas"
- "Presupuestos de plataformas de automatización empresarial"
- "¿Qué duración tiene un proyecto con backend Rails y frontend React?"

---

### 4.2 Scope Block

**Propósito:** Unidad principal de búsqueda. Captura un bloque funcional completo (backend, frontend, módulo IA, etc.) con sus funcionalidades, tecnologías y coste asociado. Responde consultas como "¿Cuánto cuesta desarrollar un backend API con autenticación JWT?" o "Bloques de integración con OpenAI".

**Campos del JSON utilizados:**

```
quote.scope_blocks[i].title
quote.scope_blocks[i].short_description
quote.scope_blocks[i].long_description
quote.scope_blocks[i].features[]
quote.scope_blocks[i].technologies[]
quote.scope_blocks[i].detailed_features[].title + description

# Enriquecimiento con items vinculados:
quote.items[] (filtrados por relación con este scope_block)
```

**Vinculación scope_block ↔ items:**

Los items del presupuesto no tienen una referencia directa al scope_block, sino al `phase`. La vinculación se resuelve mediante la siguiente cadena:

```
item.phase → roadmap_phases[].name → roadmap_phases[].modules → scope_block.title
```

Cuando esta relación no es explícita (los modules no coinciden exactamente con el título del scope_block), se aplica matching por similitud textual entre `item.name`/`item.description` y `scope_block.title`/`scope_block.features[]`/`scope_block.detailed_features[].title`.

**Plantilla de composición del texto:**

```
scope: Bloque funcional: {scope_block.title}
Resumen: {scope_block.short_description}
Descripción completa: {scope_block.long_description}
Funcionalidades principales: {scope_block.features, separadas por coma}
Tecnologías: {scope_block.technologies, separadas por coma}
Funcionalidades detalladas:
- {detailed_features[0].title}: {detailed_features[0].description}
- {detailed_features[1].title}: {detailed_features[1].description}
[...]
Tareas asociadas:
- {item_vinculado_1.name}: {item_vinculado_1.quantity} {item_vinculado_1.unit} a {item_vinculado_1.unit_price} {currency}/{unit}
- {item_vinculado_2.name}: {item_vinculado_2.quantity} {item_vinculado_2.unit} a {item_vinculado_2.unit_price} {currency}/{unit}
[...]
Coste total del bloque: {suma_items_vinculados} {currency}
```

**Ejemplo — Scope Block "Backend API":**

```
scope: Bloque funcional: Backend API
Resumen: API REST robusta y escalable
Descripción completa: Desarrollo de una API REST completa con autenticación JWT, rate limiting, y documentación OpenAPI. Incluye endpoints para todas las operaciones CRUD y webhooks para integraciones.
Funcionalidades principales: Autenticación JWT, Rate limiting, Webhooks, Documentación OpenAPI
Tecnologías: Ruby on Rails, PostgreSQL, Redis, Sidekiq
Funcionalidades detalladas:
- Sistema de Autenticación: Implementación de JWT con refresh tokens, gestión de sesiones y soporte para OAuth 2.0 con proveedores externos.
- Rate Limiting Inteligente: Control de peticiones por usuario/IP con límites configurables, burst allowance y respuestas 429 con headers informativos.
- Sistema de Webhooks: Notificaciones en tiempo real a sistemas externos con reintentos automáticos, firma de payloads y panel de monitoreo.
- Documentación OpenAPI: Especificación OpenAPI 3.0 auto-generada con Swagger UI integrado, ejemplos de uso y sandbox de pruebas.
Tareas asociadas:
- Desarrollo API REST: 15 día a 500 EUR/día
- Base de datos y migraciones: 5 día a 450 EUR/día
Coste total del bloque: 9750 EUR
```

**Ejemplo — Scope Block "Módulo IA":**

```
scope: Bloque funcional: Módulo IA
Resumen: Integración con modelos de lenguaje
Descripción completa: Implementación de asistente virtual con capacidades de procesamiento de lenguaje natural, análisis de documentos y generación de informes automáticos.
Funcionalidades principales: Chatbot inteligente, Análisis de documentos, Generación de informes, Clasificación automática
Tecnologías: OpenAI API, LangChain, Python, FastAPI
Funcionalidades detalladas:
- Chatbot Conversacional: Asistente virtual con memoria de contexto, capacidad multiturno y personalización de personalidad mediante prompts.
- Procesamiento de Documentos: Extracción de información de PDFs, imágenes y documentos escaneados con OCR y análisis semántico.
- Generación de Informes: Creación automática de reportes en múltiples formatos (PDF, Word, Excel) basados en datos y plantillas.
- Clasificación Inteligente: Categorización automática de contenido, etiquetado semántico y enrutamiento basado en intenciones.
Tareas asociadas:
- Integración OpenAI: 5 día a 550 EUR/día
- Desarrollo chatbot: 5 día a 550 EUR/día
Coste total del bloque: 5500 EUR
```

**Metadata estructurada (JSONB):**

```json
{
  "chunk_type": "scope_block",
  "block_title": "Backend API",
  "technologies": ["Ruby on Rails", "PostgreSQL", "Redis", "Sidekiq"],
  "features": ["Autenticación JWT", "Rate limiting", "Webhooks", "Documentación OpenAPI"],
  "detailed_features_count": 4,
  "project_title": "Plataforma de Gestión con IA",
  "source_quote_id": "uuid",
  "related_items": [
    {
      "name": "Desarrollo API REST",
      "quantity": 15,
      "unit": "dia",
      "unit_price": 500,
      "total": 7500
    },
    {
      "name": "Base de datos y migraciones",
      "quantity": 5,
      "unit": "dia",
      "unit_price": 450,
      "total": 2250
    }
  ],
  "block_total_cost": 9750,
  "block_total_days": 20,
  "currency": "EUR"
}
```

**Consultas típicas que resuelve:**

- "Backend API con autenticación JWT y webhooks"
- "Módulo de inteligencia artificial con chatbot y procesamiento de documentos"
- "Frontend React con dashboard interactivo y modo oscuro"
- "¿Cuánto cuesta un bloque de integración con OpenAI?"

---

### 4.3 Line Item

**Propósito:** Capturar tareas individuales con su estimación de esfuerzo y coste. Es el nivel más granular de búsqueda, ideal para consultas específicas como "¿Cuánto cuesta un sistema de autenticación?" o "Precio por día de desarrollo de chatbot".

**Campos del JSON utilizados:**

```
quote.items[i].name
quote.items[i].description
quote.items[i].type
quote.items[i].quantity
quote.items[i].unit
quote.items[i].unit_price
quote.items[i].discount_percent
quote.items[i].phase
quote.currency
```

**Plantilla de composición del texto:**

```
task: Tarea: {item.name}
Descripción: {item.description}
Tipo: {item.type}
Estimación: {item.quantity} {item.unit} a {item.unit_price} {currency}/{item.unit}
Total: {item.quantity * item.unit_price} {currency}
Fase del proyecto: {item.phase}
```

**Ejemplo — Item "Desarrollo API REST":**

```
task: Tarea: Desarrollo API REST
Descripción: Backend completo con autenticación, CRUD y webhooks
Tipo: service
Estimación: 15 día a 500 EUR/día
Total: 7500 EUR
Fase del proyecto: Fase 2: Desarrollo Backend
```

**Ejemplo — Item "Desarrollo chatbot":**

```
task: Tarea: Desarrollo chatbot
Descripción: Asistente virtual con contexto y memoria de conversación
Tipo: service
Estimación: 5 día a 550 EUR/día
Total: 2750 EUR
Fase del proyecto: Fase 4: Integración IA
```

**Metadata estructurada (JSONB):**

```json
{
  "chunk_type": "line_item",
  "item_name": "Desarrollo API REST",
  "item_type": "service",
  "quantity": 15,
  "unit": "dia",
  "unit_price": 500,
  "total_price": 7500,
  "discount_percent": 0,
  "currency": "EUR",
  "phase": "Fase 2: Desarrollo Backend",
  "project_title": "Plataforma de Gestión con IA",
  "source_quote_id": "uuid"
}
```

**Consultas típicas que resuelve:**

- "¿Cuánto cuesta el desarrollo de una API REST?"
- "Estimación de diseño UX/UI en días"
- "Precio por día de desarrollo de chatbot"
- "Tareas de testing y QA: ¿cuántos días?"
- "Coste de configuración de CI/CD y despliegue"

---

### 4.4 Phase

**Propósito:** Capturar fases del roadmap con su duración, entregables y coste acumulado. Responde consultas sobre planificación y secuenciación como "¿Cuánto dura una fase de testing?" o "¿Qué entregables incluye la fase de diseño?".

**Campos del JSON utilizados:**

```
quote.roadmap_phases[i].name
quote.roadmap_phases[i].duration
quote.roadmap_phases[i].description
quote.roadmap_phases[i].deliverables[]
quote.roadmap_phases[i].modules[]

# Enriquecimiento con items de la fase:
quote.items[] (filtrados por item.phase == phase.name)
quote.currency
```

**Plantilla de composición del texto:**

```
phase: Fase: {phase.name}
Duración: {phase.duration}
Descripción: {phase.description}
Entregables:
- {phase.deliverables[0]}
- {phase.deliverables[1]}
[...]
Módulos involucrados: {phase.modules, separados por coma}
Tareas incluidas en esta fase:
- {item_1.name}: {item_1.quantity} {item_1.unit} a {item_1.unit_price} {currency}/{unit} = {total} {currency}
- {item_2.name}: {item_2.quantity} {item_2.unit} a {item_2.unit_price} {currency}/{unit} = {total} {currency}
[...]
Coste total de la fase: {suma_items_fase} {currency}
```

**Ejemplo — "Fase 2: Desarrollo Backend":**

```
phase: Fase: Fase 2: Desarrollo Backend
Duración: 4 semanas
Descripción: Implementación de la API, base de datos y lógica de negocio
Entregables:
- API REST funcional
- Base de datos configurada
- Tests unitarios
- Documentación API
Módulos involucrados: Auth, Core, API
Tareas incluidas en esta fase:
- Desarrollo API REST: 15 día a 500 EUR/día = 7500 EUR
- Base de datos y migraciones: 5 día a 450 EUR/día = 2250 EUR
Coste total de la fase: 9750 EUR
```

**Ejemplo — "Fase 5: Testing y Deploy":**

```
phase: Fase: Fase 5: Testing y Deploy
Duración: 1 semana
Descripción: Pruebas finales, optimización y despliegue en producción
Entregables:
- Tests completos
- Despliegue en producción
- Documentación de usuario
- Formación equipo
Módulos involucrados: QA, DevOps
Tareas incluidas en esta fase:
- Testing y QA: 3 día a 400 EUR/día = 1200 EUR
- Despliegue y configuración: 2 día a 500 EUR/día = 1000 EUR
Coste total de la fase: 2200 EUR
```

**Metadata estructurada (JSONB):**

```json
{
  "chunk_type": "phase",
  "phase_name": "Fase 2: Desarrollo Backend",
  "duration": "4 semanas",
  "duration_weeks": 4,
  "deliverables": [
    "API REST funcional",
    "Base de datos configurada",
    "Tests unitarios",
    "Documentación API"
  ],
  "modules": ["Auth", "Core", "API"],
  "phase_total_cost": 9750,
  "phase_total_days": 20,
  "items_count": 2,
  "currency": "EUR",
  "project_title": "Plataforma de Gestión con IA",
  "source_quote_id": "uuid"
}
```

**Consultas típicas que resuelve:**

- "¿Cuánto dura una fase de desarrollo backend?"
- "Entregables típicos de una fase de análisis y diseño"
- "Coste de la fase de integración de IA"
- "¿Qué incluye normalmente una fase de testing y deploy?"

---

### 4.5 Team & Conditions

**Propósito:** Capturar la composición del equipo y las condiciones comerciales del presupuesto. Responde consultas sobre staffing y términos contractuales como "¿Qué equipo necesito para un proyecto con IA?" o "Condiciones de pago habituales".

**Campos del JSON utilizados:**

```
quote.team_members[].profile_type
quote.team_members[].description
quote.team_members[].quantity
quote.team_members[].dedication
quote.conditions.payment_terms[]
quote.conditions.included_services[]
quote.conditions.additional_services[].name + price
quote.currency
```

**Plantilla de composición del texto:**

```
team: Equipo del proyecto "{project.title}":
- {team[0].quantity} {team[0].profile_type} ({team[0].dedication}): {team[0].description}
- {team[1].quantity} {team[1].profile_type} ({team[1].dedication}): {team[1].description}
[...]
Total equipo: {suma_quantities} personas ({ft_count} a tiempo completo, {pt_count} a tiempo parcial)

Condiciones de pago:
- {payment_terms[0]}
- {payment_terms[1]}
[...]

Servicios incluidos:
- {included_services[0]}
- {included_services[1]}
[...]

Servicios adicionales disponibles:
- {additional_services[0].name}: {additional_services[0].price} {currency}
- {additional_services[1].name}: {additional_services[1].price} {currency}
[...]
```

**Ejemplo con datos reales:**

```
team: Equipo del proyecto "Plataforma de Gestión con IA":
- 1 Tech Lead (full_time): Liderazgo técnico y arquitectura de la solución
- 2 Full Stack Developer (full_time): Desarrollo de backend con Rails y frontend con React
- 1 UX/UI Designer (part_time): Diseño de interfaces, wireframes y sistema de diseño
- 1 QA Engineer (part_time): Testing y aseguramiento de calidad
- 1 Project Manager (part_time): Coordinación del proyecto y comunicación con el cliente
Total equipo: 6 personas (3 a tiempo completo, 3 a tiempo parcial)

Condiciones de pago:
- 30% al inicio del proyecto (firma del contrato)
- 30% al completar Fase 2 (Backend funcional)
- 30% al completar Fase 4 (Sistema completo)
- 10% a la entrega final y aceptación

Servicios incluidos:
- Soporte técnico 3 meses post-entrega
- Documentación técnica completa
- Manual de usuario
- Formación al equipo (8 horas)
- Código fuente con licencia perpetua
- Despliegue en infraestructura del cliente

Servicios adicionales disponibles:
- Mantenimiento mensual: 800 EUR
- Soporte premium 24/7: 1200 EUR
- Desarrollo de nuevas funcionalidades: 450 EUR
```

**Metadata estructurada (JSONB):**

```json
{
  "chunk_type": "team_conditions",
  "team_composition": [
    { "profile": "Tech Lead", "quantity": 1, "dedication": "full_time" },
    { "profile": "Full Stack Developer", "quantity": 2, "dedication": "full_time" },
    { "profile": "UX/UI Designer", "quantity": 1, "dedication": "part_time" },
    { "profile": "QA Engineer", "quantity": 1, "dedication": "part_time" },
    { "profile": "Project Manager", "quantity": 1, "dedication": "part_time" }
  ],
  "total_team_size": 6,
  "ft_count": 3,
  "pt_count": 3,
  "payment_milestones": 4,
  "included_services_count": 6,
  "additional_services_count": 3,
  "project_title": "Plataforma de Gestión con IA",
  "total_budget": 30300,
  "currency": "EUR",
  "source_quote_id": "uuid"
}
```

**Consultas típicas que resuelve:**

- "¿Qué equipo necesito para un proyecto full-stack con IA?"
- "Condiciones de pago habituales para proyectos de 30K EUR"
- "¿Cuántos developers a tiempo completo para un proyecto de 12 semanas?"
- "Servicios incluidos típicos en un presupuesto de desarrollo"

---

## 5. Pipeline de Vectorización

### 5.1 Flujo completo

```
          JSON del presupuesto
                  │
                  ▼
       ┌─────────────────────┐
       │   1. VALIDACIÓN     │  Pydantic valida estructura y campos
       └──────────┬──────────┘
                  │
                  ▼
       ┌─────────────────────┐
       │  2. ANONIMIZACIÓN   │  Eliminar/cifrar datos del cliente
       └──────────┬──────────┘
                  │
                  ▼
       ┌─────────────────────┐
       │   3. CHUNKING       │  Generar los 5 tipos de chunks
       │                     │
       │  ┌───────────────┐  │
       │  │ Para cada tipo│  │
       │  │ de chunk:     │  │
       │  │               │  │
       │  │ a) Extraer    │  │
       │  │    campos     │  │
       │  │               │  │
       │  │ b) Componer   │  │
       │  │    texto      │  │
       │  │               │  │
       │  │ c) Calcular   │  │
       │  │    metadata   │  │
       │  └───────────────┘  │
       └──────────┬──────────┘
                  │
                  ▼
       ┌─────────────────────┐
       │  4. PREPROCESAMIENTO│  Normalización Unicode, limpieza,
       │     DE TEXTO        │  preservación de tecnicismos,
       │                     │  añadir prefijo de tipo
       └──────────┬──────────┘
                  │
                  ▼
       ┌─────────────────────┐       ┌──────────────┐
       │  5. EMBEDDING       │ ────► │  OpenAI API  │
       │                     │ ◄──── │  Embeddings  │
       │  Batch de textos    │       └──────────────┘
       │  preparados         │
       └──────────┬──────────┘
                  │
                  ▼
       ┌─────────────────────┐       ┌──────────────┐
       │  6. ALMACENAMIENTO  │ ────► │  PostgreSQL  │
       │                     │       │  + pgvector  │
       │  content_text       │       └──────────────┘
       │  embedding (1536)   │
       │  metadata (JSONB)   │
       └─────────────────────┘
```

### 5.2 Paso detallado: Preprocesamiento de texto

Antes de generar el embedding, el texto compuesto pasa por las siguientes transformaciones:

**1. Normalización Unicode (NFC):**

Los presupuestos pueden contener caracteres con distintas representaciones Unicode (tildes, eñe). Se normaliza a NFC para garantizar que el mismo carácter siempre produce la misma secuencia de bytes.

```
"Diseño" (NFD: D+i+s+e+ñ+o)  →  "Diseño" (NFC: D+i+s+e+ño)
```

**2. Limpieza de whitespace:**

Se colapsan espacios múltiples, tabs y saltos de línea redundantes en un solo espacio o salto de línea según corresponda. Esto evita que variaciones de formato en el JSON produzcan embeddings diferentes para el mismo contenido.

**3. Eliminación de artefactos de encoding:**

Caracteres como `Ã±` (ñ mal codificada), `â€"` (em dash mal codificado) se corrigen o eliminan.

**4. Preservación de tecnicismos:**

No se aplica stemming, lemmatización ni lowercasing. Los nombres de tecnologías (JWT, OAuth, PostgreSQL, FastAPI) y terminología técnica deben mantener su forma original porque el modelo de embeddings los reconoce en su forma canónica.

**5. Adición de prefijo de tipo:**

Se añade el prefijo correspondiente al inicio del texto: `project:`, `scope:`, `task:`, `phase:`, `team:`.

### 5.3 Paso detallado: Generación de embeddings

Los embeddings se generan en batch para eficiencia:

- Se agrupan todos los textos de chunks de un presupuesto (típicamente 15-25 textos).
- Se envían en una sola llamada a la API de embeddings (OpenAI soporta hasta 2048 textos por batch).
- Se verifica que cada embedding tenga exactamente 1536 dimensiones.
- Se valida que el embedding no sea un vector nulo (todos ceros), lo que indicaría un error.

**Configuración del modelo:**

| Parámetro | Valor |
|---|---|
| Modelo | `text-embedding-3-small` |
| Dimensiones | 1536 |
| Encoding | `cl100k_base` |
| Max tokens de entrada | 8191 |

**Gestión de textos largos:**

Si un texto compuesto excede los 8191 tokens (improbable para chunks individuales, pero posible para scope_blocks muy detallados), se trunca preservando las primeras secciones (título, descripción, funcionalidades) y descartando las últimas (tareas asociadas detalladas), ya que la información más discriminante semánticamente suele estar al inicio.

### 5.4 Paso detallado: Almacenamiento

Cada chunk se almacena como una fila en `rag.chunks` con:

| Columna | Contenido | Tipo |
|---|---|---|
| `content_text` | Texto compuesto completo (lo que se vectorizó) | TEXT |
| `embedding` | Vector de 1536 dimensiones | vector(1536) |
| `metadata` | Metadata estructurada (variable por tipo) | JSONB |
| `chunk_type` | Tipo del chunk | VARCHAR |
| `project_title` | Título del proyecto (desnormalizado) | TEXT |
| `technologies` | Tecnologías (desnormalizadas para filtrado) | TEXT[] |
| `total_cost` | Coste del bloque/item/fase (desnormalizado) | DECIMAL |
| `currency` | Moneda (desnormalizada) | VARCHAR |

La desnormalización de `technologies`, `total_cost` y `currency` en columnas dedicadas permite filtrado SQL eficiente sin necesidad de parsear el JSONB en cada query.

---

## 6. Búsqueda Semántica

### 6.1 Flujo de búsqueda

```
     Query del usuario
            │
            ▼
  ┌──────────────────┐
  │ Preprocesamiento │  Normalización, expansión de abreviaciones,
  │ de la query      │  detección de tecnologías
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐       ┌──────────────┐
  │ Embedding de la  │ ────► │  OpenAI API  │
  │ query            │ ◄──── │              │
  │                  │       └──────────────┘
  │ SIN prefijo      │
  │ de tipo          │
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐       ┌──────────────┐
  │ Búsqueda en      │ ────► │  PostgreSQL  │
  │ pgvector         │ ◄──── │  + pgvector  │
  │                  │       └──────────────┘
  │ Cosine similarity│
  │ + filtros SQL    │
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │ Re-ranking       │  Score compuesto:
  │                  │  similitud + tech match + recencia + varianza
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │ Resultados       │  Top-K chunks con score, metadata y
  │ finales          │  content_text para contexto del LLM
  └──────────────────┘
```

### 6.2 Sin prefijo en la query

El embedding de la query se genera **sin prefijo de tipo**. Esto es intencional: permite que una query como "desarrollo de chatbot con memoria de conversación" busque de forma natural entre scope_blocks (que describen el módulo completo), line_items (que tienen la tarea específica) y phases (que muestran la fase donde se implementa). El prefijo en los chunks ayuda a discriminar entre tipos, pero la query debe ser agnóstica al tipo para maximizar el recall.

Cuando el usuario especifica un filtro de `chunk_types` en la request, el filtrado se hace a nivel SQL (pre-retrieval), no a nivel de embedding.

### 6.3 Query SQL de búsqueda

```sql
SELECT
    c.id,
    c.chunk_type,
    c.content_text,
    c.metadata,
    c.project_title,
    c.technologies,
    c.total_cost,
    c.currency,
    c.created_at,
    1 - (c.embedding <=> :query_embedding) AS similarity_score
FROM rag.chunks c
WHERE
    -- Filtro por tipo de chunk
    (:chunk_types IS NULL OR c.chunk_type = ANY(:chunk_types))
    -- Filtro por tecnologías (intersección: al menos una coincide)
    AND (:technologies IS NULL OR c.technologies && :technologies)
    -- Filtro por rango de coste
    AND (:min_cost IS NULL OR c.total_cost >= :min_cost)
    AND (:max_cost IS NULL OR c.total_cost <= :max_cost)
    -- Filtro por similitud mínima
    AND 1 - (c.embedding <=> :query_embedding) >= :min_similarity
ORDER BY c.embedding <=> :query_embedding
LIMIT :top_k;
```

**Notas sobre la query:**

- `<=>` es el operador de distancia coseno de pgvector. `1 - distancia = similitud`.
- Los filtros SQL se aplican **antes** de la búsqueda vectorial (pre-filtering), lo que reduce el espacio de búsqueda y mejora el rendimiento.
- El índice HNSW acepta filtros, aunque con pre-filtering agresivo puede necesitar escanear más nodos. Si el rendimiento se degrada con muchos filtros, se puede evaluar post-filtering.

### 6.4 Re-ranking

Los resultados de pgvector se re-rankean con un score compuesto:

```
final_score = (
    similarity_score        × 0.50    // Similitud semántica (peso principal)
  + technology_match_score  × 0.25    // Match de tecnologías
  + recency_score           × 0.15    // Presupuestos más recientes
  + cost_range_score        × 0.10    // Penalizar outliers de coste
)
```

**technology_match_score:**

Jaccard similarity entre las tecnologías de la query (detectadas en preprocesamiento) y las del chunk.

```
J(A, B) = |A ∩ B| / |A ∪ B|
```

Si la query no menciona tecnologías, este factor se neutraliza (score = 0.5).

**recency_score:**

Decaimiento exponencial basado en la antigüedad del presupuesto:

```
recency_score = e^(-λ × age_months)

donde λ = 0.03 (decay rate)
```

| Antigüedad | Score |
|---|---|
| 0-6 meses | 0.83 - 1.00 |
| 6-12 meses | 0.70 - 0.83 |
| 1-2 años | 0.49 - 0.70 |
| 2-3 años | 0.34 - 0.49 |
| 3+ años | < 0.34 |

**cost_range_score:**

Penaliza chunks cuyo coste es un outlier estadístico respecto al conjunto de resultados:

```
Si |cost - median| > 2 × MAD:  score = 0.2
Si |cost - median| > 1 × MAD:  score = 0.6
Else:                           score = 1.0

donde MAD = Median Absolute Deviation
```

---

## 7. Ejemplo Completo End-to-End

### 7.1 Ingesta

Se recibe el presupuesto JSON de ejemplo "Plataforma de Gestión con IA".

**Chunks generados (20 total):**

| # | Tipo | Texto (inicio) | Embedding dims | Metadata keys |
|---|---|---|---|---|
| 1 | project_overview | `project: Proyecto: Plataforma de Gestión con IA...` | 1536 | total_budget, team_size, technologies... |
| 2 | scope_block | `scope: Bloque funcional: Backend API...` | 1536 | block_title, related_items, block_total_cost... |
| 3 | scope_block | `scope: Bloque funcional: Frontend Web...` | 1536 | block_title, related_items, block_total_cost... |
| 4 | scope_block | `scope: Bloque funcional: Módulo IA...` | 1536 | block_title, related_items, block_total_cost... |
| 5 | line_item | `task: Tarea: Análisis de requisitos y arquitectura...` | 1536 | item_name, quantity, unit_price, total_price... |
| 6 | line_item | `task: Tarea: Diseño UX/UI...` | 1536 | item_name, quantity, unit_price, total_price... |
| 7 | line_item | `task: Tarea: Desarrollo API REST...` | 1536 | item_name, quantity, unit_price, total_price... |
| 8 | line_item | `task: Tarea: Base de datos y migraciones...` | 1536 | item_name, quantity, unit_price, total_price... |
| 9 | line_item | `task: Tarea: Desarrollo Frontend React...` | 1536 | item_name, quantity, unit_price, total_price... |
| 10 | line_item | `task: Tarea: Dashboard y visualizaciones...` | 1536 | item_name, quantity, unit_price, total_price... |
| 11 | line_item | `task: Tarea: Integración OpenAI...` | 1536 | item_name, quantity, unit_price, total_price... |
| 12 | line_item | `task: Tarea: Desarrollo chatbot...` | 1536 | item_name, quantity, unit_price, total_price... |
| 13 | line_item | `task: Tarea: Testing y QA...` | 1536 | item_name, quantity, unit_price, total_price... |
| 14 | line_item | `task: Tarea: Despliegue y configuración...` | 1536 | item_name, quantity, unit_price, total_price... |
| 15 | phase | `phase: Fase: Fase 1: Análisis y Diseño...` | 1536 | phase_name, duration_weeks, phase_total_cost... |
| 16 | phase | `phase: Fase: Fase 2: Desarrollo Backend...` | 1536 | phase_name, duration_weeks, phase_total_cost... |
| 17 | phase | `phase: Fase: Fase 3: Desarrollo Frontend...` | 1536 | phase_name, duration_weeks, phase_total_cost... |
| 18 | phase | `phase: Fase: Fase 4: Integración IA...` | 1536 | phase_name, duration_weeks, phase_total_cost... |
| 19 | phase | `phase: Fase: Fase 5: Testing y Deploy...` | 1536 | phase_name, duration_weeks, phase_total_cost... |
| 20 | team_conditions | `team: Equipo del proyecto "Plataforma de Gestión con IA"...` | 1536 | team_composition, payment_milestones... |

### 7.2 Búsqueda

**Query:** "Necesito un chatbot con memoria de conversación y procesamiento de documentos usando OpenAI"

**Resultados esperados (por relevancia):**

| Rank | Tipo | Contenido | Similarity | Final Score |
|---|---|---|---|---|
| 1 | scope_block | Módulo IA (chatbot + documentos + informes) | 0.91 | 0.88 |
| 2 | line_item | Desarrollo chatbot (5 días, 550 EUR/día) | 0.87 | 0.84 |
| 3 | line_item | Integración OpenAI (5 días, 550 EUR/día) | 0.83 | 0.80 |
| 4 | phase | Fase 4: Integración IA (2 semanas, 5500 EUR) | 0.76 | 0.72 |
| 5 | project_overview | Plataforma de Gestión con IA (proyecto completo) | 0.68 | 0.62 |

El scope_block del Módulo IA rankea primero porque contiene la mayor concentración de conceptos relevantes (chatbot, documentos, OpenAI, LangChain). Los line_items de chatbot e integración OpenAI aparecen a continuación con datos granulares de coste. La fase 4 aporta contexto de duración. El project_overview aporta contexto general pero con un score menor por ser más genérico.

---

## 8. Decisiones de Diseño y Trade-offs

### 8.1 ¿Por qué texto compuesto en vez de campos individuales?

| Enfoque | Ventaja | Desventaja |
|---|---|---|
| **Texto compuesto (elegido)** | Un solo embedding captura relaciones entre conceptos. Búsqueda simple. | El embedding promedia la semántica, puede diluir señales finas. |
| Campos individuales | Cada campo tiene su propio espacio semántico puro. | Multiplicación de embeddings, queries complejas multi-vector, mayor coste. |
| Multi-vector con fusión | Lo mejor de ambos mundos. | Complejidad alta, latencia mayor, difícil de explicar y depurar. |

El texto compuesto es la opción más pragmática para la fase inicial. Si la evaluación de calidad muestra que ciertas queries no recuperan bien (ej: búsqueda solo por tecnología que se diluye en el texto largo), se puede evolucionar a multi-vector.

### 8.2 ¿Por qué no vectorizar la metadata numérica?

Los embeddings representan semántica, no magnitudes numéricas. El embedding de "500 EUR/día" y "450 EUR/día" serán casi idénticos porque semánticamente son el mismo concepto (precio por día de desarrollo). La diferencia numérica es relevante para el negocio pero no para la recuperación semántica.

Por eso los valores numéricos van en metadata estructurada: el filtrado SQL sí distingue entre 450 y 500.

### 8.3 ¿Por qué HNSW y no IVFFlat?

| Índice | Ventaja | Desventaja |
|---|---|---|
| **HNSW (elegido)** | Mejor recall, no requiere entrenamiento, funciona bien desde el primer vector | Mayor uso de memoria, construcción más lenta |
| IVFFlat | Menor uso de memoria, construcción rápida | Requiere entrenamiento (nlist), menor recall con pocas particiones |

Para un dataset que empieza pequeño y crece gradualmente, HNSW es la mejor opción porque no necesita re-entrenamiento del índice cuando se añaden nuevos vectores.

### 8.4 ¿Por qué prefijos de tipo en los chunks pero no en las queries?

Los prefijos en los chunks crean sub-regiones en el espacio vectorial: los chunks de tipo `task:` se agrupan cerca entre sí, separados de los `scope:` y `phase:`. Esto mejora la precisión intra-tipo.

Pero la query no lleva prefijo para permitir **búsqueda cross-type**: una pregunta sobre "chatbot" debería encontrar tanto el scope_block que lo describe como el line_item que lo presupuesta y la fase que lo planifica. Si la query llevara `task:`, solo encontraría line_items.

Cuando el usuario quiere restringir la búsqueda a un tipo, se usa el filtro SQL `chunk_type = ANY(...)`, que es más preciso y explícito que depender del prefijo.
