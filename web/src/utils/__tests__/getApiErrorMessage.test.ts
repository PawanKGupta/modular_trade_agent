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

	it('joins validation detail array', () => {
		const err = axiosErrorWithData(422, {
			detail: [{ loc: ['body', 'x'], msg: 'field required' }],
		});
		expect(getApiErrorMessage(err)).toContain('field required');
		expect(getApiErrorMessage(err)).toContain('body.x');
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
});
