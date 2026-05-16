---
name: issue-spec
description: Produce una spec técnica completa para una issue local. Explora el codebase, selecciona agentes via @project-coordinator, y añade la spec al final del fichero issues/{id}.md. Ejecutar antes de /worktree-tdd.
argument-hint: <issue_id>
disable-model-invocation: true
---

<input>
$ARGUMENTS
</input>

# /issue-spec — Spec técnica para una issue local

Eres un arquitecto técnico. Tu trabajo es producir una especificación completa para la issue indicada, coordinando varios sub-agentes especializados que escriben en un **documento de sesión único y vivo**, y guardarlo localmente para que `/worktree-tdd` lo use como contexto.

El input es el ID o slug de la issue (e.g. `006-02` o `006-02-extract-design-system`).

---

## Fase 1 — Setup

1. Parsear `$ARGUMENTS` como ID de issue `N`
2. Leer la issue: `issues/{N}*.md` (glob por prefijo de ID)
   - Si no existe, detener y pedir al usuario que la cree con `/create-new-gh-issue`
3. Verificar si ya existe una sección `## Technical Spec` en `issues/{N}*.md`
   - Si existe, usar AskUserQuestion: "Ya existe una spec para la issue #{N}. ¿La mantenemos o la sobreescribimos?"
   - Opciones: "Mantener la existente" / "Sobreescribir"

---

## Fase 2 — Exploración del codebase

Lanzar **2-3 Explore agents en paralelo** (background) con focos específicos basados en el contenido de la issue:

- **Agent 1**: Identificar endpoints FastAPI, modelos SQLAlchemy, servicios y schemas Pydantic relevantes (cruzar keywords de la issue con nombres de archivos y clases en `app/`)
- **Agent 2**: Encontrar tests existentes en `tests/`, fixtures relevantes en `conftest.py`, y patrones de test pytest-asyncio a seguir
- **Agent 3** (si la issue involucra AI/frontend/infra): Explorar `app/core/`, `adapters/primary/web/`, o infra según corresponda

Esperar que **todos** completen antes de continuar.

---

## Fase 3 — Selección de agentes via `@project-coordinator`

Invocar `@project-coordinator` con:
- Body de la issue
- Findings de la exploración (Fase 2)
- Lista de agentes disponibles:

| Agente | Dominio |
|--------|---------|
| `@backend-developer` | FastAPI endpoints, SQLAlchemy models, servicios, Alembic migrations |
| `@backend-test-engineer` | pytest-asyncio: fixtures, mocks, casos de test |
| `@vertex-ai-architect` | Gemini 2.5 Flash, embeddings, prompts, RAG pipeline |
| `@ui-ux-analyzer` | HTML/JS frontend, Web Audio API, accesibilidad |
| `@mlops-engineer` | Docker, Cloud Build, Cloud Run, CI/CD |
| `@sentry-pipeline-engineer` | Sentry error tracking para FastAPI |
| `@qa-criteria-validator` | Criterios Given-When-Then, specs Playwright |

`@project-coordinator` debe determinar y devolver:
- Qué agentes son necesarios para esta issue concreta
- Cuáles forman el **explore tier** (pueden correr en paralelo)
- Cuáles forman el **synthesis tier** (deben correr secuencialmente)
- El orden de dependencias

Presentar al usuario via AskUserQuestion:
```
| Agente | Dominio | Tier | ¿Paralelo? |
|--------|---------|------|-----------|
| @backend-developer | FastAPI architecture | Explore | Sí |
| ... | ... | ... | ... |
```
Opciones: "Proceder" / "Añadir [agente]" / "Quitar [agente]"

**Esperar confirmación** antes de continuar.

---

## Fase 4 — Inicializar sección de spec en el issue

1. Localizar el fichero de la issue: `issues/{N}*.md`
2. Añadir al final del fichero la sección de spec (contenido de la plantilla):
   ```bash
   echo "\n---\n" >> issues/{N}-{slug}.md
   cat ${CLAUDE_SKILL_DIR}/issue-spec-template.md >> issues/{N}-{slug}.md
   ```
3. Rellenar en la nueva sección:
   - Fecha actual (YYYY-MM-DD)
   - Estado: `draft`
   - Lista de agentes confirmados
   - Estado actual del sistema (de la exploración, Fase 2)
4. Dejar todas las secciones de agentes con sus marcadores `[PENDING]`

---

## Fase 5 — Explore Tier (paralelo)

Lanzar todos los agentes del explore tier **en paralelo** (background).

