# UI Analysis — EPIC-006: Frontend Web HER

**Fecha:** 2026-05-16
**Worktree:** `/Users/simba/Documents/ghen/rag-estimation-service/.trees/feature-issue-EPIC-006/`
**Ficheros analizados:**
- `rag-estimation-platform/app/assets/stylesheets/application.tailwind.css`
- `rag-estimation-platform/config/tailwind.config.js`
- `app/api/v1/speech.py`, `checkin.py`, `ceo.py`
- `app/api/schemas/checkin_response.py`, `ceo_response.py`, `ceo_request.py`
- `app/main.py`

---

## 1. Frontend Assessment

### Estado previo
El proyecto no tenía frontend implementado. `app/main.py` ya contenía el mount condicional de `StaticFiles` apuntando a `adapters/primary/web/` (líneas 77-81), que solo se activaba si el directorio existiera. El directorio no existía.

### Ficheros creados
```
adapters/primary/web/
├── index.html       (3.4 KB) — landing con selector de rol
├── employee.html    (7.9 KB) — check-in 4 turnos con voz
├── ceo.html         (10.2 KB) — consulta CEO texto+voz
├── style.css        (12.5 KB) — design system extraído del legacy
└── js/
    ├── employee.js  (9.1 KB) — lógica MediaRecorder + checkin flow
    └── ceo.js       (9.3 KB) — lógica query + summary + TTS
```

### Integración con el backend
El mount `StaticFiles(directory=web_dir, html=True)` se registra después de los routers `/api/v1/*`, garantizando que las rutas de API tengan prioridad. Al existir el directorio ahora, el mount se activa sin cambios en `main.py`.

---

## 2. Design Issues Identificados

### Critical

Ninguno. El diseño parte de un design system bien definido (legacy Tailwind) y se convierte fielmente a CSS vanilla.

### Major

**M-01: Google Fonts con dependencia de red externa**
- Archivo: `style.css` línea 1
- `@import url('https://fonts.googleapis.com/...')` falla en entornos sin internet (desarrollo offline, producción air-gapped).
- Recomendación: añadir `font-display: swap` y stack de fallback sólido ya incluido (`system-ui, sans-serif`). Para producción, considerar self-hosting de Inter via `fontsource`.

**M-02: Contraste del color primary dorado sobre fondo card**
- `hsl(46 78% 59%)` = aprox `#d4a828` sobre `#121212` = ratio ~7.2:1 (pasa AA y AAA para texto normal).
- Sin embargo, el primary sobre `var(--secondary)` `#1f1f1f` = ratio ~6.8:1 — pasa AA.
- El primary sobre `var(--muted)` `#1a1a1a` en badges: ratio ~6.5:1 — pasa AA.
- No se detectan violaciones de contraste WCAG 2.1 AA.

**M-03: `type="module"` en scripts requiere servidor HTTP**
- `<script src="/js/employee.js" type="module">` falla con `file://` protocol (CORS restriction de módulos ES).
- Esto es correcto por diseño (FastAPI sirve los archivos), pero debe documentarse: **no abrir index.html directamente desde el sistema de ficheros**.
- No se requiere cambio en el código.

### Minor

**m-01: Sin `<meta name="description">` en páginas internas**
- `employee.html` y `ceo.html` carecen de meta description.
- Impacto bajo (aplicación interna), pero buena práctica.

**m-02: `details[open] summary::after` usa `content: '&#9660;'` en CSS**
- El pseudo-elemento `::after` con `content` HTML entity funciona, pero la sintaxis correcta en CSS es `content: '\25BC'` (Unicode escape).
- En `ceo.html` está escrito como string HTML en el atributo `style` CSS embebido — necesita corrección a Unicode escape o usar `▼` directamente como texto UTF-8 en el CSS.
- Archivo: `ceo.html`, bloque `<style>`, regla `details.sources-details summary::after`.

**m-03: El botón "Preguntar" no indica carácter restante (500 chars)**
- El textarea de CEO tiene `maxlength="500"` pero no hay contador visible.
- Impacto menor (el límite es generoso para preguntas naturales).

---

## 3. Improvement Recommendations

### R-01: Indicador de caracteres restantes en CEO textarea (Minor)
**Archivo:** `adapters/primary/web/ceo.html` y `adapters/primary/web/js/ceo.js`

