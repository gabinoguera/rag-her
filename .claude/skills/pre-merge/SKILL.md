---
name: pre-merge
description: Analiza la viabilidad de un merge entre ramas, orquestando @backend-developer, @mlops-engineer y @vertex-ai-architect en paralelo. Para merges a main incluye verificación de backup de Cloud SQL si está configurado. Genera un checklist ordenado por criticidad y propone la secuencia exacta de comandos.
argument-hint: <rama_origen> <rama_destino>
disable-model-invocation: true
---

<input>
$ARGUMENTS
</input>

# /pre-merge — Análisis de merge entre ramas

Eres un coordinador de releases. Tu trabajo es orquestar el análisis de un merge entre dos ramas, asegurar que todos los riesgos están identificados, y presentar al usuario un checklist claro antes de ejecutar ningún comando destructivo.

El input son dos ramas: `<origen> <destino>` (e.g. `feature-issue-001 main`).

---

## Fase 1 — Setup

1. Parsear `$ARGUMENTS`:
   - `SOURCE_BRANCH` = primera palabra
   - `TARGET_BRANCH` = segunda palabra
2. Determinar el **nivel de riesgo** según `TARGET_BRANCH`:
   - `main` → Nivel: **Alto** (verificar backup si Cloud SQL está configurado)
   - cualquier otra → Nivel: **Bajo**
3. Verificar que ambas ramas existen localmente:
   ```bash
   git branch -a | grep -E "{SOURCE_BRANCH}|{TARGET_BRANCH}"
   ```

---

## Fase 2 — Análisis de ramas

Ejecutar en paralelo:

```bash
# Commits que SOURCE tiene y TARGET no
git log --oneline origin/{TARGET_BRANCH}..origin/{SOURCE_BRANCH}

# Commits que TARGET tiene y SOURCE no
git log --oneline origin/{SOURCE_BRANCH}..origin/{TARGET_BRANCH}

# Archivos modificados en SOURCE respecto a TARGET
git diff --name-status origin/{TARGET_BRANCH}...origin/{SOURCE_BRANCH}

# Conflictos potenciales (simulación sin commitear)
git merge-tree $(git merge-base origin/{TARGET_BRANCH} origin/{SOURCE_BRANCH}) \
  origin/{TARGET_BRANCH} origin/{SOURCE_BRANCH} | grep -c "^<<<<<<" || echo "0 conflictos"
```

Determinar la **dirección de merge recomendada**:
- Si TARGET tiene commits que SOURCE no tiene → recomendar primero rebase/merge TARGET→SOURCE
- Si hay 0 conflictos → merge directo viable
- Si hay conflictos → listarlos explícitamente

---

## Fase 3 — Análisis paralelo por dominio

Lanzar los 3 agentes **en paralelo** (background), cada uno con el diff completo:

```bash
git diff origin/{TARGET_BRANCH}...origin/{SOURCE_BRANCH}
```

### `@backend-developer`
Analizar el diff y responder:
- ¿Hay migraciones Alembic nuevas? Listarlas
- ¿Son backwards-compatible? (no eliminan/renombran columnas usadas por el código de TARGET)
- ¿Hay conflictos de migración (múltiples heads en Alembic)?
- ¿Cambian los modelos SQLAlchemy de forma incompatible?
- ¿Hay nuevas variables de entorno que añadir a `.env.example`?
- ¿Hay riesgo de zero-downtime durante el deploy?

### `@mlops-engineer`
Analizar el diff y responder:
- ¿Cambiaron `cloudbuild.yaml`, `Dockerfile`, o `docker-compose.yml`?
- ¿Hay nuevas variables de entorno? ¿Están en Secret Manager (para producción)?
- ¿El `pyproject.toml` tiene nuevas dependencias con impacto en el build?
- ¿Cambia el mount point de `StaticFiles` (frontend)?
- Plan de rollback si el deploy falla: qué revisión de Cloud Run activar

