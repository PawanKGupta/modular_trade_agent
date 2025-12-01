import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
	testDir: './tests/e2e',
	timeout: 60000, // Increase default test timeout to 60 seconds
	expect: {
		timeout: 10000, // Increase expect timeout to 10 seconds
	},
	globalSetup: './tests/e2e/global-setup.ts',
	globalTeardown: './tests/e2e/global-teardown.ts',
	use: {
		baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:5173',
		trace: 'retain-on-failure',
		screenshot: 'only-on-failure',
		video: 'retain-on-failure',
		actionTimeout: 15000, // Increase action timeout to 15 seconds
		navigationTimeout: 30000, // Increase navigation timeout to 30 seconds
	},
	projects: [
		{
			name: 'chromium',
			use: { ...devices['Desktop Chrome'] },
		},
	],
});
