<local_issue>
#$ARGUMENTS
</local_issue>
1- Read issue file: `issues/$ARGUMENTS*.md` (glob by id prefix). If not found, stop and ask the user to create it with `/create-new-gh-issue`
2- git worktree add ./.trees/feature-issue-$ARGUMENTS -b feature-issue-$ARGUMENTS
3- Register the worktree in the guard hook: `mkdir -p .claude/.worktrees_active && echo "$(pwd)/.trees/feature-issue-$ARGUMENTS" > .claude/.worktrees_active/feature-issue-$ARGUMENTS`
4- cd .trees/feature-issue-$ARGUMENTS
5- activate plan mode on
6- analyze the local issue #$ARGUMENTS and determine with the @project-coordinator subagent what subagents from the folder @.claude/agents should be involved in implementing this issue. @project-coordinator should determine if the agents can run in parallel if there is no overlapping on tasks, even run parallel instances of the same agent if needed or possible, ALWAYS show the plan to the user to confirm.
7- Launch the subagents that the @project-coordinator subagent determined should be involved in implementing this issue, if the @project-coordinator subagent determined that the agents can run in parallel, launch them in parallel, if the @project-coordinator subagent determined that the agents can't run in parallel, launch them one by one
8- IMPORTANT: ALL file edits MUST use absolute paths within the worktree (`.trees/feature-issue-$ARGUMENTS/`). NEVER edit files in the main working tree.
9- At the end after the confirmation of the user, commit the changes locally and push the branch:
   ```bash
   git add -A && git commit -m "feat: implement issue #$ARGUMENTS"
   git push origin feature-issue-$ARGUMENTS
   ```
10- Create a PR from `feature-issue-$ARGUMENTS` → `main`:
    ```bash
    gh pr create \
      --title "feat: issue #$ARGUMENTS — {title from issue file}" \
      --body "$(cat <<'EOF'
    ## Summary
    Implements local issue #$ARGUMENTS

    ## Changes
    {brief list of what was implemented}

    ## Testing
    - All unit tests pass
    - See `.claude/doc/$ARGUMENTS/qa-report.md` for QA report
    EOF
    )"
    ```
11- Update `issues/$ARGUMENTS*.md` status to `in-review` and note the PR URL
12- Remove the sentinel: `rm -f .claude/.worktrees_active/feature-issue-$ARGUMENTS`
