---
name: block-migration-delete
enabled: true
event: bash
pattern: rm\s+.*migrations/\d
action: block
---

**Eliminacion de migracion bloqueada**

Las migraciones de Django son roll-forward only. Nunca se deben eliminar archivos de migracion.

**Reglas del proyecto:**
- NUNCA eliminar o hacer rollback de migraciones
- Las nuevas migraciones deben ser backwards-compatible
- Si hay conflictos: `python manage.py makemigrations --merge`
- Documenta cambios en el docstring de la migracion

Consulta la seccion "Database Migrations Safety" en CLAUDE.md.
