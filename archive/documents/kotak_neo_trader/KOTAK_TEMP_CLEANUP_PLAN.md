# Kotak Neo Auto Trader - Temp Folder Cleanup Plan

## 🚨 CRITICAL SECURITY ISSUE FOUND

**File**: `modules/kotak_neo_auto_trader/Temp/test_auth.py`  
**Issue**: Contains **HARDCODED CREDENTIALS** (password, consumer_key, consumer_secret, mobile number)

---

## Current State

### Files in `modules/kotak_neo_auto_trader/Temp/`
```
Temp/
├── .coverage                   # 53KB - Coverage data (should be in project root)
├── dev_introspect.py          # 768 bytes - Development script
├── example_usage.py           # 7.8KB - Example/dev script
├── kotak_neo_trader.py        # 17.5KB - Old/draft implementation
├── mock_client.py             # 3.6KB - Mock for testing
├── run_auto_trade_mock.py     # 2.8KB - Mock runner
├── run_place_gtt.py           # 4.4KB - GTT order script
├── session_cache.json         # 921 bytes - OBSOLETE (v2.1 removed caching)
├── test_auth.py               # 687 bytes - 🚨 HARDCODED CREDENTIALS
└── working_neo_login.py       # 7.7KB - Working login example
```

**Total**: 10 files, mostly temporary/development files

---

## Security Risk: test_auth.py 🚨

### Exposed Credentials
```python
# ⚠️ SECURITY BREACH - Remove immediately
consumer_key = "4z1vzG3f4EL3nYZofphRwNPl3IQa"
consumer_secret = "4SDFCpmiF1ZDEF_LEi8r7fuDFJMa"
mobilenumber = "+918565859556"
password = "Pkmast@61"
m_otp = "5656"
```

### **IMMEDIATE ACTION REQUIRED**
1. Delete `test_auth.py` immediately
2. Rotate/revoke exposed credentials:
   - ❌ Consumer Key: `4z1vzG3f4EL3nYZofphRwNPl3IQa`
   - ❌ Consumer Secret: `4SDFCpmiF1ZDEF_LEi8r7fuDFJMa`
   - ❌ Mobile: `+918565859556`
   - ❌ Password: `Pkmast@61`
3. Check if repository is public (if yes, credentials are compromised)
4. Generate new API keys from Kotak Neo portal
5. Change password immediately

---

## Recommended Actions

### Option 1: Delete Entire Temp Folder ✅ **RECOMMENDED**
**Rationale**: All files appear to be temporary/development artifacts

```powershell
# Backup first (optional)
Copy-Item "modules\kotak_neo_auto_trader\Temp" "modules\kotak_neo_auto_trader\Temp_backup_$(Get-Date -Format 'yyyyMMdd')" -Recurse

# Delete Temp folder
Remove-Item "modules\kotak_neo_auto_trader\Temp" -Recurse -Force
```

**Pros**:
- ✅ Removes security risk
- ✅ Cleans up temporary files
- ✅ Removes obsolete session_cache.json
- ✅ Simplifies project structure

**Cons**:
- ⚠️ Loses development examples (can recreate if needed)

---

### Option 2: Selective Cleanup
Keep potentially useful files, delete sensitive/obsolete ones:

```powershell
# Delete files
Remove-Item "modules\kotak_neo_auto_trader\Temp\test_auth.py" -Force        # 🚨 SECURITY
Remove-Item "modules\kotak_neo_auto_trader\Temp\session_cache.json" -Force  # Obsolete v2.1
Remove-Item "modules\kotak_neo_auto_trader\Temp\.coverage" -Force           # Wrong location
Remove-Item "modules\kotak_neo_auto_trader\Temp\kotak_neo_trader.py" -Force # Old draft

# Keep (move to examples/ directory)
New-Item -ItemType Directory -Path "modules\kotak_neo_auto_trader\examples" -Force
Move-Item "modules\kotak_neo_auto_trader\Temp\example_usage.py" "modules\kotak_neo_auto_trader\examples\"
Move-Item "modules\kotak_neo_auto_trader\Temp\mock_client.py" "modules\kotak_neo_auto_trader\examples\"
Move-Item "modules\kotak_neo_auto_trader\Temp\working_neo_login.py" "modules\kotak_neo_auto_trader\examples\"

# Review manually before deleting
# - dev_introspect.py
# - run_auto_trade_mock.py
# - run_place_gtt.py
```

**Pros**:
- ✅ Keeps potentially useful examples
- ✅ Removes security risks

**Cons**:
- ⚠️ More manual work
- ⚠️ Creates new examples/ directory

---

## File-by-File Analysis

| File | Purpose | Action | Reason |
|------|---------|--------|--------|
| **test_auth.py** | Auth testing | 🚨 **DELETE IMMEDIATELY** | Hardcoded credentials |
| **session_cache.json** | Session cache | ❌ **DELETE** | Obsolete (v2.1 removed caching) |
| **.coverage** | Coverage data | ❌ **DELETE** | Wrong location (belongs in root) |
| **kotak_neo_trader.py** | Old implementation | ❌ **DELETE** | Superseded by current code |
| **example_usage.py** | Usage example | 🟡 **KEEP or DELETE** | May be useful reference |
| **mock_client.py** | Mock for testing | 🟡 **KEEP or DELETE** | May be useful for tests |
| **working_neo_login.py** | Login example | 🟡 **KEEP or DELETE** | May contain useful patterns |
| **dev_introspect.py** | Dev tool | 🟡 **KEEP or DELETE** | Development utility |
| **run_auto_trade_mock.py** | Mock runner | 🟡 **KEEP or DELETE** | Testing utility |
| **run_place_gtt.py** | GTT orders | 🟡 **KEEP or DELETE** | Feature not yet implemented |

