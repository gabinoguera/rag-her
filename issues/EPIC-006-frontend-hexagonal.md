# EPIC-006: Frontend Web (Adaptador Primario Hexagonal)

**Status:** open
**Espera a:** EPIC-003, EPIC-004, EPIC-005
**Issues hijas:** 006-01, 006-02, 006-03

## Descripción
Interfaz HTML/JS vanilla ubicada en `adapters/primary/web/` (adaptador primario en arquitectura hexagonal). Selector de rol en landing, vista empleado con grabación de voz, vista CEO con consulta voz/texto. Design system extraído del frontend legacy.

## Estructura objetivo
```
adapters/
└── primary/
    └── web/
        ├── index.html       ← landing con selector de rol
        ├── employee.html    ← check-in con grabación
        ├── ceo.html         ← consulta CEO
        ├── style.css        ← design tokens extraídos del legacy
        └── js/
            ├── employee.js
            └── ceo.js
```

FastAPI sirve el frontend con:
```python
app.mount("/", StaticFiles(directory="adapters/primary/web", html=True), name="web")
```

## Tareas
- **006-01** — Actualizar docs + agentes (path `adapters/primary/web/`)
- **006-02** — Extraer design system del legacy → `adapters/primary/web/style.css`
- **006-03** — Crear estructura base HTML + JS
- FE-01 — Configurar `StaticFiles` en `app/main.py`
- FE-02 — `index.html` landing con selector de rol
- FE-03 — `employee.html` vista check-in con voz
- FE-04 — `ceo.html` vista consulta CEO
- FE-05 — Error handling (STT fallo, API caída, MediaRecorder no soportado)

## Paralelización interna

| Tarea | Paralelo con | Espera a |
|-------|-------------|---------|
| 006-01 | 006-02 | — |
| 006-02 | 006-01 | — |
| 006-03 | — | 006-02 |
| FE-01 | — | 006-01 |
| FE-02 | FE-03, FE-04 | FE-01, 006-02 |
| FE-03 | FE-02, FE-04 | FE-01, 006-02 |
| FE-04 | FE-02, FE-03 | FE-01, 006-02 |
| FE-05 | — | FE-02, FE-03, FE-04 |

---

## Technical Spec

### 1. Executive Summary

Frontend vanilla HTML/JS ubicado en `adapters/primary/web/` como adaptador primario en arquitectura hexagonal. Sin frameworks ni bundlers: HTML5 semántico, CSS custom properties, fetch API nativa. FastAPI sirve los ficheros estáticos condicionalmente (el directorio ya está montado en `app/main.py`). Tres páginas: landing con selector de rol, vista empleado con flujo conversacional de 4 turnos usando MediaRecorder, y vista CEO con consulta RAG voz+texto.

### 2. MoSCoW

#### Must Have
- **Landing (`index.html`)**: selector de rol con dos botones "Soy empleado" / "Soy dirección"
- **Employee (`employee.html`)**: flujo de 4 turnos con grabación MediaRecorder (audio/webm), indicador de progreso, transcripción visible, fallback a texto si MediaRecorder no disponible
- **CEO (`ceo.html`)**: input texto + grabación opcional, botón "Preguntar" (POST /api/v1/ceo/query), botón "Briefing del día" (GET /api/v1/ceo/summary), reproducción TTS automática, sección fuentes colapsable
- **Error handling**: toast no bloqueante para errores STT, API caída, MediaRecorder no soportado

#### Should Have
- Reproducción TTS de preguntas en el flujo empleado
- Indicador visual de estado (idle / grabando / procesando / reproduciendo)
- Transcripción visible para que el usuario confirme lo que se oyó

#### Could Have
- Animaciones de entrada (fade-in-up del design system legacy)
- Replay de audio para escuchar la pregunta de nuevo

#### Won't Have (esta iteración)
- Autenticación / login
- PWA / service workers
- Internacionalización (solo español)

### 3. Design Tokens

