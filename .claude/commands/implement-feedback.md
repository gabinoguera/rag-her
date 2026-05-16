# Local Feedback Implementation Workflow for Issue #$ARGUMENT$

## Setup Phase
1. Read issue file: `issues/$ARGUMENT$*.md`
2. Read task details from `.trees/task_plan_$ARGUMENT$.md` (if exists)

## Analysis Phase
1. Read `issues/$ARGUMENT$*.md` completo — el feedback está en la sección `## QA Report` al final
2. Read current implementation report from `.trees/feature-issue-$ARGUMENT$/task_report.md`
4. Analyze the requirements, context, and feedback thoroughly

## Implementation Phase
1. Implement a plan to apply the changes needed to address the feedback
2. Execute the plan step by step, remember to build test before the implementation and run the test suite constantly to get quick feedback.
3. Create always unit tests
4. Ensure consistency with existing code in the branch
5. Run local builds and test suite before git commit
6. Never implement the manual tests
7. Update the task report: `.trees/feature-issue-$ARGUMENT$/task_report.md`
8. Report status of completeness:

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

9. Run all tests again to verify everything passes
10. If some tests fail, check the problems and implement the fixes, repeating in a loop until all tests are green
11. Commit and push updates to the feature branch (the open PR auto-updates):
    ```bash
    git add -A && git commit -m "fix: address QA feedback for issue #$ARGUMENT$"
    git push origin feature-issue-$ARGUMENT$
    ```

## Important Notes
- All completed is the desired status and we can only arrive if we have implemented all the requirements and all the test suite are implemented and green otherwise we need more work until that happens
- Issues are local (`issues/*.md`) — do NOT use `gh issue` CLI
- PRs are on GitHub — pushing to the feature branch auto-updates the open PR
- Keep detailed records in `.trees/feature-issue-$ARGUMENT$/` directory
- Wait for explicit confirmation before proceeding with major changes

## Final checks
- Run all tests and verify they pass
- Update `.trees/feature-issue-$ARGUMENT$/task_report.md` with what was implemented
- Push to feature branch (PR updates automatically)
- Continue in loop until all tests are green
- Once all is green, report completion with PR URL
