---
name: block-drop-database
enabled: true
event: bash
pattern: (DROP\s+(TABLE|DATABASE)|python\s+manage\.py\s+flush|python\s+manage\.py\s+reset_db|sqlite3.*\.delete|rm\s+.*db\.sqlite3)
action: block
---

**Operacion destructiva de base de datos bloqueada**

Se detecto un comando que puede eliminar datos de la base de datos:
- `DROP TABLE/DATABASE` — elimina tablas/BD completa
- `manage.py flush` — vacia todas las tablas
- `manage.py reset_db` — elimina y recrea la BD
- Eliminar `db.sqlite3` — destruye la BD local

**Alternativas:**
- Usa migraciones Django para cambios de esquema
- Usa `manage.py migrate` para aplicar cambios
- Haz backup antes: `cp db.sqlite3 db.sqlite3.bak`
- Para revertir datos de prueba, usa fixtures
