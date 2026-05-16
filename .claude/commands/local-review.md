# Local Review Workflow for Task: $ARGUMENT$

## Setup Phase
1. Read task details from `.trees/task_plan_$ARGUMENT$.md` or task description

## Analysis Phase
1. Read the full task content and requirements
2. Analyze the requirements, context, and any feedback thoroughly
3. Read implementation report from `.trees/feature-task-$ARGUMENT$/task_report.md` if exists

## Review Phase
1. use @qa-criteria-validator agent to provide feedback over the manual test required and the use cases described in the task plan
2. Document the feedback in `.trees/feature-task-$ARGUMENT$/task_review.md`

## Decision over feedback
1. if the report from @qa-criteria-validator shows all tests pass, document "TASK READY TO MERGE" in the review file
2. if the report from @qa-criteria-validator has missing fixes, document the feedback and needed changes

## Important Notes
- Work entirely locally, no GitHub operations
- Keep detailed records in `.trees/feature-task-$ARGUMENT$/` directory
- All feedback stored in local markdown files
