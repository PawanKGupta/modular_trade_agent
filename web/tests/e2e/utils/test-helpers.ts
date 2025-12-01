import { Page } from '@playwright/test';
import { LoginPage } from '../pages/LoginPage';
import { TestConfig } from '../config/test-config';

/**
 * Test Helper Utilities
 * Common utility functions for tests
 */

/**
 * Login user and wait for dashboard
 */
export async function loginUser(
	page: Page,
	email: string = TestConfig.users.admin.email,
	password: string = TestConfig.users.admin.password,
): Promise<void> {
	const loginPage = new LoginPage(page);
	await loginPage.login(email, password);

	// Wait for redirect to dashboard
	await page.waitForURL(/\/dashboard/, { timeout: TestConfig.timeouts.navigation });
}

/**
 * Generate unique test email
 */
export function generateTestEmail(prefix: string = 'test'): string {
	const timestamp = Date.now();
	return `${prefix}${timestamp}@rebound.com`;
}

/**
 * Generate unique test name
 */
export function generateTestName(prefix: string = 'Test User'): string {
	const timestamp = Date.now();
	return `${prefix} ${timestamp}`;
}

/**
 * Wait for API response
 */
export async function waitForAPIResponse(
	page: Page,
	urlPattern: string | RegExp,
	timeout: number = TestConfig.timeouts.action,
): Promise<void> {
	await page.waitForResponse(
		(response) => {
			const url = response.url();
			if (typeof urlPattern === 'string') {
				return url.includes(urlPattern);
			}
			return urlPattern.test(url);
		},
		{ timeout },
	);
}

/**
 * Mock API response
 */
export async function mockAPIResponse(
	page: Page,
	urlPattern: string | RegExp,
	response: { status: number; body: any },
): Promise<void> {
	await page.route(urlPattern, (route) => {
		route.fulfill({
			status: response.status,
			contentType: 'application/json',
			body: JSON.stringify(response.body),
		});
	});
}

/**
 * Clear all mocks
 */
export async function clearMocks(page: Page): Promise<void> {
	await page.unrouteAll();
}

// Re-export cleanup utilities for convenience
export {
	cleanupTestUser,
	cleanupTestUsers,
	saveOriginalTradingConfig,
	resetTradingConfig,
	saveOriginalNotificationPreferences,
	resetNotificationPreferences,
	trackNotificationId,
	cleanupTestNotifications,
	clearBrowserStorage,
	cleanupAllTestData,
	TestDataTracker,
} from './test-cleanup';
