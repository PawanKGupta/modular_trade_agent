/**
 * Test Data Seeder
 * Utility to check if seeding is enabled and provide instructions
 * Actual seeding is done via Python script in global-setup.ts
 */

/**
 * Check if test data seeding is enabled
 */
export function isSeedingEnabled(): boolean {
	return process.env.E2E_SEED_DATA === 'true' || process.env.E2E_SEED_DATA === '1';
}
