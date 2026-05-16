---
name: block-dangerous-rm
enabled: true
event: bash
pattern: rm\s+(-rf|-fr|--recursive\s+--force)\s
action: block
---

**Comando rm destructivo bloqueado**

`rm -rf` puede causar perdida irreversible de datos del proyecto.

**Alternativas:**
- Elimina archivos individuales: `rm archivo.py`
- Usa `git clean -n` (dry-run) para ver que se eliminaria
- Mueve a papelera: `mv archivo /tmp/`
- Pide confirmacion explicita al usuario antes de eliminar directorios