### `@vertex-ai-architect`
Analizar el diff y responder:
- ¿Cambia `app/core/generation.py`, `embeddings.py`, o `prompts.py`?
- ¿Hay cambios en el modelo Gemini usado? Impacto en coste/latencia
- ¿Cambian los prompts del CEO o del check-in? ¿Son compatibles con datos ya vectorizados?
- ¿Cambia la dimensión del embedding (768d)? Requeriría re-indexar todos los check-ins
- ¿Cambia la lógica de re-ranking (similarity/recency weights)?

Esperar que **todos** completen antes de continuar.

---

## Fase 4 — Verificación de backup (solo si TARGET es main y Cloud SQL está activo)

Si `TARGET_BRANCH` es `main` y el proyecto tiene Cloud SQL configurado:

Usar `AskUserQuestion`:
> "El merge es a `main`. ¿Tienes un backup reciente de la base de datos antes de continuar?"
>
> Opciones: "Sí, tengo backup reciente" / "Voy a hacer el backup ahora" / "No aplica (PoC local)"

Si el usuario indica que es un entorno PoC local: continuar sin backup.

---

## Fase 5 — Consolidar checklist

Leer los informes de los 3 agentes y generar el checklist en `.claude/sessions/pre_merge_{SOURCE}_{TARGET}.md` siguiendo la plantilla (`${CLAUDE_SKILL_DIR}/pre-merge-template.md`).

Clasificar cada item:

| Nivel | Criterio | Color |
|-------|---------|-------|
| **Bloqueante** | Impide el merge; resolver primero | 🔴 |
| **Requerido post-merge** | Acción necesaria tras el merge (alembic upgrade, etc.) | 🟡 |
| **Recomendado** | Mejora la seguridad del deploy pero no es bloqueante | 🔵 |
| **Verificado OK** | Revisado y sin riesgo | ✅ |

Ejemplos:
- Conflictos de código → 🔴 Bloqueante
- Migración Alembic no backwards-compatible → 🔴 Bloqueante
- Nueva variable de entorno sin confirmar en `.env.example` → 🔴 Bloqueante
- Migración nueva (requiere `alembic upgrade head`) → 🟡 Requerido post-merge
- Cambio de modelo Gemini → 🔵 Recomendado (validar en staging primero)
- Tests en verde → ✅ OK

---

## Fase 6 — Presentar al usuario

Usar `AskUserQuestion` con:

1. **Resumen ejecutivo**: nivel de riesgo, nº de bloqueantes, nº de acciones post-merge
2. **Dirección de merge recomendada** (de Fase 2)
3. **Items bloqueantes** (si los hay)
4. **Secuencia exacta de comandos** para ejecutar el merge

Opciones:
- "Proceder con el merge" (solo si 0 bloqueantes)
- "Ver checklist completo"
- "Hay bloqueantes — cancelar"

Si hay bloqueantes: **NO ejecutar ningún comando de merge**.

---

## Fase 7 — Publicar checklist en PR

Buscar el PR asociado a la rama origen:

```bash
gh pr list --head {SOURCE_BRANCH} --json number,url --jq '.[0]'
```

Si existe PR → comentar el checklist:
```bash
gh pr comment {PR_NUMBER} --body-file .claude/sessions/pre_merge_{SOURCE}_{TARGET}.md
```

Si no existe PR → informar al usuario e indicar dónde está el fichero local.

---

## Reglas

- `AskUserQuestion` OBLIGATORIO antes de backup (Fase 4) y antes de merge (Fase 6)
- **NUNCA ejecutar merge sin confirmación explícita del usuario**
- Si hay items 🔴 Bloqueantes: el skill termina sin mergear
- El archivo de sesión `pre_merge_{SOURCE}_{TARGET}.md` NO se borra — sirve de auditoría
- Para entornos PoC locales (sin Cloud SQL), omitir la verificación de backup
