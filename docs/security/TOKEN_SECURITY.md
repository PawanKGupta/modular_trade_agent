# Token and Credential Security

## Overview

This document outlines the security measures implemented to prevent accidental exposure of sensitive authentication tokens, API keys, and credentials in logs, outputs, or version control.

## Security Utilities

### Location
`modules/kotak_neo_auto_trader/utils/security_utils.py`

### Available Functions

#### 1. `mask_sensitive_value(value, visible_chars=4)`
Masks a sensitive string, showing only first/last few characters.

```python
from modules.kotak_neo_auto_trader.utils.security_utils import mask_sensitive_value

token = "my_secret_token_12345"
masked = mask_sensitive_value(token, visible_chars=4)
# Result: "my_s...2345"
```

#### 2. `mask_token_in_dict(data, sensitive_keys=None)`
Recursively masks sensitive keys in dictionaries.

```python
from modules.kotak_neo_auto_trader.utils.security_utils import mask_token_in_dict

response = {
    "user": "john",
    "token": "secret_token_123",
    "data": {"session_token": "jwt_123"}
}
safe_response = mask_token_in_dict(response)
# Result: {"user": "john", "token": "sec...123", "data": {"session_token": "jwt...***"}}
```

**Default Sensitive Keys (case-insensitive):**
- `token`, `access_token`, `session_token`, `auth_token`, `bearer_token`
- `jwt`, `sid`, `hsservid`, `jwttoken`
- `password`, `mpin`, `secret`, `api_key`, `consumer_secret`
- `authorization`, `api_secret`

#### 3. `sanitize_log_message(message)`
Removes potential tokens/secrets from log messages using pattern matching.

```python
from modules.kotak_neo_auto_trader.utils.security_utils import sanitize_log_message

log_msg = "Authentication successful. JWT: eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.payload.signature"
safe_msg = sanitize_log_message(log_msg)
# Result: "Authentication successful. JWT: eyJ...***"
```

#### 4. `safe_log_dict(data, sensitive_keys=None)`
Converts dictionary to safe string for logging.

```python
from modules.kotak_neo_auto_trader.utils.security_utils import safe_log_dict
import logging

response = {"user": "john", "token": "secret123"}
logging.info(f"API Response: {safe_log_dict(response)}")
# Logs: "API Response: {'user': 'john', 'token': 'sec...123'}"
```

## Usage Guidelines

### ✅ DO

1. **Use security utilities before logging any API responses:**
   ```python
   from modules.kotak_neo_auto_trader.utils.security_utils import safe_log_dict

   response = api_call()
   logger.info(f"Response: {safe_log_dict(response)}")
   ```

2. **Mask tokens in error messages:**
   ```python
   from modules.kotak_neo_auto_trader.utils.security_utils import sanitize_log_message

   error_msg = f"Auth failed: {raw_error}"
   logger.error(sanitize_log_message(error_msg))
   ```

3. **Use masked values in debugging:**
   ```python
   from modules.kotak_neo_auto_trader.utils.security_utils import mask_sensitive_value

   logger.debug(f"Token: {mask_sensitive_value(token)}")
   ```

### ❌ DON'T

1. **Never log raw API responses without masking:**
   ```python
   # BAD - may contain tokens
   logger.info(f"Response: {response}")
   ```

2. **Never print tokens/credentials directly:**
   ```python
   # BAD - exposes credentials
   print(f"Token: {auth.session_token}")
   ```

3. **Never commit files containing tokens:**
   - Check `.gitignore` for excluded patterns
   - Review changes before committing
   - Use `git diff` to verify no secrets are staged

4. **Never run dev test scripts in production:**
   - Scripts in `modules/kotak_neo_auto_trader/dev_tests/` are for local debugging only
   - They intentionally print sensitive data
   - See warning in `test_client_attrs.py`

## Existing Security Tests

### Location
- `tests/unit/test_security_utils.py` - Unit tests for security utilities
- `tests/security/test_kotak_security.py` - Integration tests for Kotak auth
- `tests/regression/test_continuous_service_v2_1.py` - Regression tests for sensitive data logging

