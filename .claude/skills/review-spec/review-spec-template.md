# Review Spec: [Título] — #[N]

**Issue local:** `issues/[N]*.md`
**PR:** [PR URL]
**Fecha:** [YYYY-MM-DD]
**Spec de referencia:** `.claude/sessions/issue_spec_[N].md` del [fecha de la spec]

---

## Veredicto

> ✅ Apto para QA / ⚠️ Apto para QA con notas / ❌ Bloqueado para QA

[Justificación en 1-2 frases]

---

## Comparativa: Implementation Phases

| # | Fase Planificada | Archivos/Clases Clave | Evidencia en PR | Estado |
|---|-----------------|----------------------|-----------------|--------|
| 1 | [de la spec] | [clases/archivos esperados] | [archivos modificados relevantes] | ✅/⚠️/❌/🔒 |

**Leyenda:** ✅ OK · ⚠️ Approach Change · ❌ Missing · 🔒 Descoped

---

## Comparativa: MoSCoW Must

| Capability (Must) | Evidencia en PR | Estado |
|-------------------|-----------------|--------|
| [de la spec] | [evidencia o ausencia] | ✅/⚠️/❌ |

---

## Desviaciones Detectadas

### 🆕 Scope Creep
[Archivos modificados no planificados con potencial impacto. "Ninguno" si no hay.]

### ❌ Missing
[Fases o Must sin evidencia de implementación. "Ninguno" si no hay.]

### ⚠️ Approach Changes
[Cambios de enfoque respecto a lo planificado. Indicar si se han aceptado o no.]

---

## Decisiones Tomadas

[Decisiones del usuario ante desviaciones escaladas. Formato:]

| Desviación | Planificado | Implementado | Decisión del usuario |
|-----------|-------------|--------------|---------------------|
| [nombre] | [spec] | [actual] | Aceptado / Requiere ajuste / Descartado |

---

## Notas para QA

[Contexto específico para `/update-feedback`: qué approach changes se aceptaron, qué should/could quedaron fuera de scope, qué áreas requieren atención especial durante el testing.]
