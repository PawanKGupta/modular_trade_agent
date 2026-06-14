# Release Plan v26.2.2.1

**Branch:** `hotfix/rebound_26221`
**Version:** 26.2.2.1 (CalVer Q2 2026 hotfix patch)
**Status:** Ready for tag and deploy after checklist below
**Release notes:** Full branch scope — see [CHANGELOG.md](../../CHANGELOG.md) `[26.2.2.1]`

---

## Scope

Major themes on this hotfix branch (since `v26.2.2`):

| Theme | Operator impact |
|-------|-----------------|
| MFA Setup QR code | Generates and displays a scannable QR code image on the setup wizard screen |
| MFA Login Challenge | Prompts for and validates the 6-digit authenticator code inline at login form |
| Settings UX | Collapses User Profile and Trading Account configuration panels by default |
| Login UX | Removes redundant "Required fields" static notice from form |

---

## Pre-release verification

| Gate | Result (2026-06-14 local) |
|------|---------------------------|
| Web Vitest + coverage | **90.85%** lines (exceeds 90% threshold) |
| SettingsPage unit tests | Mocked setup & disable paths verified |
| LoginPage unit tests | Mocked inline login challenge & back options verified |
| Settings E2E Playwright tests | **7 passed** (including Account Settings page loads) |

---

## Deploy steps

1. Pull `hotfix/rebound_26221` (or tag `v26.2.2.1`).
2. Rebuild and restart Web UI service (or package the frontend files).
3. **Post-deploy smoke:**
   - Go to Settings -> Security -> Two-factor auth. Click "Set up MFA". Verify that a QR code image renders and the manual secret text fallback is shown.
   - Set up MFA, scan, and confirm it enables.
   - Logout and log back in. Verify the form prompts for the 6-digit verification code inline, handles incorrect codes correctly, and navigates to Dashboard on success.
   - Verify Settings accordion groups are collapsed by default.

---

## Rollback

- Redeploy previous tag/container image (`v26.2.2`).

---

## Deliverables checklist

- [x] Version `26.2.2.1` in `VERSION` and `web/package.json`
- [x] `CHANGELOG.md` `[26.2.2.1]`
- [x] This release plan
- [x] Upgrade notes in [DEPLOYMENT.md](../deployment/DEPLOYMENT.md#upgrading-to-26221)
- [ ] Tag `v26.2.2.1` on branch tip (local; push with explicit approval)

---

## Related docs

- [Upgrading to 26.2.2.1](../deployment/DEPLOYMENT.md#upgrading-to-26221)
- [Release Plan v26.2.2](RELEASE_PLAN_V26.2.2.md)
