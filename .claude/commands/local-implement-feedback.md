# Local Feedback Implementation Workflow for Task: $ARGUMENT$

## Setup Phase
1. Read task details from `.trees/task_plan_$ARGUMENT$.md`

## Analysis Phase
1. Read the full task description and requirements
2. Read the feedback from `.trees/feature-task-$ARGUMENT$/task_review.md`
3. Analyze the requirements, context, and feedback thoroughly

## Implementation Phase
1. Implement a plan to apply the changes needed for the feedback
2. Execute the plan step by step, remember to build test before the implementation and run the test suite constantly to get quick feedback.
3. Create always unit tests
4. Ensure consistency with existing code in the branch
5. Run local builds and tests suite before git commit
6. Never implement the manual tests
7. Update the task report: `.trees/feature-task-$ARGUMENT$/task_report.md`
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

## Important Notes
- All completed is the desired status and we can only arrive if we have implemented all the requirements and all the test suite are implemented and green otherwise we need more work until that happens
- Work entirely locally, no GitHub operations
- Keep detailed records in `.trees/feature-task-$ARGUMENT$/` directory
- Wait for explicit confirmation before proceeding with major changes

## Final checks
- Run all tests and verify they pass
- Update `.trees/feature-task-$ARGUMENT$/task_report.md` with what was implemented
- Commit changes locally (no push)
- Continue in loop until all tests are green
- Once all is green, report completion to Joan