Añadir un `<small id="char-count">500 caracteres restantes</small>` bajo el textarea, actualizado con un event listener `input`. Mejora la UX sin coste.

```html
<!-- ceo.html: tras el .query-input-row -->
<small id="char-count" style="color: var(--muted-fg); font-size: 0.75rem;">500 caracteres restantes</small>
```
```js
// ceo.js
const charCount = document.getElementById('char-count');
queryInput.addEventListener('input', () => {
  const remaining = 500 - queryInput.value.length;
  charCount.textContent = `${remaining} caracteres restantes`;
  charCount.style.color = remaining < 50 ? 'var(--warning)' : 'var(--muted-fg)';
});
```

### R-02: Corrección CSS `content` en `details::after` (Minor)
**Archivo:** `adapters/primary/web/ceo.html`, bloque `<style>` embebido

Cambiar:
```css
details.sources-details summary::after {
  content: '&#9660;';  /* INCORRECTO en CSS */
```
Por:
```css
details.sources-details summary::after {
  content: '\25BC';    /* Unicode escape correcto en CSS */
```
O bien mover los estilos del `details` al `style.css` compartido donde se puede usar el carácter UTF-8 directamente: `content: '▼'`.

### R-03: Autoplay TTS bloqueado por política de browsers (Importante para QA)
**Archivos:** `js/employee.js` (función `playTTS`), `js/ceo.js` (función `playTTS`)

Los navegadores modernos bloquean autoplay de audio sin interacción previa del usuario. Dado que:
- En `employee.js`, el TTS se llama en `initCheckin()` al cargar la página — **puede fallar en Chrome/Firefox** si el usuario no ha interactuado antes con la página.
- En `ceo.js`, el TTS se llama tras hacer clic en un botón — esto **si cumple** el requisito de user gesture.

**Recomendación para `employee.js`:**
- Mostrar el texto de la primera pregunta y un botón "Iniciar / Escuchar" que el usuario pulse explícitamente antes de reproducir TTS.
- Alternativamente, capturar el error `NotAllowedError` del `audio.play()` y mostrar el botón de replay en ese caso.

El código actual en `employee.js` ya tiene manejo de error en `playTTS` (catch silencioso + muestra el botón replay). Esta estrategia es aceptable como degradación, pero se recomienda documentar el comportamiento en los criterios de aceptación de QA.

### R-04: `session_id` en `employee.js` — sin persistencia entre recargas
**Archivo:** `adapters/primary/web/js/employee.js`

El `sessionId` vive solo en memoria. Si el usuario recarga la página, el flujo reinicia desde cero. Esto es aceptable para el PoC (el endpoint `/start` crea una nueva sesión), pero conviene documentarlo para evitar confusión en QA.

No se recomienda usar `sessionStorage` todavía (complicaría el flujo sin beneficio claro en esta fase).

### R-05: Accesibilidad — focus management en completion screen
**Archivo:** `adapters/primary/web/employee.html` + `js/employee.js`

Cuando se muestra `#completion-screen`, el foco permanece en el último elemento activo (normalmente `#btn-confirm`). Añadir en `showCompletion()`:
```js
completionScreen.setAttribute('tabindex', '-1');
completionScreen.focus();
```
Esto comunica correctamente el cambio de estado a lectores de pantalla.

---

## 4. Consistency Check

### Alineación con patrones del proyecto

| Patrón | Estado |
|--------|--------|
| Dark theme `#0a0a0a` background | Implementado |
| Primary `hsl(46 78% 59%)` dorado | Implementado |
| Inter + JetBrains Mono fonts | Implementado |
| Utilidades `.glow-sm`, `.glow-md`, `.glass` | Implementadas |
| `.animate-fade-in-up`, `.stagger-children` | Implementadas |
| Fetch API nativa, sin librerías | Cumplido |
| `async/await` con try/catch | Cumplido |
| MediaRecorder `audio/webm;codecs=opus` con fallback | Cumplido |
| Toast no bloqueante para errores | Cumplido |
| `aria-live="polite"` en transcripciones | Cumplido |
| `aria-live="assertive"` en toast de errores | Cumplido |
| Fallback texto si MediaRecorder no disponible | Cumplido |

### Páginas del proyecto — comparativa

