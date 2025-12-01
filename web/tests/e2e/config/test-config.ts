/**
 * Test Configuration
 * Centralized configuration for E2E tests
 */

export const TestConfig = {
	// Base URLs
	baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173',
	apiURL: process.env.VITE_API_URL || 'http://localhost:8000',

	// Test Users
	users: {
		admin: {
			email: process.env.TEST_ADMIN_EMAIL || 'testadmin@rebound.com',
			password: process.env.TEST_ADMIN_PASSWORD || 'testadmin@123',
			role: 'admin' as const,
		},
		user: {
			email: process.env.TEST_USER_EMAIL || 'testuser@rebound.com',
			password: process.env.TEST_USER_PASSWORD || 'testuser@123',
			role: 'user' as const,
		},
	},

	// Timeouts (in milliseconds)
	timeouts: {
		navigation: 30000,
		action: 15000,
		expect: 10000,
		element: 10000,
		test: 60000,
	},

	// Test Data
	testData: {
		// Trading configuration defaults
		trading: {
			rsiPeriod: 10,
			emaPeriod: 9,
			minCapital: 1000,
		},
		// Notification preferences
		notifications: {
			email: 'test@example.com',
		},
	},
} as const;
