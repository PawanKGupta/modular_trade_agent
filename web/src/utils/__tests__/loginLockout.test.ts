import { describe, it, expect, beforeEach } from 'vitest';
import {
	clearLoginLockout,
	formatLockoutCountdown,
	readLoginLockoutSeconds,
	saveLoginLockout,
} from '../loginLockout';

describe('loginLockout', () => {
	beforeEach(() => {
		sessionStorage.clear();
	});

	it('formats countdown as m:ss', () => {
		expect(formatLockoutCountdown(305)).toBe('5:05');
		expect(formatLockoutCountdown(59)).toBe('0:59');
		expect(formatLockoutCountdown(0)).toBe('0:00');
	});

	it('persists and reads lockout for matching email', () => {
		saveLoginLockout('User@Example.com', 90);
		expect(readLoginLockoutSeconds('user@example.com')).toBeGreaterThan(80);
		expect(readLoginLockoutSeconds('other@example.com')).toBe(0);
	});

	it('clears stored lockout', () => {
		saveLoginLockout('user@example.com', 60);
		clearLoginLockout();
		expect(readLoginLockoutSeconds('user@example.com')).toBe(0);
	});
});
