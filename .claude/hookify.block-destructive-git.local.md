---
name: block-destructive-git
enabled: true
event: bash
pattern: git\s+(push\s+--force|push\s+-f\s|reset\s+--hard|clean\s+-fd|checkout\s+--\s+\.|restore\s+--staged\s+\.|branch\s+-D)
action: block
---

**Operacion git destructiva bloqueada**

Se ha detectado un comando git que puede causar perdida de datos irreversible:
- `git push --force` — sobrescribe historial remoto
- `git reset --hard` — descarta commits y cambios locales
- `git clean -fd` — elimina archivos no rastreados
- `git checkout -- .` / `git restore --staged .` — descarta cambios masivamente
- `git branch -D` — elimina rama sin verificar merge

**Alternativas seguras:**
- Usa `git stash` en lugar de `git reset --hard`
- Usa `git push --force-with-lease` si realmente necesitas forzar
- Elimina archivos individuales en lugar de `git clean -fd`
- Pide confirmacion explicita al usuario antes de proceder