### Run Security Tests
```bash
pytest tests/unit/test_security_utils.py -v
pytest tests/security/ -v -m security
```

## Git Ignore Patterns

The following patterns are excluded from version control to prevent accidental exposure:

```gitignore
*.env
cred.env
modules/kotak_neo_auto_trader/kotak_neo.env
modules/kotak_neo_auto_trader/session_cache.json

# Dev test outputs (may contain sensitive tokens)
modules/kotak_neo_auto_trader/dev_tests/logs/
modules/kotak_neo_auto_trader/dev_tests/output/
modules/kotak_neo_auto_trader/dev_tests/*_output.txt
modules/kotak_neo_auto_trader/dev_tests/*_tokens.txt
```

## Dev Test Scripts Security

### ⚠️ WARNING: Dev Tests May Print Sensitive Data

Scripts in `modules/kotak_neo_auto_trader/dev_tests/` are for **local development only** and may intentionally print tokens, credentials, and other sensitive data for debugging purposes.

**Example:** `test_client_attrs.py`
- Prints ALL client attributes including tokens
- Prints session tokens, JWTs, and auth headers
- **NEVER** run in production
- **NEVER** save output to version control
- **DELETE** output immediately after use

### Safe Dev Testing Practices

1. **Run in isolated environment:**
   ```bash
   # Use sandbox/test credentials only
   KOTAK_ENVIRONMENT=sandbox python modules/kotak_neo_auto_trader/dev_tests/test_client_attrs.py
   ```

2. **Pipe output to temporary file:**
   ```bash
   python dev_tests/test_client_attrs.py > /tmp/debug_output.txt
   # Review, then delete immediately:
   rm /tmp/debug_output.txt
   ```

3. **Never commit dev test outputs:**
   ```bash
   # Check before committing
   git status
   git diff
   ```

## Incident Response

### If Tokens Are Accidentally Exposed

1. **Immediate Actions:**
   - Revoke/rotate the exposed tokens immediately
   - Change passwords and MPIN
   - Regenerate API keys
   - Logout all active sessions

2. **If Committed to Git:**
   ```bash
   # Remove from Git history (use with caution)
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch path/to/file" \
     --prune-empty --tag-name-filter cat -- --all

   # Force push (coordinate with team)
   git push origin --force --all
   ```

3. **Notify:**
   - Inform the team
   - Document the incident
   - Review and improve security practices

## Regular Security Audits

### Checklist

- [ ] Run security tests: `pytest tests/security/ -v`
- [ ] Review recent commits for exposed secrets
- [ ] Verify `.gitignore` patterns are up-to-date
- [ ] Check log files for accidentally logged tokens
- [ ] Ensure dev test outputs are deleted
- [ ] Verify environment variables are properly secured

### Tools

```bash
# Search for potential token patterns in codebase
grep -r "token.*=.*['\"]" --include="*.py" modules/ server/ src/

# Check for hardcoded credentials
grep -r "password.*=.*['\"]" --include="*.py" modules/ server/ src/

# Find files that might contain tokens
find . -name "*token*" -o -name "*secret*" -o -name "*credential*"
```

## Best Practices Summary

1. ✅ **Always** use security utilities before logging API responses
2. ✅ **Always** mask tokens in error messages and debug logs
3. ✅ **Always** use environment variables for credentials
4. ✅ **Always** check `.gitignore` before committing
5. ❌ **Never** commit `.env` files or credentials
6. ❌ **Never** run dev test scripts in production
7. ❌ **Never** log raw API responses without masking
8. ❌ **Never** share log files publicly without review

## Resources

- Security Tests: `tests/unit/test_security_utils.py`
- Security Utilities: `modules/kotak_neo_auto_trader/utils/security_utils.py`
- Git Ignore: `.gitignore`
- Environment Template: `modules/kotak_neo_auto_trader/kotak_neo.env.example`
