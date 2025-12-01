import { Page } from '@playwright/test';
import { TestConfig } from '../config/test-config';

/**
 * Test Cleanup Utilities
 * Functions to clean up test data created during E2E tests
 * IMPORTANT: Only cleans up data that was explicitly tracked during tests
 */

/**
 * Check if email is a test email (safety check)
 * Exported for testing purposes
 */
export function isTestEmail(email: string): boolean {
	// Only clean up emails that match test patterns
	const testPatterns = [
		/^test.*@rebound\.com$/i,
		/^signup\d+@rebound\.com$/i,
		/^newuser\d+@rebound\.com$/i, // Admin-created users
		/^testuser\d+@rebound\.com$/i,
		/^test.*@example\.com$/i,
		/^\d+@rebound\.com$/, // Timestamp-based emails
	];

	// Never clean up admin or system users
	const protectedEmails = [
		TestConfig.users.admin.email.toLowerCase(),
		TestConfig.users.user.email.toLowerCase(),
		'admin@',
		'system@',
	];

	const emailLower = email.toLowerCase();
	if (protectedEmails.some((protectedEmail) => emailLower.includes(protectedEmail))) {
		return false;
	}

	return testPatterns.some((pattern) => pattern.test(email));
}

/**
 * Clean up test user by email
 * ONLY deletes if email matches test patterns
 */
export async function cleanupTestUser(page: Page, email: string): Promise<void> {
	// Safety check: Only delete test emails
	if (!isTestEmail(email)) {
		console.warn(`Skipping cleanup of non-test email: ${email}`);
		return;
	}

	try {
		// First, get the user by email to find user_id
		const listResponse = await page.request.get(`${TestConfig.apiURL}/api/v1/admin/users`);

		if (!listResponse.ok()) {
			// If unauthorized (401), skip cleanup silently (page not authenticated, e.g., in signup tests)
			if (listResponse.status() === 401) {
				// Silent skip - not an error, just can't cleanup without authentication
				return;
			}
			// For other errors, log a warning
			console.warn(`Failed to get user list for cleanup: ${listResponse.status()}`);
			return;
		}

		const users = await listResponse.json() as Array<{ id: number; email: string }>;
		const user = users.find((u) => u.email.toLowerCase() === email.toLowerCase());

		if (!user) {
			// User doesn't exist, nothing to clean up
			return;
		}

		// Delete user by user_id
		const deleteResponse = await page.request.delete(`${TestConfig.apiURL}/api/v1/admin/users/${user.id}`);

		if (!deleteResponse.ok() && deleteResponse.status() !== 404) {
			// If unauthorized, skip silently (same reason as above)
			if (deleteResponse.status() === 401) {
				return;
			}
			console.warn(`Failed to cleanup user ${email} (ID: ${user.id}): ${deleteResponse.status()}`);
		} else {
			console.log(`✓ Cleaned up test user: ${email} (ID: ${user.id})`);
		}
	} catch (error) {
		// Silent skip for network/auth errors - cleanup is best-effort
		// Only log if it's not an authentication-related error
		if (error instanceof Error && !error.message.includes('401')) {
			console.warn(`Error cleaning up user ${email}:`, error);
		}
	}
}

/**
 * Clean up test users created during signup tests
 */
export async function cleanupTestUsers(page: Page, emails: string[]): Promise<void> {
	for (const email of emails) {
		await cleanupTestUser(page, email);
	}
}

/**
 * Store original config values before modification
 */
const originalConfigs = new Map<string, any>();

/**
 * Save original trading configuration before modification
 * Call this BEFORE modifying config in tests
 */
export async function saveOriginalTradingConfig(page: Page): Promise<void> {
	try {
		const response = await page.request.get(`${TestConfig.apiURL}/api/v1/user/trading-config`);
		if (response.ok()) {
			const config = await response.json();
			originalConfigs.set('trading-config', config);
		}
	} catch (error) {
		console.warn('Error saving original trading config:', error);
	}
}

/**
 * Reset trading configuration to original values
 * ONLY resets if config was tracked and saved
 */
export async function resetTradingConfig(page: Page): Promise<void> {
	const originalConfig = originalConfigs.get('trading-config');

	if (!originalConfig) {
		// This is expected - tests only reset if they modified config
		// Only show warning in debug mode to reduce test output noise
		if (process.env.DEBUG_CLEANUP === 'true') {
			console.warn('No original trading config saved - skipping reset');
		}
		return;
	}

	try {
		const response = await page.request.put(`${TestConfig.apiURL}/api/v1/user/trading-config`, {
			data: originalConfig,
			headers: {
				'Content-Type': 'application/json',
			},
		});

		if (!response.ok()) {
			console.warn(`Failed to reset trading config: ${response.status()}`);
		} else {
			console.log('✓ Reset trading config to original values');
			originalConfigs.delete('trading-config');
		}
	} catch (error) {
		console.warn('Error resetting trading config:', error);
	}
}

/**
 * Track notification IDs created during tests
 */
const testNotificationIds: number[] = [];

/**
 * Track a notification ID for cleanup
 */
export function trackNotificationId(notificationId: number): void {
	testNotificationIds.push(notificationId);
}

/**
 * Clean up only tracked test notifications
 * ONLY cleans up notifications that were explicitly tracked
 */