Extraídos de `rag-estimation-platform/app/assets/stylesheets/application.tailwind.css` y `rag-estimation-platform/config/tailwind.config.js`:

```css
/* Variables CSS — convertidas de hsl() a valores concretos */
--background:        #0a0a0a;   /* hsl(0 0% 4%) */
--foreground:        #f2f2f2;   /* hsl(0 0% 95%) */
--card:              #121212;   /* hsl(0 0% 7%) */
--card-foreground:   #f2f2f2;
--primary:           hsl(46 78% 59%);   /* dorado — #d4a828 aprox */
--primary-fg:        #0a0a0a;
--secondary:         #1f1f1f;   /* hsl(0 0% 12%) */
--secondary-fg:      #cccccc;
--muted:             #1a1a1a;   /* hsl(0 0% 10%) */
--muted-fg:          #8c8c8c;   /* hsl(0 0% 55%) */
--border:            #242424;   /* hsl(0 0% 14%) */
--destructive:       hsl(0 62% 50%);
--success:           hsl(152 60% 42%);
--warning:           hsl(38 92% 50%);
--radius:            0.625rem;

/* Tipografía */
--font-sans: 'Inter', system-ui, sans-serif;
--font-mono: 'JetBrains Mono', monospace;

/* Google Fonts import */
/* https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap */
```

**Utilidades a implementar en CSS puro** (sin Tailwind):
- `.glow-sm` — `box-shadow: 0 0 15px -3px hsl(46 78% 59% / 0.15)`
- `.glow-md` — `box-shadow: 0 0 30px -5px hsl(46 78% 59% / 0.2)`
- `.glass` — `background: rgba(18,18,18,0.8); backdrop-filter: blur(8px); border: 1px solid rgba(36,36,36,0.5)`
- `.animate-fade-in-up` — keyframe `fade-in-up`: `opacity 0→1, translateY(12px)→0, 0.3s ease-out`
- `.stagger-children > *` — delays escalonados: 0.05s, 0.1s, 0.15s, 0.2s, 0.25s

### 4. Estructura de ficheros

```
adapters/
└── primary/
    └── web/
        ├── index.html          ← landing con selector de rol
        ├── employee.html       ← check-in conversacional (4 turnos)
        ├── ceo.html            ← consulta CEO (texto+voz, RAG, TTS)
        ├── style.css           ← design system extraído del legacy
        └── js/
            ├── employee.js     ← lógica check-in: MediaRecorder + fetch
            └── ceo.js          ← lógica CEO: query + summary + TTS
```

### 5. Contratos de API usados

#### Employee flow (4 turnos)

```
POST /api/v1/checkin/start
  → { session_id: string, question_text: string }

POST /api/v1/checkin/{session_id}/answer
  body: { answer_text: string }
  → { next_question_text: string|null, is_complete: bool, employee_name: string|null }
```

Turn 1 captura el nombre del empleado. Turnos 2-4 son preguntas de check-in. `is_complete: true` en el turn 4 indica flujo terminado; `employee_name` se devuelve en ese momento.

#### CEO

```
POST /api/v1/ceo/query
  body: { question: string }     (max 500 chars)
  → { answer: string, confidence: "alta"|"media"|"baja"|"sin_datos", sources: [{employee_name, date, excerpt}] }

GET /api/v1/ceo/summary
  → { summary: string, checkins_count: int, period: string }
```

#### Speech

```
POST /api/v1/speech/transcribe
  multipart/form-data: audio (UploadFile)
  → { transcript: string, confidence: float }

POST /api/v1/speech/synthesize
  body: { text: string }         (max 5000 chars)
  → audio/mpeg binary
```

### 6. Integración FastAPI — StaticFiles

Ya configurado en `app/main.py` (líneas 77-81):

```python
web_dir = os.path.join(os.path.dirname(__file__), "..", "adapters", "primary", "web")
if os.path.isdir(web_dir):
    from fastapi.staticfiles import StaticFiles
    application.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
```

