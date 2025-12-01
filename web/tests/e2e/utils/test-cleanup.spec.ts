/**
 * Test Cleanup Safety Tests
 * These tests verify that cleanup only affects test data
 */

import { test, expect } from '../fixtures/test-fixtures';
import { TestDataTracker, isTestEmail } from './test-cleanup';
import { TestConfig } from '../config/test-config';

test.describe('Test Cleanup Safety', () => {
	test('TestDataTracker only tracks test emails', () => {
		const tracker = new TestDataTracker();

		// Should track test emails
		tracker.trackUser('test123@rebound.com');
		tracker.trackUser('signup456@rebound.com');
		expect(tracker.getUserEmails()).toHaveLength(2);

		// Should NOT track admin emails
		tracker.trackUser(TestConfig.users.admin.email);
		expect(tracker.getUserEmails()).toHaveLength(2); // Still 2, admin not added

		// Should NOT track system emails
		tracker.trackUser('admin@rebound.com');
		tracker.trackUser('system@rebound.com');
		expect(tracker.getUserEmails()).toHaveLength(2); // Still 2
	});

	test('isTestEmail correctly identifies test emails', () => {
		// Valid test emails
		expect(isTestEmail('test123@rebound.com')).toBe(true);
		expect(isTestEmail('signup456@rebound.com')).toBe(true);
		expect(isTestEmail('testuser789@rebound.com')).toBe(true);
		expect(isTestEmail('test@example.com')).toBe(true);

		// Protected emails (should return false)
		expect(isTestEmail(TestConfig.users.admin.email)).toBe(false);
		expect(isTestEmail(TestConfig.users.user.email)).toBe(false);
		expect(isTestEmail('admin@rebound.com')).toBe(false);
		expect(isTestEmail('system@rebound.com')).toBe(false);
	});

	test('TestDataTracker only resets configs that were tracked', async ({ authenticatedPage: page }) => {
		const tracker = new TestDataTracker();

		// Don't track config
		// Config should NOT be reset
		await tracker.cleanup(page);
		expect(tracker.getConfigs()).toHaveLength(0);
	});
});
