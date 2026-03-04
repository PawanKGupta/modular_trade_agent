"""
Check Alembic migration heads status
"""
from alembic.config import Config
from alembic.script import ScriptDirectory

config = Config("alembic.ini")
script = ScriptDirectory.from_config(config)

heads = script.get_heads()
print(f"Current heads in migration files: {heads}")
print(f"Number of heads: {len(heads)}")

if len(heads) > 1:
    print("\n[WARN] Multiple heads detected!")
    print("This will cause 'Multiple head revisions' error.")
    print("\nTo fix:")
    print("1. Ensure all merge migrations are in alembic/versions/")
    print("2. Run: alembic upgrade heads (to apply all)")
    print("3. Or target specific head: alembic upgrade a9b8c7d6e5f4")
else:
    print(f"\n[OK] Single head: {heads[0]}")
