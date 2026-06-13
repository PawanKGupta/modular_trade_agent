const STORAGE_KEY = 'ta_login_lockout';

type LoginLockoutRecord = {
	email: string;
	untilMs: number;
};

function normalizeEmail(email: string): string {
	return email.trim().toLowerCase();
}

/** Seconds remaining for this email's login lockout (0 if none or expired). */
export function readLoginLockoutSeconds(email: string): number {
	const normalized = normalizeEmail(email);
	if (!normalized) {
		return 0;
	}
	try {
		const raw = sessionStorage.getItem(STORAGE_KEY);
		if (!raw) {
			return 0;
		}
		const parsed = JSON.parse(raw) as LoginLockoutRecord;
		if (parsed.email !== normalized || parsed.untilMs <= Date.now()) {
			return 0;
		}
		return Math.max(0, Math.ceil((parsed.untilMs - Date.now()) / 1000));
	} catch {
		return 0;
	}
}

/** Persist lockout end time so refresh keeps the countdown for the same email. */
export function saveLoginLockout(email: string, retryAfterSeconds: number): void {
	const normalized = normalizeEmail(email);
	if (!normalized || retryAfterSeconds <= 0) {
		return;
	}
	const record: LoginLockoutRecord = {
		email: normalized,
		untilMs: Date.now() + retryAfterSeconds * 1000,
	};
	sessionStorage.setItem(STORAGE_KEY, JSON.stringify(record));
}

export function clearLoginLockout(): void {
	sessionStorage.removeItem(STORAGE_KEY);
}

/** Format seconds as `m:ss` for the lockout timer (e.g. 125 → `2:05`). */
export function formatLockoutCountdown(totalSeconds: number): string {
	const seconds = Math.max(0, totalSeconds);
	const minutes = Math.floor(seconds / 60);
	const remainder = seconds % 60;
	return `${minutes}:${remainder.toString().padStart(2, '0')}`;
}

export const LOGIN_LOCKOUT_HEADLINE = 'Too many login attempts. Please wait before trying again.';
