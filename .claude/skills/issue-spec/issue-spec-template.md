# Issue Spec: [Título] — #[N]

**Issue local:** `issues/[N]*.md`
**Fecha:** [YYYY-MM-DD]
**Estado:** draft
**Agentes:** [lista de agentes que contribuyeron]

---

## Executive Summary

[PENDING]

---

## Problem Statement

**Issue #[N]:**

[Body de la issue verbatim]

**Estado actual del sistema:**

[De la exploración — cómo maneja el sistema esto hoy]

**Impacto:**

[Quién se ve afectado y cómo]

---

## Proposed Solution

**Overview:**

[PENDING]

**Arquitectura:**
- **API Layer:** [endpoints FastAPI involucrados — routers, schemas Pydantic]
- **Service Layer:** [servicios en `app/services/` afectados]
- **Domain/Core:** [módulos en `app/core/` afectados]
- **Base de datos:** [modelos SQLAlchemy, migraciones Alembic necesarias]
- **AI Integration:** [cambios en `app/core/generation.py`, `embeddings.py`, `prompts.py`, si aplica]
- **Frontend:** [cambios en `adapters/primary/web/`, si aplica]

### Core Capabilities (MoSCoW)

| Priority | Capability | Rationale |
|----------|-----------|-----------|
| Must | [PENDING] | |
| Should | [PENDING] | |
| Could | [PENDING] | |
| Won't | [PENDING] | |

---

## Technical Design

<!-- === @backend-developer section === -->
### FastAPI Architecture Plan

[PENDING]
<!-- === end @backend-developer === -->

<!-- === @vertex-ai-architect section === -->
### AI Integration Design

[PENDING — solo si la issue lo requiere, eliminar sección si no aplica]
<!-- === end @vertex-ai-architect === -->

<!-- === @ui-ux-analyzer section === -->
### UI/UX Design

[PENDING — solo si la issue lo requiere, eliminar sección si no aplica]
<!-- === end @ui-ux-analyzer === -->

<!-- === @mlops-engineer section === -->
### Infrastructure Changes

[PENDING — solo si la issue lo requiere, eliminar sección si no aplica]
<!-- === end @mlops-engineer === -->

<!-- === @sentry-pipeline-engineer section === -->
### Error Tracking Design

[PENDING — solo si la issue lo requiere, eliminar sección si no aplica]
<!-- === end @sentry-pipeline-engineer === -->

---

## Edge Cases & Error Handling

| Scenario | Expected Behavior |
|----------|-------------------|
| [PENDING] | [PENDING] |

---

## Implementation Phases

| # | Phase | Description | Status | Parallel | Depends | TDD |
|---|-------|-------------|--------|----------|---------|-----|
| [PENDING] | | | pending | | | |

> **Status:** pending / in-progress / complete / blocked
> **TDD:** `yes` para todas las fases excepto puro styling/layout sin lógica
> **Description:** incluir nombres concretos de clases y rutas reales de archivo
> **Parallel:** "with N" si puede correr junto a la fase N, "-" si es secuencial
> Las fases deben ser granulares: cada una es un solo commit lógico

### Parallelism Notes

[PENDING]

---

## Test Strategy

<!-- === @backend-test-engineer section === -->

[PENDING]

<!-- === end @backend-test-engineer === -->

---

## Acceptance Criteria

<!-- === @qa-criteria-validator section === -->

### Criterios Given-When-Then

[PENDING]

### Manual Testing Scenarios (Playwright)

| TC | Nombre | Parallel | Motivo | Prerrequisitos |
|----|--------|----------|--------|----------------|
| TC-1 | [nombre] | Sí/No | [por qué es paralelo o secuencial] | [estado previo necesario] |

> **Parallel: Sí** — no depende de estado creado por otro TC, usa rol diferente, o testa ruta independiente
> **Parallel: No** — requiere estado de otro TC, comparte sesión, o debe ejecutarse en orden

**Detalle de TCs:**

**TC-1: [Nombre]**

| Step | Acción | Resultado Esperado |
|------|--------|-------------------|
| 1 | [acción] | [resultado] |

<!-- === end @qa-criteria-validator === -->

---

## Success Criteria

**Funcionales:**
- [ ] [PENDING]

**No funcionales:**
- [ ] [PENDING]

---

## UML Sequence Diagrams

[PENDING — diagramas Mermaid para flujos clave; obligatorio para issues con endpoints, pipelines async o integración AI]

---

## Appendix

**Files to Create:**

| # | File Path | Description |
|---|-----------|-------------|
| [PENDING] | | |

**Files to Edit:**

| # | File Path | Change |
|---|-----------|--------|
| [PENDING] | | |

**Nuevas dependencias (`pyproject.toml`):**
- [PENDING]

**Nuevas variables de entorno (`.env.example`):**
- [PENDING]

---

## Open Questions

- [ ] [PENDING]

---

## Notas de Progreso
<!-- Auto-actualizado por /worktree-tdd -->
<!-- Formato: [YYYY-MM-DD HH:MM] Fase X: estado — notas -->
