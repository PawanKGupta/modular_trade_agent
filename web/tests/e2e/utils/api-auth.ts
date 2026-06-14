import { Page } from '@playwright/test';

/**
 * Build Authorization/CSRF headers for Playwright API requests from browser storage.
 * page.request does not read localStorage; the UI stores Bearer tokens there in dev/E2E.
 */
export async function getApiAuthHeaders(page: Page): Promise<Record<string, string>> {
	const tokens = await page.evaluate(() => ({
		access: localStorage.getItem('ta_access_token'),
		csrf: sessionStorage.getItem('ta_csrf_token'),
	}));
	const headers: Record<string, string> = {};
	if (tokens.access) {
		headers.Authorization = `Bearer ${tokens.access}`;
	}
	if (tokens.csrf) {
		headers['X-CSRF-Token'] = tokens.csrf;
	}
	return headers;
}
