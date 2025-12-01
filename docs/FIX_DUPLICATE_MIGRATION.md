# Fix Duplicate Migration Files

The migration files already exist in `archive/docs/migration/`, so we just need to remove the duplicates from `docs/migration/`.

## Solution

Since the files are already archived, we can safely delete the originals:

```powershell
# Remove the migration folder and its contents (files already archived)
Remove-Item -Path "docs\migration" -Recurse -Force
```

This will remove the duplicate files since they're already safely archived.
