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
	if (Array.isArray(detail)) {
		const parts = detail.map((item) => {
			if (typeof item === 'string') {
				return item;
			}
			if (typeof item === 'object' && item !== null && 'msg' in item) {
				const msg = String((item as { msg: unknown }).msg);
				const loc = (item as { loc?: unknown }).loc;
				const locStr = Array.isArray(loc) ? loc.join('.') : '';
				return locStr ? `${locStr}: ${msg}` : msg;
			}
			return JSON.stringify(item);
		});
		return parts.join('; ');
	}
	return null;
}
