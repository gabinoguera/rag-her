# Sentry Error Report — [FECHA]

**Periodo analizado:** [24h / 7d / 30d]
**Último deploy:** [versión y fecha]
**Total errores únicos:** [N]
**Total usuarios afectados:** [N]

---

## Resumen Ejecutivo

[3-4 frases describiendo el estado de salud de la app. ¿Hay regresiones? ¿Algún flujo crítico (check-in, CEO query, STT/TTS) en problemas? ¿Tendencia al alza o a la baja?]

---

## 🔴 Top 3 — Resolver YA

### 1. [Nombre del error]

| Campo | Valor |
|-------|-------|
| Tipo | Técnico / UX / Regresión |
| Frecuencia | [N veces] |
| Usuarios afectados | [N únicos] |
| Endpoint / Flujo | [ej: POST /api/v1/checkin/answer, flujo STT] |
| Actor afectado | Empleado / CEO / Ambos |
| Primera vez visto | [fecha] |
| Link Sentry | [URL] |

**Qué está pasando:**
[Explicación en lenguaje humano — no el stack trace, sino qué experimenta el usuario]

**Causa probable:**
[Hipótesis técnica]

**Acción sugerida:**
[Qué habría que hacer para resolverlo]

---

### 2. [Nombre del error]
[Mismo formato]

---

### 3. [Nombre del error]
[Mismo formato]

---

## Tabla Completa Priorizada

| # | Error | Tipo | Frecuencia | Usuarios | Endpoint/Flujo | Prioridad |
|---|-------|------|-----------|---------|----------------|-----------|
| 1 | [nombre] | Técnico/UX/Regresión | [N] | [N] | [flujo] | 🔴/🟡/🔵 |
| 2 | | | | | | |

---

## Patrones de UX Detectados

> Comportamientos repetidos que indican fricción en la experiencia, no errores individuales.

### [Patrón 1 — ej: "Empleados con STT fallando en el segundo intento"]
- **Señal**: [qué muestra Sentry]
- **Impacto**: [qué experimenta el usuario]
- **Hipótesis**: [por qué está pasando]
- **Sugerencia**: [cambio de UX o código que lo mejoraría]

### [Patrón 2]
[Mismo formato]

---

## Regresiones (errores nuevos desde último deploy)

| Error | Primera vez | Deploy relacionado | Impacto |
|-------|------------|-------------------|---------|
| [nombre] | [fecha] | [versión] | [N usuarios] |

---

## Issues Locales Sugeridas

| Error | Fichero sugerido | Creada |
|-------|-----------------|--------|
| [nombre] | `issues/{id}-[slug].md` | ✅ / ⬜ Pendiente |

---

## Notas

[Observaciones adicionales, contexto sobre tendencias, o errores conocidos que se pueden ignorar]