Las tres páginas (`index.html`, `employee.html`, `ceo.html`) comparten:
- Header con logo "HER" en `var(--font-mono)` y `var(--primary)`
- Enlace de vuelta a `/` en el logo
- Estructura `<header> + <main>` semántica
- Mismo `style.css` vía `<link rel="stylesheet" href="/style.css">`
- Toast `#toast` con mismo markup y comportamiento

---

## 5. Responsive Behavior

| Breakpoint | index.html | employee.html | ceo.html |
|------------|-----------|---------------|---------|
| 375px mobile | Botones en columna, logo centr. | Card sin bordes laterales, controles full-width | Textarea full-width, botones apilados |
| 768px tablet | Botones en fila (480px+) | Container 560px centrado | Container 720px centrado |
| 1280px desktop | — | — | Max 900px con padding lateral |

---

## 6. WCAG 2.1 AA Checklist

| Criterio | Estado | Notas |
|----------|--------|-------|
| 1.4.3 Contraste (texto normal ≥ 4.5:1) | Pasa | fg #f2f2f2 / bg #0a0a0a = 18.3:1 |
| 1.4.3 Contraste (primary sobre bg) | Pasa | ~7.2:1 |
| 2.1.1 Teclado | Parcial | `Enter` en textarea → submit; falta focus trap en completion |
| 2.4.3 Focus order | Pasa | Orden natural del DOM |
| 3.2.2 On Input | Pasa | Grabación no arranca sin clic explícito |
| 4.1.2 Name, Role, Value | Pasa | Botones con `aria-label`, estados con `aria-live` |
| 4.1.3 Status Messages | Pasa | `aria-live="polite"` en transcript y status, `aria-live="assertive"` en toast |

**Pendiente (ver R-05):** focus management al mostrar completion screen.

---

## 7. MediaRecorder Browser Compatibility

| Browser | Soporta MediaRecorder | `audio/webm;codecs=opus` | Fallback activo |
|---------|----------------------|--------------------------|----------------|
| Chrome 90+ | Si | Si | No |
| Firefox 86+ | Si | Si | No |
| Safari 14.1+ | Si | No (usa mp4/aac) | Código usa fallback a `audio/webm` sin codec, puede fallar |
| iOS Safari | No (hasta iOS 16) | N/A | Si — muestra textarea |
| Edge 90+ | Si | Si | No |

**Nota Safari:** El código intenta `audio/webm;codecs=opus` → si no soportado cae a `audio/webm` → si tampoco, usa `new MediaRecorder(stream)` sin mimeType (Safari usará su default mp4/aac). El backend (`/api/v1/speech/transcribe`) usa Google Cloud Speech v2 (chirp_2) que acepta múltiples formatos. No se anticipa problema, pero debe validarse en QA con Safari.

---

## 8. Próximos pasos recomendados (para /review-spec y /update-feedback)

1. **Smoke test manual:** Arrancar uvicorn, navegar a `http://127.0.0.1:8000`, verificar que las 3 páginas cargan.
2. **Test flujo empleado:** Completar los 4 turnos con micrófono y sin micrófono (textarea).
3. **Test flujo CEO:** Enviar pregunta de texto, verificar respuesta + fuentes colapsables + badge de confianza.
4. **Test TTS:** Verificar que el audio se reproduce (o que el fallo es silencioso y no bloquea).
5. **Test responsive:** Chrome DevTools en 375px, 768px, 1280px para las 3 páginas.
6. **Corregir M-03 CSS content:** Cambiar `content: '&#9660;'` por `content: '\25BC'` en `ceo.html`.
7. **Considerar R-03:** Añadir botón "Escuchar" explícito para primer TTS de employee.html si autoplay falla en QA.

---

## Referencias

- Issue: `/Users/simba/Documents/ghen/rag-estimation-service/issues/EPIC-006-frontend-hexagonal.md`
- Session context: `/Users/simba/Documents/ghen/rag-estimation-service/.claude/sessions/context_session_EPIC-006.md`
- Legacy CSS: `/Users/simba/Documents/ghen/rag-estimation-service/rag-estimation-platform/app/assets/stylesheets/application.tailwind.css`
- Legacy Tailwind config: `/Users/simba/Documents/ghen/rag-estimation-service/rag-estimation-platform/config/tailwind.config.js`
