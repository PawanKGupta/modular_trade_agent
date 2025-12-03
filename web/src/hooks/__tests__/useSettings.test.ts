import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useSettings } from '../useSettings';
import * as userApi from '@/api/user';
import type { Settings } from '@/api/user';
import type { ReactNode } from 'react';

// Mock the user API
vi.mock('@/api/user', () => ({
	getSettings: vi.fn(),
}));

function createWrapper() {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: {
				retry: false,
				refetchOnWindowFocus: false,
			},
		},
	});

	return ({ children }: { children: ReactNode }) => (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
}

describe('useSettings', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('returns paper mode settings correctly', async () => {
		const mockSettings: Settings = {
			trade_mode: 'paper',
			broker: null,
			broker_status: null,
		};

		vi.mocked(userApi.getSettings).mockResolvedValue(mockSettings);

		const { result } = renderHook(() => useSettings(), {
			wrapper: createWrapper(),
		});

		expect(result.current.isLoading).toBe(true);

		await waitFor(() => {
			expect(result.current.isLoading).toBe(false);
		});

		expect(result.current.settings).toEqual(mockSettings);
		expect(result.current.isPaperMode).toBe(true);
		expect(result.current.isBrokerMode).toBe(false);
		expect(result.current.broker).toBeNull();
		expect(result.current.brokerStatus).toBeNull();
		expect(result.current.isBrokerConnected).toBe(false);
	});

	it('returns broker mode settings correctly', async () => {
		const mockSettings: Settings = {
			trade_mode: 'broker',
			broker: 'kotak-neo',
			broker_status: 'Connected',
		};

		vi.mocked(userApi.getSettings).mockResolvedValue(mockSettings);

		const { result } = renderHook(() => useSettings(), {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(result.current.isLoading).toBe(false);
		});

		expect(result.current.settings).toEqual(mockSettings);
		expect(result.current.isPaperMode).toBe(false);
		expect(result.current.isBrokerMode).toBe(true);
		expect(result.current.broker).toBe('kotak-neo');
		expect(result.current.brokerStatus).toBe('Connected');
		expect(result.current.isBrokerConnected).toBe(true);
	});

	it('handles disconnected broker status', async () => {
		const mockSettings: Settings = {
			trade_mode: 'broker',
			broker: 'kotak-neo',
			broker_status: 'Disconnected',
		};

		vi.mocked(userApi.getSettings).mockResolvedValue(mockSettings);

		const { result } = renderHook(() => useSettings(), {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(result.current.isLoading).toBe(false);
		});

		expect(result.current.isBrokerMode).toBe(true);
		expect(result.current.isBrokerConnected).toBe(false);
		expect(result.current.brokerStatus).toBe('Disconnected');
	});

	it('handles undefined settings gracefully', async () => {
		vi.mocked(userApi.getSettings).mockResolvedValue(undefined as any);

		const { result } = renderHook(() => useSettings(), {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(result.current.isLoading).toBe(false);
		});

		expect(result.current.settings).toBeUndefined();
		expect(result.current.isPaperMode).toBe(false);
		expect(result.current.isBrokerMode).toBe(false);
		expect(result.current.isBrokerConnected).toBe(false);
	});

	it('handles error state', async () => {
		const error = new Error('Failed to fetch settings');
		vi.mocked(userApi.getSettings).mockRejectedValue(error);

		const { result } = renderHook(() => useSettings(), {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(result.current.isLoading).toBe(false);
		});

		expect(result.current.error).toBeDefined();
		expect(result.current.settings).toBeUndefined();
	});

	it('caches settings for quick access', async () => {
		const mockSettings: Settings = {
			trade_mode: 'paper',
			broker: null,
			broker_status: null,
		};

		vi.mocked(userApi.getSettings).mockResolvedValue(mockSettings);

		const wrapper = createWrapper();

		// First render
		const { result: result1 } = renderHook(() => useSettings(), {
			wrapper,
		});

		await waitFor(() => {
			expect(result1.current.isLoading).toBe(false);
		});

		// Second render - should use cached data
		const { result: result2 } = renderHook(() => useSettings(), {
			wrapper,
		});

		// Should not be loading if cached
		expect(result2.current.settings).toBeDefined();
		expect(userApi.getSettings).toHaveBeenCalledTimes(1);
	});
});
