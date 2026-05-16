---
name: block-push-main
enabled: true
event: bash
pattern: git\s+push\s+(origin\s+)?(main|master)\b
action: block
---

**Push directo a main/master bloqueado**

Este proyecto usa branch strategy: `main` <- `develop` <- feature branches.
Nunca se debe hacer push directo a `main`.

**Flujo correcto:**
1. Trabaja en una feature branch
2. Abre un Pull Request hacia `develop`
3. Merge a `main` solo via PR aprobado

Usa `git push origin <tu-branch>` en su lugar.
