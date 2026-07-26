---
name: project-documentation
description: Use when implementation work changes behavior, setup, drivers, architecture, or developer workflow and the repository documentation must be reviewed and updated before the task is considered complete.
---

# Project Documentation Maintainer

Documentation updates are mandatory when implementation changes behavior or developer workflow.

## Review targets
- README.md
- DevelopmentGuide.md
- DevelopmentLog.md

## Documentation rules
### README.md
Ensure it contains:
- project purpose
- architecture summary
- main functions
- driver overview
- setup steps
- usage examples

### DevelopmentGuide.md
Ensure it contains:
- developer workflow
- file/module layout
- driver notes
- lint/test commands
- Raspberry Pi validation flow
- common troubleshooting notes

### DevelopmentLog.md
Append a dated entry with:
- task summary
- files changed
- why the change was made
- lint/test results
- Raspberry Pi validation status
- follow-up work

## Completion rule
If code changed and docs were not reviewed, the task is not complete.

## Tone and style
- Always provide clear step-by-step instructions for setup, testing, and validation.
- Give concise explanations of each step's purpose and expected outcome.
- Use plain and conversational wording that can be understood by non-technical users. If any professional jargon or abbreviations are necessary, explain them in simple terms.
- If any code examples are included, ensure they are copy-paste ready and well-commented for clarity.
