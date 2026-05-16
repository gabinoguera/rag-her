# Issue 006-01: Actualizar docs y agentes al path hexagonal del frontend

**Type:** chore
**Status:** open
**Epic:** EPIC-006-frontend-hexagonal

## Description
Actualizar todas las referencias a `frontend/` por `adapters/primary/web/` en la documentación y en el agente `ui-ux-analyzer`. Refleja la decisión de posicionar el frontend como adaptador primario en la arquitectura hexagonal.

## Acceptance Criteria
- `docs/issues.md` Epic 6 usa `adapters/primary/web/` en todos los paths
- `app/main.py` monta `StaticFiles(directory="adapters/primary/web", html=True)`
- `.claude/agents/ui-ux-analyzer.md` referencia `adapters/primary/web/` en sus Key File Locations
- No queda ninguna referencia a `frontend/` en docs ni agentes

## Definition of Done
- [ ] `docs/issues.md` actualizado
- [ ] `app/main.py` actualizado (solo el mount point, sin otros cambios)
- [ ] `ui-ux-analyzer.md` actualizado
- [ ] Búsqueda de `frontend/` en el repo no devuelve falsos positivos

## Manual Testing Checklist
- `grep -r "directory=\"frontend\"" app/` → sin resultados
- `grep -r "frontend/" docs/` → sin resultados (excepto referencias históricas)

## Notes
Puede ejecutarse en paralelo con `006-02` ya que tocan ficheros distintos.
