import { describe, it, expect } from 'vitest';
import axios, { AxiosError } from 'axios';
import { getApiErrorMessage, isAuthRateLimitError, getApiErrorWarning, getAuthRetryAfterSeconds } from '../getApiErrorMessage';

function axiosErrorWithData(status: number, data: unknown): AxiosError {
	const err = new AxiosError('request failed');
	err.response = {
		status,
		data,
		statusText: 'Error',
		headers: {},
		config: {} as AxiosError['config'],
	};
	return err;
}

describe('getApiErrorMessage', () => {
	it('returns FastAPI string detail', () => {
		const err = axiosErrorWithData(400, { detail: 'CSV not found' });
		expect(getApiErrorMessage(err)).toBe('CSV not found');
	});

	it('joins validation detail array without body path prefix', () => {
		const err = axiosErrorWithData(422, {
			detail: [{ loc: ['body', 'x'], msg: 'field required' }],
		});
		expect(getApiErrorMessage(err)).toBe('field required');
	});

	it('strips Value error prefix for custom email validator messages', () => {
		const err = axiosErrorWithData(422, {
			detail: [
				{
					loc: ['body', 'email'],
					msg: 'Value error, Only email addresses from approved providers are allowed (e.g. Gmail, Outlook, Yahoo, iCloud, Rediffmail)',
				},
			],
		});
		expect(getApiErrorMessage(err)).toBe(
			'Only email addresses from approved providers are allowed (e.g. Gmail, Outlook, Yahoo, iCloud, Rediffmail)',
		);
	});

	it('falls back for non-Axios Error', () => {
		expect(getApiErrorMessage(new Error('network'))).toBe('network');
	});

	it('uses fallback for unknown', () => {
		expect(getApiErrorMessage(null, 'custom')).toBe('custom');
	});

	it('detects axios errors', () => {
		const err = axiosErrorWithData(400, { detail: 'bad' });
		expect(axios.isAxiosError(err)).toBe(true);
	});

	it('uses message field when detail is absent', () => {
		const err = axiosErrorWithData(400, { message: 'Broker unavailable' });
		expect(getApiErrorMessage(err)).toBe('Broker unavailable');
	});

	it('returns status fallback when body has no detail', () => {
		const err = axiosErrorWithData(503, {});
		err.message = '';
		expect(getApiErrorMessage(err)).toBe('Request failed (503)');
	});

	it('stringifies non-string validation items', () => {
		const err = axiosErrorWithData(422, { detail: [42] });
		expect(getApiErrorMessage(err)).toBe('42');
	});

	it('detects auth rate limit errors', () => {
		const err = axiosErrorWithData(429, {
			detail: {
				message: 'Too many login attempts. Please wait before trying again.',
				retry_after_seconds: 120,
			},
		});
		expect(isAuthRateLimitError(err)).toBe(true);
		expect(getApiErrorMessage(err)).toBe('Too many login attempts. Please wait before trying again.');
		expect(getAuthRetryAfterSeconds(err)).toBe(120);
	});

	it('does not treat other status codes as rate limit', () => {
		expect(isAuthRateLimitError(axiosErrorWithData(401, { detail: 'Invalid credentials' }))).toBe(false);
	});

	it('extracts message and warning from structured login failure detail', () => {
		const err = axiosErrorWithData(401, {
			detail: {
				message: 'Invalid credentials',
				warning: 'Multiple failed login attempts. Your account may be temporarily locked if this continues.',
			},
		});
		expect(getApiErrorMessage(err)).toBe('Invalid credentials');
		expect(getApiErrorWarning(err)).toMatch(/temporarily locked/i);
	});

	it('returns null warning when detail is a plain string', () => {
		const err = axiosErrorWithData(401, { detail: 'Invalid credentials' });
		expect(getApiErrorWarning(err)).toBeNull();
	});

	it('uses axios error.message when response body has no detail', () => {
		const err = axiosErrorWithData(400, {});
		err.message = 'Connection reset';
		expect(getApiErrorMessage(err)).toBe('Connection reset');
	});

	it('formats string items in validation detail arrays', () => {
		const err = axiosErrorWithData(422, { detail: ['plain error'] });
		expect(getApiErrorMessage(err)).toBe('plain error');
	});

	it('ignores object-shaped detail values', () => {
		const err = axiosErrorWithData(400, { detail: { code: 'X' } });
		err.message = 'from axios';
		expect(getApiErrorMessage(err)).toBe('from axios');
	});

	it('labels generic pydantic field errors with friendly field names', () => {
		const err = axiosErrorWithData(422, {
			detail: [{ loc: ['body', 'password'], msg: 'field required' }],
		});
		expect(getApiErrorMessage(err)).toBe('Password: field required');
	});
});
