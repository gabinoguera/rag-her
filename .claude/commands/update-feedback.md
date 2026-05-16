# Local QA Workflow for Issue #$ARGUMENT$

## Setup Phase

1. Read issue file: `issues/$ARGUMENT$*.md` — contiene todo: descripción, spec (## Technical Spec) y review (## Implementation Review)
2. Read implementation report: `.trees/feature-issue-$ARGUMENT$/task_report.md` (if exists)
3. Read `.claude/sessions/context_session_$ARGUMENT$.md` for accumulated context
4. Verify the local dev server is running at `http://127.0.0.1:8000` before continuing
   ```bash
   curl -s http://127.0.0.1:8000/health -o /dev/null -w "%{http_code}"
   # Expected: 200
   ```

## TC Classification Phase

Invoke `@qa-criteria-validator` with:
- Full issue content + implementation report
- Notes from `context_session_$ARGUMENT$.md`
- Instruction **exclusive** to this phase: **classify TCs, do not execute yet**

`@qa-criteria-validator` must return a classification table:

| TC | Description | Type | Reason |
|----|-------------|------|--------|
| TC-1 | [description] | **Parallel** | No dependency on prior state |
| TC-2 | [description] | **Parallel** | Different role, independent state |
| TC-3 | [description] | **Sequential** | Requires TC-1 completed first |

**Parallelization criteria:**
- **Parallel**: TC has no dependency on state created by another TC, uses a different role, or tests a fully independent route
- **Sequential**: TC needs prior state, shares a session, or must execute in a specific order

## Parallel Execution Phase

Launch `@qa-criteria-validator` to execute tests with the following strategy:

**Parallel TCs** — use `concurrent-browser`:
- Create one browser instance per parallel TC: `mcp__concurrent-browser__browser_create_instance`
- Run all in parallel (background), each executing its TC independently
- Each instance reports result (pass/fail + evidence) independently

**Sequential TCs** — use standard Playwright MCP in the defined order.

Wait for **all** (parallel + sequential) to complete.

Close all concurrent-browser instances when done:
```
mcp__concurrent-browser__browser_close_all_instances
```

## Results Classification Phase

For each failed TC, classify as:

| Type | Criteria | Action |
|------|----------|--------|
| **Bug** | Code error, failed assertion, deterministic unexpected behavior | Auto-fix: invoke `/local-implement-feedback $ARGUMENT$` |
| **Functional** | UX ambiguity, product decision, subjective criteria | Escalate: `AskUserQuestion` |

## Auto-fix Loop (max 3 cycles)

If there are **Bug** type failures:

1. Invoke `/local-implement-feedback $ARGUMENT$` with the list of bugs to fix
2. Wait for completion
3. Re-run the **Parallel Execution Phase** in full
4. Increment cycle counter (cycle 1 → 2 → 3)

If after 3 cycles bugs remain:
- **Do not continue the loop**
- Document persistent bugs
- Write final QA report (see next phase)
- Escalate to user via `AskUserQuestion`

## Report Phase

Añadir el QA report al final de `issues/$ARGUMENT$*.md` como nueva sección:

```markdown
---

## QA Report
**Fecha:** [YYYY-MM-DD]
**Resultado:** ✅ Todo OK / ⚠️ Ciclos agotados con fallos persistentes

### TCs Ejecutados
| TC | Tipo Ejecución | Resultado |
|----|---------------|-----------|
| TC-1 | Paralelo | ✅ Pass |
| ... | ... | ... |

### Bugs Corregidos (ciclos de auto-fix)
[Lista de bugs resueltos en los ciclos, o "Ninguno"]

### Bugs Persistentes (si aplica)
[Lista de bugs que no se pudieron resolver en 3 ciclos]

### Ciclos de auto-fix: [0/1/2/3]
```

Update `.claude/sessions/context_session_$ARGUMENT$.md` noting QA complete.

Post the QA section as a comment on the open PR:
```bash
PR_NUMBER=$(gh pr list --head feature-issue-$ARGUMENT$ --json number -q '.[0].number')
gh pr comment $PR_NUMBER --body "$(sed -n '/^## QA Report/,$p' issues/$ARGUMENT$*.md)"
```

**If all OK** → update the issue file status to `ready-to-merge` and add a PR approval comment:
```bash
gh pr comment $PR_NUMBER --body "✅ QA passed — all TCs green. Ready to merge."
```

**If persistent bugs** → do NOT mark as ready-to-merge. Post findings on PR and escalate to user.

## Important Notes

- The local dev server must be active at `http://127.0.0.1:8000` before any test
- Always close all concurrent-browser instances when done (success or error)
- Functional failures do NOT enter the auto-fix loop — always escalate
- The 3-cycle limit is per `update-feedback` session; it does not accumulate
- Issues are local (`issues/*.md`) — do NOT use `gh issue` CLI
- PRs are on GitHub — use `gh pr` CLI for comments and status only
