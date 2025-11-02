# CONTRIBUTING

Thank you for helping improve Modular Trade Agent. This guide explains how to work in the repo, the folder layout, and contribution rules.

## Project layout (top-level)
- src/ — application code
- documents/ — all documentation (organized)
  - getting-started/, architecture/, features/, deployment/, testing/, phases/, reference/
- scripts/ — developer and ops scripts
  - build/ — build and packaging PowerShell scripts
  - deploy/ — deployment helpers (gcp, windows, ubuntu)
- build/ — PyInstaller spec and build outputs
- logs/ — runtime logs; coverage HTML lives in logs/htmlcov
- tests/ — test suite
- temp/ — temporary testing scripts (local only, not for distribution)

## Common tasks
- Create venv (Windows): .\.venv\Scripts\python.exe -m pip install -r requirements.txt
- Run tests: .\.venv\Scripts\python.exe -m pytest -q
- Test with coverage HTML: .\.venv\Scripts\python.exe -m pytest --cov=. --cov-report=html (see logs/htmlcov/index.html)

## Build and packaging
- Windows executable build: scripts\build\build.ps1
- Installer build (EXE): scripts\build\build_installer.ps1
- Configure continuous Windows service (unified service): scripts\build\configure_continuous_service.ps1
- PyInstaller spec: build\build_executable.spec

## Deployment helpers
- Windows scheduled tasks scripts: scripts\deploy\windows\
- Ubuntu installers/tests: scripts\deploy\ubuntu\{installers,tests}\
- GCP helper assets: scripts\deploy\gcp\

## Documentation rules
- Place all docs under documents/ in the appropriate category.
- Update documents/README.md and documents/getting-started/DOCUMENTATION_INDEX.md when adding or moving docs.
- Keep quick-start docs in documents/getting-started/.
- Reference commands with Windows paths for consistency.

## Testing rules
- Always add/update unit tests for any new feature or bug fix (tests/).
- Run the full test suite before proposing a change.

## Commit policy
- Run tests before committing.
- Do not push without explicit approval.
- Keep commits scoped and descriptive (conventional style preferred: feat:, fix:, docs:, chore:, refactor:, test:).

## Coding practices
- Maintain SOLID principles.
- Prefer clear modular design, composition over inheritance.
- Adhere to existing patterns and module boundaries under src/.

## Temporary scripts
- Put throwaway or ad-hoc testing scripts in temp/ (do not commit sensitive data).

## Versioning
- We use CalVer (YY.Q.PATCH). See documents/reference/VERSION_MANAGEMENT.md.

## Where to find things quickly
- Commands reference: documents/reference/COMMANDS.md
- Health check: documents/deployment/HEALTH_CHECK.md (batch: scripts\health_check.bat)
- Oracle Cloud: documents/deployment/oracle/ORACLE_CLOUD_DEPLOYMENT.md
- Windows executable: documents/getting-started/WINDOWS_EXECUTABLE_GUIDE.md

## Opening changes
1) Create a branch.
2) Make changes with tests and docs.
3) Run tests locally.
4) Open a PR with a clear description and links to updated docs.
