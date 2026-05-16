---
name: block-pr-to-main
enabled: true
event: bash
pattern: gh\s+pr\s+create.*--base\s+main|gh\s+pr\s+create.*-B\s+main
action: block
---

🚨 **PR directo a `main` bloqueado**

El flujo correcto es:

```
worktree → rama de trabajo (feature/fix/...) → gabriel/develop/staging
```

**Nunca** se crea un PR apuntando directamente a `main`.

`main` solo recibe merges desde `gabriel` (o la rama de staging equivalente) una vez que el trabajo ha sido revisado, testeado y aprobado.

**Para corregir el comando:**
- Cambia `--base main` por `--base gabriel` (u otra rama base correcta)
- Ejemplo: `gh pr create --base gabriel --head <tu-rama> ...`