export async function cleanupTestNotifications(page: Page): Promise<void> {
	if (testNotificationIds.length === 0) {
		return; // No notifications to clean up
	}

	try {
		// Mark tracked notifications as read
		for (const notificationId of testNotificationIds) {
			const response = await page.request.post(
				`${TestConfig.apiURL}/api/v1/user/notifications/${notificationId}/read`,
				{
					headers: {
						'Content-Type': 'application/json',
					},
				}
			);

			if (!response.ok() && response.status() !== 404) {
				console.warn(`Failed to cleanup notification ${notificationId}: ${response.status()}`);
			}
		}

		console.log(`✓ Cleaned up ${testNotificationIds.length} test notifications`);
		testNotificationIds.length = 0; // Clear array
	} catch (error) {
		console.warn('Error cleaning up notifications:', error);
	}
}

/**
 * Save original notification preferences before modification
 * Call this BEFORE modifying preferences in tests
 */
export async function saveOriginalNotificationPreferences(page: Page): Promise<void> {
	try {
		const response = await page.request.get(`${TestConfig.apiURL}/api/v1/user/notification-preferences`);
		if (response.ok()) {
			const prefs = await response.json();
			originalConfigs.set('notification-preferences', prefs);
		}
	} catch (error) {
		console.warn('Error saving original notification preferences:', error);
	}
}

/**
 * Reset notification preferences to original values
 * ONLY resets if preferences were tracked and saved
 */
export async function resetNotificationPreferences(page: Page): Promise<void> {
	const originalPrefs = originalConfigs.get('notification-preferences');

	if (!originalPrefs) {
		// This is expected - tests only reset if they modified preferences
		// Only show warning in debug mode to reduce test output noise
		if (process.env.DEBUG_CLEANUP === 'true') {
			console.warn('No original notification preferences saved - skipping reset');
		}
		return;
	}

	try {
		const response = await page.request.put(`${TestConfig.apiURL}/api/v1/user/notification-preferences`, {
			data: originalPrefs,
			headers: {
				'Content-Type': 'application/json',
			},
		});

		if (!response.ok()) {
			console.warn(`Failed to reset notification preferences: ${response.status()}`);
		} else {
			console.log('✓ Reset notification preferences to original values');
			originalConfigs.delete('notification-preferences');
		}
	} catch (error) {
		console.warn('Error resetting notification preferences:', error);
	}
}

/**
 * Clear browser storage (localStorage, sessionStorage, cookies)
 */
export async function clearBrowserStorage(page: Page): Promise<void> {
	await page.evaluate(() => {
		localStorage.clear();
		sessionStorage.clear();
	});

	await page.context().clearCookies();
}

/**
 * Clean up all test data
 * ONLY cleans up data that was explicitly tracked
 * Use TestDataTracker instead for automatic cleanup
 */
export async function cleanupAllTestData(page: Page, testUserEmails: string[] = []): Promise<void> {
	// Clean up test users (only test emails)
	if (testUserEmails.length > 0) {
		await cleanupTestUsers(page, testUserEmails);
	}

	// Note: Configs and notifications are only cleaned up if tracked
	// This function is mainly for manual cleanup scenarios
	// Use TestDataTracker for automatic cleanup
}

/**
 * Track test data for cleanup
 * Only tracks data created/modified during the current test
 */
export class TestDataTracker {
	private testUserEmails: string[] = [];
	private modifiedConfigs: string[] = [];
	private savedConfigs: Map<string, any> = new Map();

	/**
	 * Track a test user email for cleanup
	 * Only tracks if email matches test patterns
	 */
	trackUser(email: string): void {
		if (!isTestEmail(email)) {
			// Only warn in debug mode or if explicitly enabled
			// This prevents noise in test output when protecting admin/system emails
			if (process.env.DEBUG_CLEANUP === 'true') {
				console.warn(`Warning: Attempting to track non-test email: ${email}. Skipping.`);
			}
			return;
		}
		this.testUserEmails.push(email);
	}

	/**
	 * Track a modified config and save original value
	 * Call this BEFORE modifying config in tests
	 */
	async trackConfig(page: Page, configName: string): Promise<void> {
		if (this.modifiedConfigs.includes(configName)) {
			return; // Already tracking
		}

		// Save original config before modification
		if (configName === 'trading-config') {
			await saveOriginalTradingConfig(page);
		} else if (configName === 'notification-preferences') {
			await saveOriginalNotificationPreferences(page);
		}

		this.modifiedConfigs.push(configName);
	}

	/**
	 * Get all tracked user emails
	 */
	getUserEmails(): string[] {
		return [...this.testUserEmails];
	}

	/**
	 * Get all tracked configs
	 */
	getConfigs(): string[] {
		return [...this.modifiedConfigs];
	}

	/**
	 * Clear all tracked data
	 */
	clear(): void {
		this.testUserEmails = [];
		this.modifiedConfigs = [];
		this.savedConfigs.clear();
	}

	/**
	 * Clean up all tracked data
	 * ONLY cleans up data that was explicitly tracked
	 */
	async cleanup(page: Page): Promise<void> {
		// Clean up tracked users (only test emails)
		if (this.testUserEmails.length > 0) {
			await cleanupTestUsers(page, this.testUserEmails);
		}

		// Reset tracked configs (only if original was saved)
		if (this.modifiedConfigs.includes('trading-config')) {
			await resetTradingConfig(page);
		}

		if (this.modifiedConfigs.includes('notification-preferences')) {
			await resetNotificationPreferences(page);
		}

		// Clean up tracked notifications
		await cleanupTestNotifications(page);

		this.clear();
	}
}
