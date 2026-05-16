<task_description>
#$ARGUMENTS
</task_description>
1- git worktree add ./.trees/feature-local-$ARGUMENTS -b feature-local-$ARGUMENTS
2- Register the worktree in the guard hook: `mkdir -p .claude/.worktrees_active && echo "$(pwd)/.trees/feature-local-$ARGUMENTS" > .claude/.worktrees_active/feature-local-$ARGUMENTS`
3- cd .trees/feature-local-$ARGUMENTS
4- activate plan mode on
5- analyze the task description (#$ARGUMENTS) and determine with the @project-coordinator subagent what subagents from the folder @.claude/agents should be involved in implement this task. @project-coordinator should determine if the agents can run in parallel if there is no overlapping on tasks, even run parallel instances of the same agent if is needed or possible, ALWAYS show the plan to the user to confirm.
6- Launch the subagents that the @project-coordinator subagent determined should be involved in implement this task, if the @project-coordinator subagent determined that the agents can run in parallel, launch them in parallel, if the @project-coordinator subagent determined that the agents can't run in parallel, launch them one by one
7- IMPORTANT: ALL file edits MUST use absolute paths within the worktree (`.trees/feature-local-$ARGUMENTS/`). NEVER edit files in the main working tree.
8- Generate implementation report in `.trees/feature-local-$ARGUMENTS/task_report.md` with:
   - Summary of requirements implemented
   - Requirements pending (if any)
   - Tests implemented and their run status
   - Proof that all builds pass
   - Overall completion status: [Needs More Work/All Completed]
9- At the end after the confirmation of the user, commit the changes locally (no push)
10- Remove the sentinel: `rm -f .claude/.worktrees_active/feature-local-$ARGUMENTS`
