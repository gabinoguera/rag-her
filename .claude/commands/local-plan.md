<context_session_file>
#$ARGUMENTS
</context_session_file>

# Create Local Task Plan

## Input
Feature/Bug/Chore plan: $ARGUMENTS

## Step 1: Analysis
- Analyze the feature/bug/chore idea provided
- Look at relevant context_session_file and code files to understand current and needed implementation

## Step 2: Draft Plan
Create a plan document with this structure:

### Problem Statement
What problem does this solve? What are current limitations?

### User Value
What specific benefits will users get? Give concrete examples.

### Definition of Done
- Implementation complete with edge cases handled
- Unit tests added (>80% coverage)
- Integration tests for main flows
- Documentation updated
- Code review ready
- All tests pass
- Manual testing complete

### Manual Testing Checklist
- Basic flow: [specific steps]
- Edge case testing: [specific scenarios]
- Error handling: [error scenarios to test]
- Integration: [test with existing features]

## Step 3: Review
Show me the complete plan draft and ask: "Is this ready to implement? Any changes needed?"

Wait for approval.

## Step 4: Save Plan
After approval, save to:
`.trees/task_plan_$ARGUMENTS.md`

Tell me when done and ready to proceed.

## Remember
- Check actual code before suggesting solutions
- Use specific file names and paths
- Make testing steps concrete and actionable
- Focus on user benefits, not technical details
- Triage and use the correct term: it's a feature, a bug or a chore?
