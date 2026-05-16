# Local Issue Workflow for Issue #$ARGUMENT$

## Setup Phase
1. Read issue file: `issues/$ARGUMENT$*.md` (glob by id prefix if full filename not provided)
   - If the file does not exist, stop and ask the user to create it with `/create-new-gh-issue`
2. Extract issue title and slug for branch naming

## Worktree Phase (if you are not now in a ./.trees folder)
1. `git worktree add ./.trees/feature-issue-$ARGUMENT$ -b feature-issue-$ARGUMENT$`
2. `cd ./.trees/feature-issue-$ARGUMENT$`

## Analysis Phase
1. Read the full issue content from `issues/$ARGUMENT$*.md`
2. Analyze the requirements and context thoroughly
3. Create `.claude/sessions/context_session_$ARGUMENT$.md` with issue summary and initial notes

## Implementation Phase
1. Execute the plan step by step, remember to build test before the implementation and run the test suite constantly to get quick feedback.
2. Create always unit tests
3. Ensure consistency with existing code in the branch
4. Run local builds and test suite before git commit
5. Never implement the manual tests
6. Document changes in `.trees/feature-issue-$ARGUMENT$/task_report.md`
7. Report status of completeness:

<results>

  # Summary of the requirements implemented:
	- req 1
        - req 2
	- ...

  # Requirements pending
	- req 1
        - req 2
	- ...
  # Test implemented and their run status
     ok    path/to/test_file.py       Xs

  # Proof that all build passes
     ok    all tests passed            Xs

  # Overall status: [Needs More Work/All Completed]
</results>

8. Commit and push the feature branch:
   ```bash
   git add -A && git commit -m "feat: implement issue #$ARGUMENT$"
   git push origin feature-issue-$ARGUMENT$
   ```
9. Create a PR from `feature-issue-$ARGUMENT$` → `main`:
   ```bash
   gh pr create \
     --title "feat: issue #$ARGUMENT$ — {title from issue file}" \
     --body "$(cat <<'EOF'
   ## Summary
   Implements local issue #$ARGUMENT$

   ## Changes
   {brief list of what was implemented}

   ## Testing
   - All unit tests pass
   - See `issues/$ARGUMENT$*.md` (## QA Report section) for QA report
   EOF
   )"
   ```
10. Update the issue file: change `**Status:** open` to `**Status:** in-review`, add the PR URL

## Important Notes
- All completed is the desired status and we can only arrive if we have implemented all the requirements and all the test suite are implemented and green otherwise we need more work until that happens
- Issues are local (`issues/*.md`) — do NOT use `gh issue` CLI
- PRs are on GitHub — use `gh pr` CLI for creating and tracking
- Keep detailed records in `.trees/feature-issue-$ARGUMENT$/` directory
- Wait for explicit confirmation before proceeding with major changes

## Final checks
- Run all tests and verify they pass
- Document what was implemented in `.trees/feature-issue-$ARGUMENT$/task_report.md`
- Push branch and open PR
- Update `issues/$ARGUMENT$*.md` status to `in-review`
- Report completion status with PR URL
