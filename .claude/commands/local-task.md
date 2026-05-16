# Local Task Workflow for Task: $ARGUMENT$

## Setup Phase
1. Read task description from context or user input

## Worktree Phase (if you are not now in a ./trees folder)
1. git worktree add ./.trees/feature-task-$ARGUMENT$ -b feature-task-$ARGUMENT$
2- cd .trees/feature-task-$ARGUMENT$

## Analysis Phase
1. Read the full task description and requirements
2. Analyze the requirements and context thoroughly

## Implementation Phase
1. Execute the plan step by step, remember to build test before the implementation and run the test suite constantly to get quick feedback.
2. Create always unit tests
3. Ensure consistency with existing code in the branch
4. Run local builds and tests suite before git commit
5. Never implement the manual tests
6. Document changes in a local file: `.trees/feature-task-$ARGUMENT$/task_report.md`
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

8. Commit changes locally (no push)

## Important Notes
- All completed is the desired status and we can only arrive if we have implemented all the requirements and all the test suite are implemented and green otherwise we need more work until that happens
- Work entirely locally, no GitHub operations
- Keep detailed records in `.trees/feature-task-$ARGUMENT$/` directory
- Wait for explicit confirmation before proceeding with major changes

## Final checks
- Run all tests and verify they pass
- Document what was implemented in `.trees/feature-task-$ARGUMENT$/task_report.md`
- Commit changes locally
- Report completion status to Joan
