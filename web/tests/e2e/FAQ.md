# E2E Tests - Frequently Asked Questions

## Database Questions

### Q: Do I need to use e2e.db for development, even in Docker?

**A: NO!** Docker should continue using `app.db` for development.

- **Docker/Development**: Use `app.db` (your normal development database)
- **E2E Tests**: Use `e2e.db` (separate test database)

The `e2e.db` is **ONLY** for E2E tests. Keep using `app.db` for:
- ✅ Normal development
- ✅ Docker containers
- ✅ Production deployment
- ✅ Manual testing in the UI

### Q: Why are there two databases?

**A: For test isolation and safety.**

Having separate databases means:
- ✅ E2E tests can reset/clear data without affecting your development data
- ✅ You can run Docker app and E2E tests simultaneously
- ✅ Test data doesn't interfere with your real development data
- ✅ You can safely experiment with test data

### Q: What if I want to use the same database for both?

**A: Not recommended, but possible.**

If you really want to use the same database:

1. **Set E2E_DB_URL to point to app.db:**
   ```powershell
   $env:E2E_DB_URL="sqlite:///./data/app.db"
   ```

2. **Warning**: This means:
   - Test data will mix with development data
   - Tests might modify/delete your development data
   - You can't run Docker and tests simultaneously safely
   - Tests will affect your development environment

**Better approach**: Keep them separate. Use `e2e.db` for tests, `app.db` for development.

### Q: Can I run Docker and E2E tests at the same time?

**A: YES!** That's the whole point of separate databases.

- Docker uses `app.db` → Your development environment
- E2E tests use `e2e.db` → Your test environment
- They don't interfere with each other

### Q: How do I know which database is being used?

**Check the environment variables:**

- **Docker/Development**: `DB_URL=sqlite:///./data/app.db`
- **E2E Tests**: `E2E_DB_URL=sqlite:///./data/e2e.db` (defaults to e2e.db)

The test runner scripts automatically set the correct database for tests.

## Seeding Questions

### Q: Where does seeded data go?

**A: Into `e2e.db` (the test database)**

Seeding script always seeds into the E2E test database, not your development database. This keeps your dev data safe.

### Q: Will seeding affect my Docker app data?

**A: NO.** Seeding only affects `e2e.db`, not `app.db`.

Your Docker app continues using `app.db` with your development data untouched.

### Q: How do I seed data for development?

**A: Don't use the E2E seeding script for development.**

For development:
- Use the UI to create data manually
- Use Docker/API to create data through normal application flows
- Use migration scripts if needed

The `seed-db.py` script is specifically for E2E test data.

## Test Execution Questions

### Q: Do I need to stop Docker before running tests?

**A: NO.** You can run both simultaneously.

- Docker uses `app.db` on port 8000
- Tests can start their own API server with `e2e.db` (if not already running)
- Or tests can use existing API server (as long as it's using `e2e.db`)

### Q: What if my API server is already running from Docker?

**A: Check which database it's using.**

If Docker is running and using `app.db`, then:
- E2E tests won't see seeded data (because it's in `e2e.db`)
- Tests might fail or behave unexpectedly

**Solution**: Use the test runner scripts which automatically start an API server with `e2e.db`, or stop Docker first.

## General Questions

### Q: Can I use e2e.db for development?

**A: Technically yes, but not recommended.**

If you use `e2e.db` for development:
- ✅ You'll see test data in your dev environment
- ❌ Test data might get mixed with real development data
- ❌ Running tests might clear/reset your development data
- ❌ Less clear separation between test and dev environments

**Better**: Keep using `app.db` for development, `e2e.db` for tests.

### Q: What's the recommended workflow?

**A: Recommended workflow:**

1. **Development**: Use Docker with `app.db`
   ```powershell
   docker-compose up
   # Uses app.db automatically
   ```

2. **Running E2E Tests**: Use test runner scripts
   ```powershell
   .\run-e2e-tests.ps1
   # Automatically uses e2e.db
   ```

3. **Seeding Test Data** (optional):
   ```powershell
   python web/tests/e2e/utils/seed-db.py --signals 10
   # Seeds into e2e.db
   ```

This keeps everything clean and separated!