La condición `os.path.isdir(web_dir)` significa que el mount solo ocurre si el directorio existe. Crear el directorio activa la funcionalidad automáticamente. Las rutas de API `/api/v1/*` tienen prioridad porque el router se registra antes del mount.

### 7. Notas de implementación

#### `index.html`
- Fondo oscuro full-viewport, logo "HER" centrado (tipografía grande, color primary dorado)
- Dos botones con clase `.role-btn`: "Soy empleado" navega a `/employee.html`, "Soy dirección" navega a `/ceo.html`
- `<main>` con `display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh`

#### `employee.html` + `js/employee.js`
- Al cargar: `POST /api/v1/checkin/start` → guarda `session_id` en variable JS, muestra `question_text` en el DOM
- Indicador de progreso: `<div class="progress-bar">` con 4 pasos numerados (aria-label="Progreso del check-in")
- Botón de grabación: `<button id="btn-record" class="record-btn">` con estados idle/grabando/procesando
- `getUserMedia({ audio: true })` → `new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })`
- Al detener grabación: `Blob` → `FormData` → `POST /api/v1/speech/transcribe` → muestra transcripción en `#transcript`
- El usuario confirma: automáticamente envía transcript a `POST /api/v1/checkin/{session_id}/answer`
- Si `is_complete: true`: muestra pantalla de confirmación con `employee_name`
- Fallback MediaRecorder: si `!window.MediaRecorder` → muestra `<input type="text" id="text-fallback">` en lugar del botón mic
- TTS de preguntas: después de recibir `question_text`, `POST /api/v1/speech/synthesize` → `new Audio(URL.createObjectURL(blob)).play()`
- Turn counting: variable `currentTurn` (0→4), actualiza el indicador de progreso en cada respuesta exitosa

#### `ceo.html` + `js/ceo.js`
- Layout de dos columnas en desktop, una columna en mobile
- Input de texto `<textarea id="query-input">` + botón "Hablar" (grabación opcional)
- Botones: "Preguntar" (POST query) y "Briefing del día" (GET summary)
- Área de respuesta `#answer-area`: texto + badge de confianza coloreado (alta=verde, media=amarillo, baja=rojo, sin_datos=gris)
- Sección fuentes `<details id="sources-section">` colapsable con `<summary>Fuentes (N)</summary>`
- TTS automático tras recibir respuesta: POST synthesize → new Audio().play()
- Toast `#toast` con `role="alert" aria-live="assertive"`, auto-dismiss a los 4s
- Grabación: mismo patrón MediaRecorder que employee.js, sin confirmación manual (transcript se pone directamente en textarea)

#### Accesibilidad WCAG 2.1 AA
- Todos los botones tienen `aria-label` descriptivo
- Estados de grabación comunicados via `aria-live="polite"` en `#status-label`
- Transcripción en `aria-live="polite"` en `#transcript`
- Contraste: foreground #f2f2f2 sobre background #0a0a0a = 18.3:1 (pasa AAA)
- Primary dorado sobre fondo oscuro: verificar ratio ≥ 4.5:1 para texto normal
- Focus visible con `outline: 2px solid var(--primary)`

#### Responsive (mobile 375px / tablet 768px / desktop 1280px)
- Mobile: layout columna única, botones full-width
- Tablet: contenedor max-width 600px centrado
- Desktop: contenedor max-width 800px, CEO con sidebar de fuentes opcional

### 8. Criterios de aceptación

- `GET /` devuelve `index.html` con código 200
- `GET /employee.html` devuelve la página de check-in
- `GET /ceo.html` devuelve la página CEO
- Flujo empleado completa 4 turnos sin error en navegador con micrófono disponible
- Fallback de texto visible cuando MediaRecorder no está disponible
- CEO puede enviar pregunta de texto y ver respuesta + fuentes
- TTS reproduce audio después de cada respuesta sin bloquear la UI
- Toast de error aparece y desaparece a los 4s ante fallo de API
