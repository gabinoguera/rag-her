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
