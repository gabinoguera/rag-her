# Pre-merge Report: `[SOURCE]` → `[TARGET]`

**Fecha:** [YYYY-MM-DD HH:MM]
**Nivel de riesgo:** Bajo / Alto
**Backup DB:** N/A (PoC local) / ✅ Confirmado / ❌ No realizado

---

## Veredicto

> ✅ Merge viable — 0 bloqueantes
> ⚠️ Merge viable con acciones post-merge
> ❌ Merge bloqueado — resolver [N] items primero

---

## Análisis de ramas

| Métrica | Valor |
|---------|-------|
| Commits en SOURCE que TARGET no tiene | [N] |
| Commits en TARGET que SOURCE no tiene | [N] |
| Conflictos detectados | [N archivos / Ninguno] |
| Dirección recomendada | [SOURCE→TARGET directo / Primero TARGET→SOURCE] |

**Motivo de la dirección recomendada:**
[Explicación]

---

## 🔴 Bloqueantes

> Resolver antes de ejecutar el merge.

- [ ] [Item bloqueante 1 — quién lo detectó y qué hay que hacer]
- [ ] [Item bloqueante 2]

*(Ninguno si está vacío)*

---

## 🟡 Acciones requeridas post-merge

> Ejecutar en este orden tras el merge, antes de verificar el deploy.

- [ ] `alembic upgrade head` — [migraciones nuevas: lista]
- [ ] Verificar que pgvector extension existe: `CREATE EXTENSION IF NOT EXISTS vector`
- [ ] [Otra acción post-merge]

*(Ninguna si está vacío)*

---

## 🔵 Recomendaciones

> No bloqueantes, pero importantes para la estabilidad del deploy.

- [ ] [Recomendación 1]
- [ ] [Recomendación 2]

*(Ninguna si está vacío)*

---

## ✅ Verificaciones OK

- [x] Tests suite en verde
- [x] No hay conflictos de migración Alembic
- [x] [Otro item verificado]

---

## Informe por dominio

### `@backend-developer` — Migraciones & Modelos
[Informe completo del agente]

### `@mlops-engineer` — Infra & Deploy
[Informe completo del agente]

### `@vertex-ai-architect` — AI & Embeddings
[Informe completo del agente — "No aplica" si no hay cambios en AI]

---

## Secuencia de comandos

```bash
# 1. Asegurarse de estar actualizado
git fetch origin

# 2. [Si se recomienda actualizar SOURCE con TARGET primero]
git checkout {SOURCE}
git merge origin/{TARGET}
# Resolver conflictos si los hay, luego: git add . && git commit

# 3. Merge principal (vía PR en GitHub)
# gh pr merge {PR_NUMBER} --merge

# 4. Acciones post-merge (en orden)
alembic upgrade head
# [otros comandos según sección anterior]
```

---

## Plan de rollback

**Si el deploy falla (Cloud Run):**
```bash
gcloud run services update-traffic her-api \
  --to-revisions=PREVIOUS=100 \
  --region=europe-west1 \
  --project={GCP_PROJECT_ID}
```

**Si las migraciones Alembic rompen algo:**
- Estrategia: roll-forward only (crear nueva migración que corrija)
- Restaurar DB desde backup si está disponible

---

## Checklist post-deploy

- [ ] API responde en la URL de destino: `GET /health` → 200
- [ ] Frontend carga: `GET /` → landing page
- [ ] Check-in flow funciona: `POST /api/v1/checkin/start` → session_id
- [ ] CEO query funciona: `POST /api/v1/ceo/query` → respuesta
- [ ] Verificar Sentry: sin nuevos errores en los primeros 5 minutos
