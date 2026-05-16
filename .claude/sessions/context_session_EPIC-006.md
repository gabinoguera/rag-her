# Context Session — EPIC-006: Frontend Web (Adaptador Primario Hexagonal)

## Estado
**Fase:** Implementación completada (PASO 1 spec + PASO 2 implementación + PASO 3 verificación)
**Branch:** feature-issue-EPIC-006
**Worktree:** `/Users/simba/Documents/ghen/rag-estimation-service/.trees/feature-issue-EPIC-006/`

## Descripción
Frontend vanilla HTML/JS ubicado en `adapters/primary/web/` como adaptador primario hexagonal.
Sin frameworks ni bundlers. FastAPI sirve los estáticos condicionalmente (ya configurado en `app/main.py`).

## Ficheros implementados

| Fichero | Descripción |
|---------|-------------|
| `adapters/primary/web/index.html` | Landing con selector de rol (Soy empleado / Soy dirección) |
| `adapters/primary/web/employee.html` | Check-in 4 turnos: progreso, grabación voz, transcripción, fallback texto |
| `adapters/primary/web/ceo.html` | Consulta CEO: textarea + voz, query + summary, respuesta + fuentes colapsables |
| `adapters/primary/web/style.css` | Design system completo: tokens del legacy, componentes, animaciones |
| `adapters/primary/web/js/employee.js` | Lógica empleado: MediaRecorder, STT, checkin API, TTS |
| `adapters/primary/web/js/ceo.js` | Lógica CEO: query, summary, grabación voz, TTS, toast errors |

## Design tokens (extraídos de legacy)
- Background: `#0a0a0a` (hsl 0 0% 4%)
- Foreground: `#f2f2f2` (hsl 0 0% 95%)
- Primary: `hsl(46 78% 59%)` (dorado)
- Card: `#121212`
- Border: `#242424`
- Fuentes: Inter + JetBrains Mono (Google Fonts)

## API endpoints consumidos
- `POST /api/v1/checkin/start` → `{ session_id, question_text }`
- `POST /api/v1/checkin/{session_id}/answer` body `{ answer_text }` → `{ next_question_text, is_complete, employee_name }`
- `POST /api/v1/ceo/query` body `{ question }` → `{ answer, confidence, sources }`
- `GET  /api/v1/ceo/summary` → `{ summary, checkins_count, period }`
- `POST /api/v1/speech/transcribe` multipart → `{ transcript, confidence }`
- `POST /api/v1/speech/synthesize` body `{ text }` → `audio/mpeg`

## FastAPI StaticFiles
Ya configurado en `app/main.py` líneas 77-81:
```python
web_dir = os.path.join(os.path.dirname(__file__), "..", "adapters", "primary", "web")
if os.path.isdir(web_dir):
    from fastapi.staticfiles import StaticFiles
    application.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
```
El directorio ahora existe → el mount se activa automáticamente al arrancar uvicorn.

## Documentos relacionados
- Issue: `/Users/simba/Documents/ghen/rag-estimation-service/issues/EPIC-006-frontend-hexagonal.md`
- UI Analysis: `/Users/simba/Documents/ghen/rag-estimation-service/.claude/doc/EPIC-006/ui_analysis.md`

## Notas importantes
- Los scripts JS usan `type="module"` — requieren servidor HTTP (no file://)
- MediaRecorder: fallback a textarea visible si `!window.MediaRecorder` o permiso denegado
- TTS failures son no-fatales: se loguean a console.warn pero no bloquean el flujo
- Toast auto-dismiss a los 4s para errores no bloqueantes
- CORS en main.py permite solo `localhost:3000` en development — el frontend en FastAPI es mismo origen, no necesita CORS
