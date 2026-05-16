---
name: review-spec
description: Compara la spec técnica (sección ## Technical Spec del fichero issues/{id}.md) contra lo implementado en el PR. Detecta desviaciones, escala decisiones de producto al usuario, y añade el veredicto al fichero de issue + comenta en el PR. Ejecutar entre /worktree-tdd y /update-feedback.
argument-hint: <issue_id>
disable-model-invocation: true
---

<input>
$ARGUMENTS
</input>

# /review-spec — Spec vs Implementación

Eres un revisor técnico. Tu trabajo es comparar lo que se planificó (spec de la issue) contra lo que se ha implementado (PR diff), detectar desviaciones, escalar las que requieren decisión de producto, y emitir un veredicto antes de que arranque QA.

El input es el ID de la issue `N`.

---

## Fase 1 — Setup

1. Leer el fichero de la issue completo: `issues/{N}*.md`
   - La spec está al final del fichero bajo `## Technical Spec`
   - Si no existe esa sección, usar el body del issue como spec mínima
   - Extraer las secciones: **Implementation Phases**, **MoSCoW**, **Appendix**
2. Obtener el PR asociado a la issue:
   ```bash
   gh pr list --head feature-issue-{N} --json number,title,url
   ```
3. Obtener el diff del PR:
   ```bash
   gh pr diff {PR_NUMBER}
   ```
4. Obtener los archivos modificados en el PR:
   ```bash
   gh pr view {PR_NUMBER} --json files
   ```

---

## Fase 2 — Comparativa Implementation Phases

Para cada fila de la tabla **Implementation Phases** de la spec:

1. Extraer el nombre de la fase y los archivos/clases mencionados en Description
2. Buscar evidencia en el PR diff
3. Clasificar el estado de cada fase:
   - ✅ **OK** — evidencia clara en el diff, enfoque coincide con lo planificado
   - ⚠️ **Approach Change** — está implementado pero de forma diferente
   - ❌ **Missing** — planificado pero sin evidencia en el diff
   - 🔒 **Descoped** — explícitamente excluido (Won't del MoSCoW)

---

## Fase 3 — Comparativa MoSCoW Must

Para cada ítem **Must** del MoSCoW de la spec:

1. Buscar evidencia en el diff que cubra esa capacidad
2. Clasificar: ✅ Cubierto / ❌ Sin evidencia / ⚠️ Parcialmente cubierto

---

## Fase 4 — Detectar Scope Creep

Revisar los archivos modificados en el PR contra el Appendix (Files to Create / Files to Edit):
- Archivos **en el diff pero no en la spec** → candidatos a scope creep
- Excluir: `alembic/versions/`, `tests/`, `conftest.py` (siguen el patrón TDD normal)

---

## Fase 5 — Clasificar y escalar desviaciones

| Tipo | Definición | Acción |
|------|-----------|--------|
| **Scope Creep relevante** | Cambios no planificados que afectan a otras áreas | Escalar: `AskUserQuestion` |
| **Missing bloqueante** | Must del MoSCoW sin implementar | Escalar: `AskUserQuestion` |
| **Missing no bloqueante** | Should/Could sin implementar | Documentar, no escalar |
| **Approach Change OK** | Diferente implementación, mismo resultado | Documentar, no escalar |
| **Approach Change dudoso** | Cambio de enfoque con implicaciones de diseño | Escalar: `AskUserQuestion` |

Para cada desviación a escalar, usar `AskUserQuestion` indicando:
- Qué se planificó
- Qué se implementó (o falta)
- Opciones: "Aceptar el cambio" / "Requiere ajuste antes de QA" / "Descartar del scope"

**Esperar respuesta** del usuario para cada desviación escalada antes de emitir el veredicto.

---

## Fase 6 — Emitir veredicto y publicar

Construir el informe de review y **añadirlo al final** de `issues/{N}-{slug}.md` como nueva sección:

```markdown
---

## Implementation Review
**Fecha:** [YYYY-MM-DD]
**Veredicto:** ✅ Apto para QA / ⚠️ Apto con notas / ❌ Bloqueado

[contenido del review siguiendo la plantilla]
```

Usar el contenido de `${CLAUDE_SKILL_DIR}/review-spec-template.md` como estructura de esa sección.

**Veredicto posible:**
- ✅ **Apto para QA** — scope cubierto, sin bloqueantes
- ⚠️ **Apto para QA con notas** — approach changes aceptadas o should/could descoped
- ❌ **Bloqueado para QA** — hay Must sin implementar o scope creep no aceptado

Publicar el review como comentario en el **PR**:
```bash
# Extraer solo la sección ## Implementation Review del fichero y comentar
gh pr comment {PR_NUMBER} --body "$(sed -n '/^## Implementation Review/,$p' issues/{N}-{slug}.md)"
```

Reportar al usuario:
```
Review añadido a issues/{N}-{slug}.md
Review publicado en PR #{PR_NUMBER}
Veredicto: [✅ Apto / ⚠️ Apto con notas / ❌ Bloqueado]

[Si apto]: Siguiente paso: /update-feedback {N}
[Si bloqueado]: Corregir los bloqueantes y volver a ejecutar /review-spec {N}
```

---

## Reglas

- `AskUserQuestion` SOLO para decisiones de producto (Missing bloqueantes, Scope Creep relevante, Approach Changes dudosos)
- Si el veredicto es ❌ Bloqueado, NO continuar a `/update-feedback`
- El archivo `issues/{N}-{slug}-review.md` **no se borra** — es contexto para `/update-feedback`
- Publicar siempre en el **PR**, nunca en GitHub Issues (las issues son locales)
- Los archivos de test y migraciones Alembic no cuentan como scope creep
- Si no existe spec `issues/{N}*-spec.md`, usar el body de `issues/{N}*.md` como referencia
