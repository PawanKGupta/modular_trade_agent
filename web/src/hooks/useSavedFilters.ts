import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

type FilterPreset = Record<string, unknown>;

interface FilterPresetsResponse {
  presets: Record<string, FilterPreset>;
}

/**
 * Custom hook for managing saved filter presets
 * @param page - Page identifier (e.g., 'signals', 'orders', 'trades')
 */
export function useSavedFilters(page: string) {
  const [presets, setPresets] = useState<Record<string, FilterPreset>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load presets from backend
  const loadPresets = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.get<FilterPresetsResponse>(
        `/user/filter-presets/${page}`
      );
      setPresets(response.data.presets || {});
    } catch (err: unknown) {
      console.error('Error loading filter presets:', err);
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      setError(detail || 'Failed to load presets');
      setPresets({});
    } finally {
      setLoading(false);
    }
  }, [page]);

  // Save a new preset
  const savePreset = useCallback(
    async (presetName: string, filters: FilterPreset) => {
      try {
        setLoading(true);
        setError(null);
        const response = await api.post<FilterPresetsResponse>(
          '/user/filter-presets',
          {
            page,
            preset_name: presetName,
            filters,
          }
        );
        setPresets(response.data.presets || {});
        return true;
      } catch (err: unknown) {
        console.error('Error saving filter preset:', err);
        const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
        setError(detail || 'Failed to save preset');
        return false;
      } finally {
        setLoading(false);
      }
    },
    [page]
  );

  // Delete a preset
  const deletePreset = useCallback(
    async (presetName: string) => {
      try {
        setLoading(true);
        setError(null);
        await api.delete(`/user/filter-presets/${page}/${presetName}`);
        // Reload presets after deletion
        await loadPresets();
        return true;
      } catch (err: unknown) {
        console.error('Error deleting filter preset:', err);
        const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
        setError(detail || 'Failed to delete preset');
        return false;
      } finally {
        setLoading(false);
      }
    },
    [page, loadPresets]
  );

  // Load presets on mount
  useEffect(() => {
    loadPresets();
  }, [loadPresets]);

  return {
    presets,
    loading,
    error,
    savePreset,
    deletePreset,
    reloadPresets: loadPresets,
  };
}
