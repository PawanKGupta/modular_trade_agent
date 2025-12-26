# Safe Mode Checklist

This workspace operates in Safe Mode:

- No destructive actions without explicit approval.
  - No `docker-compose down -v`, `docker system prune`, or deleting volumes/files.
  - No schema drops or irreversible DB changes.
- No Git commits or pushes without approval.
- Backup-first for any risky operation.
- Preflight confirmation required before proceeding.

## Preflight Steps
1. Summarize the intended change and commands.
2. Snapshot named volumes.
3. Confirm current container and volume state.
4. Get explicit approval.
5. Execute and verify.

## Named Volumes
- `trading_data` → `/app/data`
- `trading_logs` → `/app/logs`
- `paper_trading_data` → `/app/paper_trading`
- `postgres_data` → `/var/lib/postgresql/data`

## Approval Template
- Goal: <what>
- Impact: <risk level>
- Planned commands: <list>
- Backups: <where>
- Rollback: <how>
- Approval: YES/NO