**Prompt para cada agente** (adaptar por agente):
```
Eres parte del skill /issue-spec para la issue #{N}: [Título].

CONTEXTO DE LA ISSUE:
[Body de la issue]

FINDINGS DE EXPLORACIÓN:
[Findings relevantes de Fase 2]

TU TAREA:
1. Lee el documento de issue completo: issues/{N}-{slug}.md (la spec está al final del fichero)
2. Rellena TU sección, delimitada por:
   <!-- === @{agent-name} section === -->
   ...tu contenido va aquí...
   <!-- === end @{agent-name} === -->
3. Usa la herramienta Edit para reemplazar [PENDING] dentro de tu sección
4. NO toques ninguna otra sección del documento
5. Sé concreto: nombres reales de clases, rutas reales de archivo, código real

Stack: FastAPI, SQLAlchemy async, Python 3.11, PostgreSQL+pgvector, pytest-asyncio, google-genai, Google Cloud STT/TTS
```

Reportar progreso conforme terminen los agentes. Esperar que **todos** completen antes de continuar.

---

## Fase 6 — Synthesis Tier (secuencial)

### Paso 6a — `@backend-test-engineer`

Lanzar con instrucción de:
1. Leer `.claude/sessions/issue_spec_{N}.md` completo (especialmente sección de `@backend-developer`)
2. Rellenar la sección `<!-- === @backend-test-engineer section === -->` con:
   - Estrategia pytest-asyncio: qué endpoints/servicios testear, qué fixtures necesitar
   - Qué mockear (google-genai, Google Cloud STT/TTS, pgvector)
   - Casos de test concretos (nombres incluidos)
   - Archivos de test a crear en `tests/`

Esperar que complete antes del siguiente paso.

### Paso 6b — `@qa-criteria-validator`

Lanzar **después** de que 6a complete, con instrucción de:
1. Leer `.claude/sessions/issue_spec_{N}.md` completo
2. Rellenar la sección `<!-- === @qa-criteria-validator section === -->` con:
   - Criterios Given-When-Then por funcionalidad principal
   - Escenarios de Manual Testing para Playwright (TC-1, TC-2, etc.)
   - Prerrequisitos de estado del sistema para cada test

---

## Fase 7 — Consolidación

Leer el documento completo y sintetizar (reemplazar marcadores `[PENDING]`):

1. **Executive Summary**: 2-3 frases que resumen qué se construye y cómo

2. **MoSCoW table**:
   - Must: funcionalidades esenciales para cerrar la issue
   - Should: mejoras significativas del mismo scope
   - Could: nice-to-have si hay tiempo
   - Won't: explícitamente fuera de scope

3. **Implementation Phases table**: fases concretas y granulares
   - Cada fase: un solo commit lógico
   - Description: nombres reales de clases y archivos
   - TDD: `yes` para todas excepto puro styling/layout
   - Parallel/Depends: mapear dependencias reales

4. **UML Sequence Diagrams**: diagramas Mermaid para flujos clave
   - Obligatorio si la issue involucra endpoints, pipelines async, o integración AI

5. **Appendix** — Files to Create / Files to Edit: tablas con rutas absolutas desde la raíz del repo

6. **Success Criteria**: criterios funcionales y no-funcionales concretos y verificables

---

## Fase 8 — Review con usuario

Presentar via AskUserQuestion:
- MoSCoW table
- Implementation Phases table
- Lista de agentes que contribuyeron

Opciones:
- "Guardar spec"
- "Necesita cambios — [sección específica]"
- "Editar [sección] antes de guardar"

Si hay cambios: iterar sobre la sección indicada antes de guardar.

**Esperar confirmación** antes de guardar.

---

## Fase 9 — Guardar

1. La spec ya está añadida al final de `issues/{N}-{slug}.md`
2. Actualizar el campo de estado en la sección spec:
   - Cambiar `Estado: draft` → `Estado: listo`
3. Reportar al usuario:
   ```
   Spec añadida a issues/{N}-{slug}.md
   Siguiente paso: /worktree-tdd {N}
   ```

---

## Reglas

- Usar `AskUserQuestion` ANTES de lanzar agentes (Fase 3) y ANTES de guardar (Fase 8)
- El archivo de spec **nunca se borra** — es el contexto para `/worktree-tdd` y `/review-spec`
- La spec vive en `issues/` junto a la issue, no en `.claude/sessions/`
- Cada agente debe leer el documento completo **antes** de añadir su sección
- Los delimitadores `<!-- === @agent section === -->` son obligatorios
- MoSCoW e Implementation Phases son siempre obligatorios
- UML Mermaid es obligatorio para issues con endpoints, pipelines async o integración AI
- La lista de agentes la determina siempre `@project-coordinator`
- Stack de referencia: FastAPI, SQLAlchemy async, Python 3.11, PostgreSQL+pgvector, pytest-asyncio, google-genai, Google Cloud STT/TTS
- No usar `gh issue` CLI — las issues son locales en `issues/`
