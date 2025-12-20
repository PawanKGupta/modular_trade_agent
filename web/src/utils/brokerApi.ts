/**
 * Enhanced error handling utilities for broker API operations
 */

export interface BrokerApiError {
	message: string;
	code?: string;
	retryable: boolean;
	statusCode?: number;
}

/**
 * Check if an error is retryable
 */
export function isRetryableError(error: unknown): boolean {
	if (error instanceof Error) {
		// Network errors are retryable
		if (error.message.includes('Network Error') || error.message.includes('timeout')) {
			return true;
		}
	}

	// Check if it's an Axios error
	if (typeof error === 'object' && error !== null && 'response' in error) {
		const axiosError = error as { response?: { status?: number } };
		const status = axiosError.response?.status;

		// 5xx errors are retryable
		if (status && status >= 500 && status < 600) {
			return true;
		}

		// 503 (Service Unavailable) is retryable
		if (status === 503) {
			return true;
		}

		// 429 (Too Many Requests) is retryable
		if (status === 429) {
			return true;
		}
	}

	return false;
}

/**
 * Extract error message from various error types
 */
export function extractErrorMessage(error: unknown): string {
	if (error instanceof Error) {
		return error.message;
	}

	if (typeof error === 'string') {
		return error;
	}

	if (typeof error === 'object' && error !== null) {
		// Axios error
		if ('response' in error) {
			const axiosError = error as { response?: { data?: { detail?: string; message?: string } } };
			const detail = axiosError.response?.data?.detail;
			const message = axiosError.response?.data?.message;
			return detail || message || 'An error occurred';
		}

		// Generic object with message
		if ('message' in error) {
			return String((error as { message: unknown }).message);
		}
	}

	return 'An unknown error occurred';
}

/**
 * Calculate retry delay with exponential backoff
 */
export function calculateRetryDelay(attempt: number, baseDelay = 1000, maxDelay = 30000): number {
	const delay = baseDelay * Math.pow(2, attempt);
	return Math.min(delay, maxDelay);
}

/**
 * Format error for display to user
 */
export function formatBrokerError(error: unknown): BrokerApiError {
	const message = extractErrorMessage(error);
	const retryable = isRetryableError(error);

	let statusCode: number | undefined;
	if (typeof error === 'object' && error !== null && 'response' in error) {
		statusCode = (error as { response?: { status?: number } }).response?.status;
	}

	return {
		message,
		retryable,
		statusCode,
	};
}
