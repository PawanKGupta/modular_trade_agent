import { FullConfig } from '@playwright/test';
import { TestConfig } from './config/test-config';

/**
 * Global Setup
 * Runs once before all tests
 * Use this to:
 * - Set up test database
 * - Create initial test data
 * - Verify API is accessible
 */
async function globalSetup(config: FullConfig) {
	console.log('Running global setup...');

	// Verify API is accessible
	try {
		const response = await fetch(`${TestConfig.apiURL}/health`);
		if (!response.ok) {
			throw new Error(`API health check failed: ${response.status}`);
		}
		console.log('✓ API server is accessible');
	} catch (error) {
		console.error('✗ API server is not accessible:', error);
		throw error;
	}

	// Verify web frontend is accessible
	try {
		const response = await fetch(TestConfig.baseURL);
		if (!response.ok) {
			throw new Error(`Web frontend check failed: ${response.status}`);
		}
		console.log('✓ Web frontend is accessible');
	} catch (error) {
		console.error('✗ Web frontend is not accessible:', error);
		throw error;
	}

	console.log('Global setup completed successfully');
}

export default globalSetup;
