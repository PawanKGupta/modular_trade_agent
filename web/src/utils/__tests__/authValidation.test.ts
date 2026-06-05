import { describe, expect, it } from 'vitest';
import {
	getEmailRequirements,
	getPasswordRequirements,
	isEmailValid,
	isPasswordValid,
	validateAdminCreateUserForm,
	validateChangePasswordForm,
	validateEmail,
	validateLoginForm,
	validatePassword,
	validatePasswordConfirm,
	validateSignupForm,
} from '../authValidation';

const VALID_PASSWORD = 'Secret123!';

describe('authValidation', () => {
	it('getEmailRequirements tracks format inline', () => {
		expect(getEmailRequirements('')).toEqual([
			{ id: 'present', label: 'Email address entered', met: false },
			{ id: 'format', label: 'Valid format (name@example.com)', met: false },
		]);
		expect(isEmailValid('user@example.com')).toBe(true);
		expect(getEmailRequirements('user@example.com').every((r) => r.met)).toBe(true);
	});

	it('validateEmail rejects empty and invalid addresses', () => {
		expect(validateEmail('')).toBe('Email is required');
		expect(validateEmail('not-an-email')).toBe('Enter a valid email address');
		expect(validateEmail('user@example.com')).toBeNull();
	});

	it('validatePassword enforces length and complexity', () => {
		expect(validatePassword('')).toBe('Password is required');
		expect(validatePassword('short1!')).toContain('at least 8 characters');
		expect(validatePassword('12345678!')).toContain('letter');
		expect(validatePassword('secret123!')).toContain('capital letter');
		expect(validatePassword('Secret123')).toContain('special character');
		expect(validatePassword(VALID_PASSWORD)).toBeNull();
	});

	it('getPasswordRequirements tracks each rule inline', () => {
		expect(getPasswordRequirements('')).toEqual([
			{ id: 'length', label: 'At least 8 characters', met: false },
			{ id: 'letter', label: 'At least one letter', met: false },
			{ id: 'uppercase', label: 'At least one capital letter', met: false },
			{ id: 'number', label: 'At least one number', met: false },
			{ id: 'special', label: 'At least one special character', met: false },
		]);
		expect(isPasswordValid(VALID_PASSWORD)).toBe(true);
		expect(getPasswordRequirements(VALID_PASSWORD).every((r) => r.met)).toBe(true);
	});

	it('validatePasswordConfirm checks match', () => {
		expect(validatePasswordConfirm(VALID_PASSWORD, '')).toBe('Please confirm your password');
		expect(validatePasswordConfirm(VALID_PASSWORD, 'Secret456!')).toBe('Passwords do not match');
		expect(validatePasswordConfirm(VALID_PASSWORD, VALID_PASSWORD)).toBeNull();
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
			name: '',
			email: 'bad',
			password: 'short',
			confirmPassword: 'other',
		});
		expect(errors.map((e) => e.field)).toEqual(['name', 'email', 'password', 'confirmPassword']);
	});

	it('validateAdminCreateUserForm collects admin create field errors', () => {
		const errors = validateAdminCreateUserForm({
			name: '',
			email: 'bad',
			password: 'short',
		});
		expect(errors.map((e) => e.field)).toEqual(['name', 'email', 'password']);
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
