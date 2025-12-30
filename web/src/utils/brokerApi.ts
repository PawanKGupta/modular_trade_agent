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
		const axiosError = error as {
			response?: { status?: number; data?: { detail?: string; message?: string } };
		};
		const status = axiosError.response?.status;
		const detail = axiosError.response?.data?.detail?.toLowerCase() || '';
		const message = axiosError.response?.data?.message?.toLowerCase() || '';

		// Session expiration errors are NOT retryable - they require user action
		// Check for session expiration in response data first, before checking status codes
		if (
			detail.includes('session expired') ||
			detail.includes('broker session expired') ||
			detail.includes('please refresh the page to reconnect') ||
			message.includes('session expired') ||
			message.includes('broker session expired') ||
			message.includes('please refresh the page to reconnect')
		) {
			return false;
		}

		// 5xx errors are retryable (except session expiration which we already checked)
		if (status && status >= 500 && status < 600) {
			return true;
		}

		// 503 (Service Unavailable) is retryable (except session expiration which we already checked)
		if (status === 503) {
			return true;
		}

		// 429 (Too Many Requests) is retryable
		if (status === 429) {
			return true;
		}
	}

	// For non-Axios errors, check the error message
	const errorMessage = extractErrorMessage(error).toLowerCase();
	if (
		errorMessage.includes('session expired') ||
		errorMessage.includes('broker session expired') ||
		errorMessage.includes('please refresh the page to reconnect')
	) {
		return false;
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
