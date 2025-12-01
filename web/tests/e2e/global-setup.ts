import { execSync } from 'child_process';
import { join } from 'path';
import { FullConfig } from '@playwright/test';
import { TestConfig } from './config/test-config';

/**
 * Global Setup
 * Runs once before all tests
 * Use this to:
 * - Set up test database
 * - Create initial test data (if enabled)
 * - Verify API is accessible
 */
async function globalSetup(config: FullConfig) {
	console.log('Running global setup...');

	// Important note about database separation
	const dbUrl = process.env.E2E_DB_URL || process.env.DB_URL || 'sqlite:///./data/e2e.db';
	if (dbUrl.includes('app.db')) {
		console.warn('\n⚠️  WARNING: Detected app.db in database URL!');
		console.warn('   E2E tests should use e2e.db, not app.db.');
		console.warn('   Docker/production uses app.db, E2E tests use e2e.db.');
			console.warn('   See: web/tests/e2e/DATABASE.md\n');
	}

	// Verify API is accessible
	try {
		const response = await fetch(`${TestConfig.apiURL}/health`);
		if (!response.ok) {
			throw new Error(`API health check failed: ${response.status}`);
		}
		console.log('✓ API server is accessible');
		console.log(`  Using database: ${dbUrl}`);
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

	// Seed test data if enabled
	if (process.env.E2E_SEED_DATA === 'true' || process.env.E2E_SEED_DATA === '1') {
		console.log('\nSeeding test data...');
		try {
			// Resolve script path relative to project root
			// From web/tests/e2e/global-setup.ts to web/tests/e2e/utils/seed-db.py
			const projectRoot = process.cwd();
			const scriptPath = join(projectRoot, 'web', 'tests', 'e2e', 'utils', 'seed-db.py');
			const signalsCount = process.env.E2E_SEED_SIGNALS || '5';
			const ordersCount = process.env.E2E_SEED_ORDERS || '3';
			const notificationsCount = process.env.E2E_SEED_NOTIFICATIONS || '5';
			const dbUrl = process.env.E2E_DB_URL || 'sqlite:///./data/e2e.db';

			// Execute Python seeding script
			// Change to project root directory for relative path resolution
			const command = [
				'python',
				scriptPath.replace(/\\/g, '/'), // Normalize path separators
				'--signals', signalsCount,
				'--orders', ordersCount,
				'--notifications', notificationsCount,
				'--db-url', dbUrl,
				...(process.env.E2E_CLEAR_BEFORE_SEED === 'true' ? ['--clear'] : []),
			].join(' ');

			execSync(command, {
				cwd: projectRoot, // Run from project root
				stdio: 'inherit',
				encoding: 'utf-8',
				shell: true, // Use shell for better cross-platform support
			});

			console.log('✓ Test data seeded successfully');
		} catch (error) {
			console.warn('⚠ Failed to seed test data (tests will continue with empty database):', error);
			console.warn('  Tests will still work but may have limited coverage without test data.');
		}
	} else {
		console.log('ℹ Test data seeding is disabled (set E2E_SEED_DATA=true to enable)');
	}

	console.log('\nGlobal setup completed successfully');
}

export default globalSetup;
