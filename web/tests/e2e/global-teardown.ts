import { FullConfig } from '@playwright/test';
import { TestConfig } from './config/test-config';

/**
 * Global Teardown
 * Runs once after all tests
 * Use this to:
 * - Clean up global test data
 * - Reset database to initial state (optional)
 * - Generate test reports
 */
async function globalTeardown(config: FullConfig) {
	console.log('Running global teardown...');

	// Optional: Clean up global test data
	// This is where you'd clean up any data that should persist across test runs
	// For most cases, individual test cleanup is sufficient

	console.log('Global teardown completed');
}

export default globalTeardown;
