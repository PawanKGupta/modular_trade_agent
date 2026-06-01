import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useSavedFilters } from '../useSavedFilters';
import { api } from '@/api/client';

vi.mock('@/api/client', () => ({
	api: {
		get: vi.fn(),
		post: vi.fn(),
		delete: vi.fn(),
	},
}));

describe('useSavedFilters', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(api.get).mockResolvedValue({ data: { presets: { Default: { limit: 10 } } } });
		vi.mocked(api.post).mockResolvedValue({ data: { presets: { Default: { limit: 10 }, New: { limit: 20 } } } });
		vi.mocked(api.delete).mockResolvedValue({});
	});

	it('loads presets on mount', async () => {
		const { result } = renderHook(() => useSavedFilters('orders'));

		await waitFor(() => {
			expect(result.current.presets).toEqual({ Default: { limit: 10 } });
			expect(result.current.loading).toBe(false);
		});
		expect(api.get).toHaveBeenCalledWith('/user/filter-presets/orders');
	});

	it('saves and deletes presets', async () => {
		const { result } = renderHook(() => useSavedFilters('signals'));

		await waitFor(() => expect(result.current.loading).toBe(false));

		let saved = false;
		await act(async () => {
			saved = await result.current.savePreset('New', { limit: 20 });
		});
		expect(saved).toBe(true);
		expect(api.post).toHaveBeenCalledWith('/user/filter-presets', {
			page: 'signals',
			preset_name: 'New',
			filters: { limit: 20 },
		});

		await act(async () => {
			await result.current.deletePreset('Default');
		});
		expect(api.delete).toHaveBeenCalledWith('/user/filter-presets/signals/Default');
	});

	it('handles load errors', async () => {
		vi.mocked(api.get).mockRejectedValue({
			response: { data: { detail: 'Server error' } },
		});

		const { result } = renderHook(() => useSavedFilters('orders'));

		await waitFor(() => {
			expect(result.current.error).toBe('Server error');
			expect(result.current.presets).toEqual({});
		});
	});

	it('handles save and delete errors', async () => {
		const { result } = renderHook(() => useSavedFilters('orders'));
		await waitFor(() => expect(result.current.loading).toBe(false));

		vi.mocked(api.post).mockRejectedValue({ response: { data: { detail: 'Save failed' } } });
		let saved = true;
		await act(async () => {
			saved = await result.current.savePreset('Bad', { limit: 1 });
		});
		expect(saved).toBe(false);
		expect(result.current.error).toBe('Save failed');

		vi.mocked(api.delete).mockRejectedValue({ response: { data: { detail: 'Delete failed' } } });
		let deleted = true;
		await act(async () => {
			deleted = await result.current.deletePreset('Default');
		});
		expect(deleted).toBe(false);
		expect(result.current.error).toBe('Delete failed');
	});
});
