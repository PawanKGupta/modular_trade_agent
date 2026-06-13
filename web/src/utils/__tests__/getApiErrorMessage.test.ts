import { describe, it, expect } from 'vitest';
import axios, { AxiosError } from 'axios';
import { getApiErrorMessage } from '../getApiErrorMessage';

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
});
