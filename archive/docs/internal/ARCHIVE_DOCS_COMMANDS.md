# Commands to Archive Outdated Files in docs/

Run these commands to clean up the `docs/` folder.

## Step 1: Create Archive Directories

```powershell
New-Item -ItemType Directory -Path "archive\docs\internal" -Force
New-Item -ItemType Directory -Path "archive\docs\migration" -Force
New-Item -ItemType Directory -Path "archive\docs\refactoring" -Force
```

## Step 2: Archive Internal Documentation Cleanup Files

```powershell
Move-Item -Path "docs\ARCHIVE_COMMANDS.md" -Destination "archive\docs\internal\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "docs\ARCHIVE_PLAN.md" -Destination "archive\docs\internal\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "docs\ARCHIVE_SUMMARY.md" -Destination "archive\docs\internal\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "docs\DOCUMENTATION_CLEANUP_COMPLETE.md" -Destination "archive\docs\internal\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "docs\DOCUMENTATION_UPDATE_SUMMARY.md" -Destination "archive\docs\internal\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "docs\DOCUMENTS_REVIEW.md" -Destination "archive\docs\internal\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "docs\DOCS_FOLDER_REVIEW.md" -Destination "archive\docs\internal\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "docs\ARCHIVE_DOCS_COMMANDS.md" -Destination "archive\docs\internal\" -Force -ErrorAction SilentlyContinue
```

## Step 3: Archive Migration Documents

```powershell
Move-Item -Path "docs\migration\*" -Destination "archive\docs\migration\" -Force -ErrorAction SilentlyContinue
```

## Step 4: Review and Archive Refactoring Proposal (Optional)

```powershell
# Review first, then archive if outdated
Move-Item -Path "docs\refactoring\SHARED_SCHEDULER_REFACTOR_PROPOSAL.md" -Destination "archive\docs\refactoring\" -Force -ErrorAction SilentlyContinue
```

## Step 5: Verify What Remains

```powershell
Get-ChildItem -Path "docs" -File | Select-Object Name
```

## Expected Result

After cleanup, `docs/` should contain only:
- README.md
- GETTING_STARTED.md
- ARCHITECTURE.md
- API.md
- USER_GUIDE.md
- DEPLOYMENT.md
- engineering-standards-and-ci.md (if kept)
