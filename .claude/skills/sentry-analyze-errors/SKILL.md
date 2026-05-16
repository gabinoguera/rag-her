---
name: sentry-analyze-errors
description: Analiza los errores de Sentry en tres capas — técnica, UX y regresiones — y genera un informe priorizado por impacto real en usuarios. Puede sugerir issues locales para los problemas más críticos. Acepta periodo opcional (24h, 7d, 30d); por defecto 7d.
argument-hint: [24h|7d|30d]
disable-model-invocation: true
---

<input>
$ARGUMENTS
</input>

# /sentry-analyze-errors — Análisis de errores Sentry

Eres un analista de calidad y experiencia de usuario. Tu trabajo es leer los datos de Sentry, clasificar los errores por tipo e impacto, y presentar un informe accionable — no una lista de logs, sino conclusiones con contexto.

El input opcional es el periodo de análisis: `24h`, `7d` (default), o `30d`.

---

## Fase 1 — Setup

1. Parsear `$ARGUMENTS`:
   - Si vacío → periodo = `7d`
   - Si `24h` → `since=24h`
   - Si `7d` → `since=7d`
   - Si `30d` → `since=30d`

2. Obtener organización y proyecto:
   ```
   mcp__sentry__find_organizations
   mcp__sentry__find_projects
   ```
   Identificar el proyecto `her-poc` (o el nombre configurado en Sentry).

3. Obtener releases recientes para correlacionar regresiones:
   ```
   mcp__sentry__find_releases → últimas 5 releases con fecha
   ```

---

## Fase 2 — Recolección de datos (paralela)

Lanzar las siguientes queries **en paralelo**:

**A — Errores técnicos (volumen alto)**
```
mcp__sentry__search_issues
  query: "is:unresolved times_seen:>5"
  period: {PERIODO}
  limit: 20
```

**B — Errores que afectan a más usuarios únicos**
```
mcp__sentry__search_issues
  query: "is:unresolved"
  period: {PERIODO}
  sort: users
  limit: 20
```

**C — Errores de experiencia de usuario**
```
mcp__sentry__search_issues
  query: "is:unresolved level:error http.status_code:404"
  period: {PERIODO}
  limit: 10
```
```
mcp__sentry__search_issues
  query: "is:unresolved TimeoutError OR ConnectionError OR GeminiError OR SpeechError"
  period: {PERIODO}
  limit: 10
```

**D — Regresiones (errores nuevos desde el último deploy)**
```
mcp__sentry__search_issues
  query: "is:unresolved firstSeen:>{FECHA_ULTIMO_DEPLOY}"
  period: {PERIODO}
  limit: 15
```

Esperar que todas completen antes de continuar.

---

## Fase 3 — Análisis profundo de los top errores

Para los **5 errores con mayor impacto** (combinando frecuencia + usuarios únicos afectados):

```
mcp__sentry__analyze_issue_with_seer  → análisis AI del issue
mcp__sentry__search_issue_events      → ver eventos recientes del issue
mcp__sentry__get_issue_tag_values     → tags: url, user, browser, session_id, etc.
```

El objetivo es responder:
- ¿En qué endpoint o flujo ocurre? (`/api/v1/checkin/`, `/api/v1/ceo/`, `/api/v1/speech/`)
- ¿Afecta a un tipo de actor específico? (empleado en check-in, CEO en consulta)
- ¿Es nuevo o lleva tiempo sin resolverse?
- ¿Hay un patrón: siempre falla en el mismo paso del flujo?

---

## Fase 4 — Clasificación

Clasificar **todos** los errores encontrados en tres capas:

### Capa 1 — Errores técnicos
Excepciones, 500s, crashes. El usuario ve un error pero no sabe qué hizo mal.

Subtipos:
- `critical`: rompe funcionalidad core (check-in, CEO query, STT/TTS)
- `degraded`: funcionalidad parcial o respuesta incorrecta
- `silent`: error en background, el usuario no lo ve pero hay datos incorrectos (ej: embedding fallido)

### Capa 2 — Errores de experiencia de usuario (UX)
El sistema funciona pero el usuario tiene una mala experiencia.

Señales a detectar:
- **STT timeouts**: empleado grabando sin obtener transcripción → frustración
- **TTS failures**: CEO sin audio de respuesta → experiencia degradada
- **Gemini quota errors**: respuestas del CEO vacías o incompletas
- **Session not found**: empleado intentando continuar un check-in expirado
- **MediaRecorder errors**: navegador sin soporte, sin fallback visible

### Capa 3 — Regresiones
Errores que aparecieron después de un deploy reciente. Son urgentes porque tienen causa conocida.

---

## Fase 5 — Priorización

Ordenar todos los errores por **impacto real**:

```
Puntuación = (usuarios_únicos × 3) + (frecuencia × 1) + (es_regresión × 10) + (afecta_flujo_core × 5)
```

Flujos core de HER (penalización extra si los afectan):
- Check-in del empleado (start → answer × 3 → complete)
- Transcripción STT (audio → texto)
- Síntesis TTS (texto → audio)
- CEO query (pregunta → RAG → respuesta)
- CEO summary (briefing diario)

---

## Fase 6 — Generar informe

Crear `.claude/sessions/sentry_report_{FECHA}.md` con la estructura de la plantilla (`${CLAUDE_SKILL_DIR}/sentry-report-template.md`).

El informe debe incluir:
- Resumen ejecutivo (3-4 frases: qué está pasando)
- Top 3 errores a resolver YA con contexto completo
- Tabla completa priorizada
- Patrones de UX detectados
- Issues locales sugeridas para los críticos

---

## Fase 7 — Presentar y sugerir issues locales

Presentar el informe al usuario. Para cada error **crítico o regresión**:

Preguntar via `AskUserQuestion`:
> "¿Quieres crear una issue local para '[nombre del error]'?
> Afecta a [N] usuarios, ocurre en [endpoint/flujo], clasificado como [tipo]."

Si el usuario confirma → determinar el siguiente ID disponible en `issues/` y crear el fichero:
```bash
# Listar para obtener el siguiente ID
ls issues/ | sort | tail -5
```
```markdown
# Issue {next_id}: [Bug] {descripción corta}

**Type:** bug
**Status:** open

## Description
Error detectado via Sentry: {descripción}
Frecuencia: {N} veces. Usuarios afectados: {N}.
Endpoint/flujo: {url o flujo}.

## Acceptance Criteria
- El error no aparece en Sentry tras el fix
- El flujo afectado funciona correctamente end-to-end

## Notes
Link Sentry: {sentry_url}
Periodo detectado: {periodo}
```

---

## Reglas

- Nunca listar logs crudos — siempre interpretar y contextualizar
- Un error que afecta a 1 empleado 50 veces puede ser más urgente que uno que afecta a 50 usuarios 1 vez — evaluar el contexto
- Los errores de UX (STT/TTS fallos) son tan importantes como los técnicos
- Si Sentry no tiene datos suficientes para el periodo solicitado, reducir el scope y comunicarlo
- `AskUserQuestion` antes de crear cualquier issue local
- El informe se guarda en `.claude/sessions/` — no se publica automáticamente
- No usar `gh issue create` — las issues son ficheros locales en `issues/`
