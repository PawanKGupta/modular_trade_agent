import { describe, it, expect } from 'vitest';
import {
	isRetryableError,
	extractErrorMessage,
	calculateRetryDelay,
	formatBrokerError,
} from '../brokerApi';

describe('brokerApi utilities', () => {
	describe('isRetryableError', () => {
		it('returns true for network errors', () => {
			const error = new Error('Network Error');
			expect(isRetryableError(error)).toBe(true);
		});

		it('returns true for timeout errors', () => {
			const error = new Error('timeout');
			expect(isRetryableError(error)).toBe(true);
		});

		it('returns true for 5xx errors', () => {
			const error = {
				response: { status: 500 },
			};
			expect(isRetryableError(error)).toBe(true);
		});

		it('returns true for 503 errors', () => {
			const error = {
				response: { status: 503 },
			};
			expect(isRetryableError(error)).toBe(true);
		});

		it('returns true for 429 errors', () => {
			const error = {
				response: { status: 429 },
			};
			expect(isRetryableError(error)).toBe(true);
		});

		it('returns false for 4xx errors (except 429)', () => {
			const error = {
				response: { status: 400 },
			};
			expect(isRetryableError(error)).toBe(false);
		});

		it('returns false for non-error objects', () => {
			expect(isRetryableError({})).toBe(false);
			expect(isRetryableError(null)).toBe(false);
			expect(isRetryableError(undefined)).toBe(false);
		});
	});

	describe('extractErrorMessage', () => {
		it('extracts message from Error object', () => {
			const error = new Error('Test error');
			expect(extractErrorMessage(error)).toBe('Test error');
		});

		it('extracts message from string', () => {
			expect(extractErrorMessage('String error')).toBe('String error');
		});

		it('extracts detail from Axios error response', () => {
			const error = {
				response: {
					data: {
						detail: 'Error detail',
					},
				},
			};
			expect(extractErrorMessage(error)).toBe('Error detail');
		});

		it('extracts message from Axios error response', () => {
			const error = {
				response: {
					data: {
						message: 'Error message',
					},
				},
			};
			expect(extractErrorMessage(error)).toBe('Error message');
		});

		it('returns default message for unknown error types', () => {
			expect(extractErrorMessage(null)).toBe('An unknown error occurred');
			expect(extractErrorMessage(undefined)).toBe('An unknown error occurred');
		});
	});

	describe('calculateRetryDelay', () => {
		it('calculates exponential backoff', () => {
			expect(calculateRetryDelay(0)).toBe(1000);
			expect(calculateRetryDelay(1)).toBe(2000);
			expect(calculateRetryDelay(2)).toBe(4000);
			expect(calculateRetryDelay(3)).toBe(8000);
		});

		it('respects max delay', () => {
			const delay = calculateRetryDelay(10);
			expect(delay).toBeLessThanOrEqual(30000);
		});

		it('allows custom base delay', () => {
			expect(calculateRetryDelay(0, 500)).toBe(500);
			expect(calculateRetryDelay(1, 500)).toBe(1000);
		});
	});

	describe('formatBrokerError', () => {
		it('formats Error object', () => {
			const error = new Error('Test error');
			const result = formatBrokerError(error);
			expect(result.message).toBe('Test error');
			expect(result.retryable).toBe(false);
		});

		it('formats network error as retryable', () => {
			const error = new Error('Network Error');
			const result = formatBrokerError(error);
			expect(result.retryable).toBe(true);
		});

		it('formats 5xx error with status code', () => {
			const error = {
				response: { status: 503 },
			};
			const result = formatBrokerError(error);
			expect(result.statusCode).toBe(503);
			expect(result.retryable).toBe(true);
		});

		it('formats 4xx error as non-retryable', () => {
			const error = {
				response: { status: 400, data: { detail: 'Bad request' } },
			};
			const result = formatBrokerError(error);
			expect(result.statusCode).toBe(400);
			expect(result.retryable).toBe(false);
			expect(result.message).toBe('Bad request');
		});
	});
});
