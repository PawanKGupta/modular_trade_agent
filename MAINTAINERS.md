# MAINTAINERS

This file documents ownership, maintenance processes, and the current repo layout for quick onboarding.

## Ownership
- Tech Owner: TBA
- Docs Owner: TBA
- Release Owner: TBA

Update this section as roles are assigned.

## Maintenance checklist
- Keep documentation organized under `documents/` and update indexes after moves.
- Run test suite locally before merging: `.\.venv\Scripts\python.exe -m pytest -q`.
- Generate coverage HTML when touching critical paths: `--cov-report=html` (output: `logs/htmlcov`).
- Do not push without explicit approval.
- Keep temp experiments in `temp/` and remove stale files regularly.

## Repository layout (summary)
- `src/` — core source code
- `documents/` — all docs (architecture, deployment, features, testing, getting-started, phases, reference)
- `scripts/` — developer ops and deployment helpers
  - `scripts/build/` — build.ps1, build_installer.ps1, configure_continuous_service.ps1
  - `scripts/deploy/` — windows/, ubuntu/{installers,tests}/, gcp/
- `build/` — PyInstaller specs and build outputs
- `logs/` — runtime logs and `htmlcov/` coverage reports
- `tests/` — unit/integration tests
- `temp/` — temporary testing scripts

## Conventions
- Windows-first command examples and paths (use `\\` separators in docs).
- CalVer versioning (YY.Q.PATCH); see `documents/reference/VERSION_MANAGEMENT.md`.
- Use SOLID and clean modular design.

## Release process (high level)
1. Ensure VERSION is bumped (CalVer).
2. Update docs (changelog, index, any affected guides).
3. Run full tests; verify coverage not regressed in critical modules.
4. Build installer/executable if applicable.
5. Tag release and prepare distribution artifacts.

For contribution workflow see `CONTRIBUTING.md`.
