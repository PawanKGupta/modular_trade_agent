import { describe, expect, it } from 'vitest';
import {
	validateChangePasswordForm,
	validateEmail,
	validateLoginForm,
	validatePassword,
	validatePasswordConfirm,
	validateSignupForm,
} from '../authValidation';

describe('authValidation', () => {
	it('validateEmail rejects empty and invalid addresses', () => {
		expect(validateEmail('')).toBe('Email is required');
		expect(validateEmail('not-an-email')).toBe('Enter a valid email address');
		expect(validateEmail('user@example.com')).toBeNull();
	});

	it('validatePassword enforces length and complexity', () => {
		expect(validatePassword('')).toBe('Password is required');
		expect(validatePassword('short1')).toBe('Password must be at least 8 characters');
		expect(validatePassword('12345678')).toBe('Password must include at least one letter');
		expect(validatePassword('abcdefgh')).toBe('Password must include at least one number');
		expect(validatePassword('Secret123')).toBeNull();
	});

	it('validatePasswordConfirm checks match', () => {
		expect(validatePasswordConfirm('Secret123', '')).toBe('Please confirm your password');
		expect(validatePasswordConfirm('Secret123', 'Secret456')).toBe('Passwords do not match');
		expect(validatePasswordConfirm('Secret123', 'Secret123')).toBeNull();
	});

	it('validateLoginForm collects email and password errors', () => {
		expect(validateLoginForm({ email: '', password: '' })).toEqual([
			{ field: 'email', message: 'Email is required' },
			{ field: 'password', message: 'Password is required' },
		]);
		expect(validateLoginForm({ email: 'user@example.com', password: 'x' })).toEqual([]);
	});

	it('validateSignupForm collects signup field errors', () => {
		const errors = validateSignupForm({
			email: 'bad',
			password: 'short',
			confirmPassword: 'other',
		});
		expect(errors.map((e) => e.field)).toEqual(['email', 'password', 'confirmPassword']);
	});

	it('validateChangePasswordForm collects change-password errors', () => {
		const errors = validateChangePasswordForm({
			currentPassword: '',
			newPassword: 'short',
			confirmPassword: 'x',
		});
		expect(errors.map((e) => e.field)).toEqual(['currentPassword', 'newPassword', 'confirmPassword']);
	});
});