---

## Recommended Structure (After Cleanup)

### If keeping examples:
```
modules/kotak_neo_auto_trader/
├── application/
├── domain/
├── infrastructure/
├── logs/
├── examples/              # 🆕 NEW - Move useful examples here
│   ├── README.md
│   ├── example_usage.py           # Safe example (no credentials)
│   ├── mock_client.py             # Mock for testing
│   └── working_neo_login.py       # Login pattern example (sanitized)
├── auth.py
├── auto_trade_engine.py
├── orders.py
└── ... (other modules)
```

### If deleting everything:
```
modules/kotak_neo_auto_trader/
├── application/
├── domain/
├── infrastructure/
├── logs/
├── auth.py
├── auto_trade_engine.py
├── orders.py
└── ... (other modules)
```

---

## Security Remediation Steps

### Step 1: Immediate Deletion 🚨
```powershell
# Delete the security risk immediately
Remove-Item "modules\kotak_neo_auto_trader\Temp\test_auth.py" -Force
```

### Step 2: Credential Rotation 🔐
1. Login to Kotak Neo API portal
2. Revoke existing API credentials:
   - Consumer Key: `4z1vzG3f4EL3nYZofphRwNPl3IQa`
   - Consumer Secret: `4SDFCpmiF1ZDEF_LEi8r7fuDFJMa`
3. Generate new API credentials
4. Change account password
5. Update `modules/kotak_neo_auto_trader/kotak_neo.env` with new credentials
6. **NEVER commit .env files to git**

### Step 3: Git History Check 🔍
```powershell
# Check if file was ever committed to git
git log --all --full-history -- "modules/kotak_neo_auto_trader/Temp/test_auth.py"

# If file is in git history, credentials are PERMANENTLY compromised
# You MUST rotate credentials immediately
```

### Step 4: Add to .gitignore
```
# Add to .gitignore
modules/kotak_neo_auto_trader/Temp/
modules/kotak_neo_auto_trader/examples/*.json
*.coverage
session_cache.json
```

---

## Implementation Plan

### Option A: Full Cleanup (Recommended) ✅

```powershell
# 1. Backup (optional, if you want to review files later)
Copy-Item "modules\kotak_neo_auto_trader\Temp" "modules\kotak_neo_auto_trader\Temp_backup_$(Get-Date -Format 'yyyyMMdd')" -Recurse

# 2. Delete entire Temp folder
Remove-Item "modules\kotak_neo_auto_trader\Temp" -Recurse -Force

# 3. Verify deletion
Test-Path "modules\kotak_neo_auto_trader\Temp"  # Should return False

# 4. Rotate credentials (manual - login to Kotak Neo portal)
# 5. Update .env file with new credentials
# 6. Update .gitignore
```

### Option B: Selective Cleanup

```powershell
# 1. Delete security risks
Remove-Item "modules\kotak_neo_auto_trader\Temp\test_auth.py" -Force
Remove-Item "modules\kotak_neo_auto_trader\Temp\session_cache.json" -Force
Remove-Item "modules\kotak_neo_auto_trader\Temp\.coverage" -Force

# 2. Create examples directory
New-Item -ItemType Directory -Path "modules\kotak_neo_auto_trader\examples" -Force

# 3. Move useful files (review content first!)
# Review each file to ensure no hardcoded credentials
Move-Item "modules\kotak_neo_auto_trader\Temp\example_usage.py" "modules\kotak_neo_auto_trader\examples\"
Move-Item "modules\kotak_neo_auto_trader\Temp\mock_client.py" "modules\kotak_neo_auto_trader\examples\"

# 4. Delete remaining Temp folder
Remove-Item "modules\kotak_neo_auto_trader\Temp" -Recurse -Force

# 5. Rotate credentials
# 6. Update .gitignore
```

---

## Checklist

### Security ✅
- [ ] Delete `test_auth.py` immediately
- [ ] Rotate/revoke exposed API credentials
- [ ] Change password
- [ ] Check git history for exposed credentials
- [ ] Update `.env` with new credentials
- [ ] Verify `.env` in `.gitignore`

### Cleanup ✅
- [ ] Backup Temp folder (optional)
- [ ] Delete or reorganize Temp files
- [ ] Remove `session_cache.json` (obsolete in v2.1)
- [ ] Move `.coverage` to project root or delete
- [ ] Create `examples/` directory (if keeping examples)
- [ ] Update `.gitignore`

### Verification ✅
- [ ] Verify Temp folder deleted
- [ ] Run tests to ensure nothing broke
- [ ] Verify new credentials work
- [ ] Commit cleanup changes

---

## Summary

**Recommendation**: **DELETE ENTIRE TEMP FOLDER** (Option A)

**Critical Actions**:
1. 🚨 Delete `test_auth.py` immediately
2. 🔐 Rotate all exposed credentials
3. 🗑️ Delete obsolete Temp folder
4. 🛡️ Update .gitignore

**Risk Level**: 🔴 **HIGH** - Exposed credentials can lead to:
- Unauthorized trading
- Account compromise  
- Financial loss
- API abuse

**Execute immediately**: Delete `test_auth.py` first, ask questions later.

---

**Status**: 🚨 **ACTION REQUIRED**  
**Priority**: **CRITICAL - IMMEDIATE**
