import axios from 'axios';

/**
 * Turn FastAPI/Axios errors into a single string for UI copy.
 *
 * Handles `detail` as a string, validation error arrays, and generic Axios bodies.
 */
export function getApiErrorMessage(error: unknown, fallback = 'Something went wrong'): string {
	if (axios.isAxiosError(error)) {
		const data = error.response?.data as { detail?: unknown; message?: unknown } | undefined;
		const detailText = normalizeFastApiDetail(data?.detail);
		if (detailText) {
			return detailText;
		}
		if (typeof data?.message === 'string' && data.message.trim()) {
			return data.message;
		}
		if (typeof error.message === 'string' && error.message.trim()) {
			return error.message;
		}
		const status = error.response?.status;
		if (status) {
			return `Request failed (${status})`;
		}
	}
	if (error instanceof Error && error.message.trim()) {
		return error.message;
	}
	return fallback;
}

/** True when an auth endpoint rejected the request due to rate limiting (HTTP 429). */
export function isAuthRateLimitError(error: unknown): boolean {
	return axios.isAxiosError(error) && error.response?.status === 429;
}

/** Seconds until the client may retry (from 429 JSON or Retry-After header). */
export function getAuthRetryAfterSeconds(error: unknown): number | null {
	if (!axios.isAxiosError(error)) {
		return null;
	}
	const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail;
	if (typeof detail === 'object' && detail !== null && !Array.isArray(detail)) {
		const raw = (detail as Record<string, unknown>).retry_after_seconds;
		if (typeof raw === 'number' && Number.isFinite(raw) && raw > 0) {
			return Math.ceil(raw);
		}
	}
	const retryAfter = error.response?.headers?.['retry-after'];
	if (typeof retryAfter === 'string' && /^\d+$/.test(retryAfter.trim())) {
		return Number.parseInt(retryAfter.trim(), 10);
	}
	return null;
}

/** Optional vague pre-lockout warning from a failed login (HTTP 401 with warning field). */
export function getApiErrorWarning(error: unknown): string | null {
	if (!axios.isAxiosError(error)) {
		return null;
	}
	const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail;
	if (typeof detail !== 'object' || detail === null || Array.isArray(detail)) {
		return null;
	}
	const warning = (detail as Record<string, unknown>).warning;
	return typeof warning === 'string' && warning.trim() ? warning : null;
}

/** True when login failed because the account email is not verified yet (HTTP 403). */
export function isUnverifiedEmailLoginError(error: unknown): boolean {
	if (!axios.isAxiosError(error) || error.response?.status !== 403) {
		return false;
	}
	const detail = normalizeFastApiDetail(
		(error.response.data as { detail?: unknown } | undefined)?.detail,
	);
	return (detail ?? '').toLowerCase().includes('verify your email');
}

function normalizeFastApiDetail(detail: unknown): string | null {
	if (detail == null) {
		return null;
	}
	if (typeof detail === 'string') {
		return detail;
	}
	if (typeof detail === 'object' && !Array.isArray(detail)) {
		const record = detail as Record<string, unknown>;
		if (typeof record.message === 'string' && record.message.trim()) {
			return record.message;
		}
	}
	if (Array.isArray(detail)) {
		const parts = detail.map((item) => formatFastApiValidationItem(item));
		return parts.join('; ');
	}
	return null;
}

const BODY_FIELD_LABELS: Record<string, string> = {
	email: 'Email',
	password: 'Password',
	name: 'Name',
	mobile_number: 'Mobile number',
	current_password: 'Current password',
	new_password: 'New password',
};

/** Strip Pydantic wrappers and avoid showing raw `body.email` paths in the UI. */
function formatFastApiValidationItem(item: unknown): string {
	if (typeof item === 'string') {
		return item;
	}
	if (typeof item !== 'object' || item === null || !('msg' in item)) {
		return JSON.stringify(item);
	}
	let msg = String((item as { msg: unknown }).msg).trim();
	msg = msg.replace(/^Value error,\s*/i, '');

	const loc = (item as { loc?: unknown }).loc;
	const field =
		Array.isArray(loc) && loc.length >= 2 && loc[0] === 'body' ? String(loc[1]) : null;

	// Custom validator messages are already user-facing — show without `body.field` prefix.
	if (msg.length > 0 && !isGenericPydanticMessage(msg)) {
		return msg;
	}

	if (field && BODY_FIELD_LABELS[field]) {
		return `${BODY_FIELD_LABELS[field]}: ${msg}`;
	}

	return msg;
}

function isGenericPydanticMessage(msg: string): boolean {
	return /^(field required|string_type|missing|ensure this value|input should be)/i.test(msg);
}
