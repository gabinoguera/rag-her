<context_session_file>
#$ARGUMENTS
</context_session_file>

# Create New Local Issue
## Input
Feature/Bug/Chore plan: $ARGUMENTS

## Step 1: Analysis
- Analyze the feature/bug/chore idea provided
- Look at relevant context_session_file and code files to understand current and needed implementation
- Determine if this involves multiple features → if yes, go to **Step 1b: Epic**

## Step 1b: Epic (only when multiple features are involved)

If the request covers 2+ distinct features, note it as an Epic in the issue:
- Add an `## Epic` section listing child issues to be created
- Create one child issue file per feature, each referencing the parent: `Part of epic: {parent_id}`

**Parallelization safety check — run before defining child issues:**

For each pair of child issues, check if they touch overlapping files:
```bash
# Identify files each issue will likely modify
# (read the code, check models, services, api, tests)
```

Apply this rule:
> **Two issues CANNOT run in parallel if they modify the same file.**
> The second issue must wait until the first is merged into `main`.

In the Epic issue file, include an explicit dependency table:

| Issue | Depends on | Can start when |
|-------|-----------|----------------|
| {id-A} — Feature X | — | immediately |
| {id-B} — Feature Y | {id-A} | {id-A} merged into `main` |
| {id-C} — Feature Z | — | immediately (different files) |

If a dependency exists, state it clearly in the child issue file:
> ⚠️ **Dependency:** requires `{id-N}` merged into `main` before starting.

## Step 2: Draft Issue
Create an issue with this structure:

```markdown
# Issue {id}: {title}

**Type:** feature | bug | chore
**Status:** open

## Problem Statement
What problem does this solve? What are current limitations?

## User Value
What specific benefits will users get? Give concrete examples.

## Definition of Done
- Implementation complete with edge cases handled
- Unit tests added (>80% coverage)
- Integration tests for main flows
- Documentation updated
- All tests pass
- Manual testing complete

## Manual Testing Checklist
- Basic flow: [specific steps]
- Edge case testing: [specific scenarios]
- Error handling: [error scenarios to test]
- Integration: [test with existing features]

## Notes
[Optional context, constraints, references to docs/issues.md]
```

## Step 3: Review
Show me the complete issue draft and ask: "Is this ready to save? Any changes needed?"

Wait for my approval.

## Step 4: Save Issue
After approval, determine the next available issue ID by listing `issues/` directory and save the file:
```
issues/{id}-{slug}.md
```
e.g. `issues/003-checkin-flow-backend.md`

Tell me the file path when done.

## Remember
- Check actual code before suggesting solutions
- Use specific file names and paths
- Make testing steps concrete and actionable
- Focus on user benefits, not technical details
- Triage and use the correct term: feature, bug, or chore?
- Do NOT use `gh` CLI — there is no GitHub remote
