# Issue 006-03: Crear estructura base HTML + JS del frontend

**Type:** feature
**Status:** open
**Epic:** EPIC-006-frontend-hexagonal
**⚠️ Dependency:** requiere `006-02` completada (necesita style.css)

## Description
Crear los tres ficheros HTML y los dos módulos JS que componen el frontend del PoC, usando el design system extraído en `006-02`. El resultado es el frontend funcional completo servido por FastAPI.

## Files to create
```
adapters/primary/web/
├── index.html      ← landing con selector de rol
├── employee.html   ← check-in con grabación de voz
├── ceo.html        ← consulta CEO voz/texto
└── js/
    ├── employee.js ← flujo MediaRecorder + STT + check-in API
    └── ceo.js      ← query/summary + TTS playback
```

## Acceptance Criteria
- `index.html`: dos botones "Soy empleado" / "Soy dirección" con diseño del sistema extraído
- `employee.html`: progreso 1/3 → 2/3 → 3/3, botón de grabación, muestra transcripción, pantalla final de confirmación
- `ceo.html`: input texto + grabación, muestra respuesta, reproduce TTS, sección fuentes colapsable, botón "Briefing del día"
- Fallback: si MediaRecorder no disponible → mostrar input de texto alternativo
- Toast de error no bloqueante si la API no responde

## Definition of Done
- [ ] Los 3 HTML + 2 JS creados en `adapters/primary/web/`
- [ ] FastAPI sirve el frontend correctamente (`StaticFiles`)
- [ ] Flujo empleado completo: start → 3 respuestas → confirmación
- [ ] Flujo CEO completo: pregunta → respuesta → TTS reproduce

## Manual Testing Checklist
- Abrir `http://127.0.0.1:8000` → ver landing con selector de rol
- Clic "Soy empleado" → flujo de check-in con voz (o texto si no hay mic)
- Responder 3 preguntas → ver pantalla de confirmación
- Clic "Soy dirección" → hacer una pregunta al CEO → ver resumen + audio
- Probar "Briefing del día" → ver resumen del día
- Forzar error de red → ver toast no bloqueante

## Notes
Depende de `006-02` para tener el `style.css` disponible.
El JS debe usar `fetch` nativo (sin librerías). El audio usa `MediaRecorder` con `audio/webm;codecs=opus`.
