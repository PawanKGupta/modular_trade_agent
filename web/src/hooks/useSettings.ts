import { useQuery } from '@tanstack/react-query';
import { getSettings, type Settings } from '@/api/user';

/**
 * Custom hook to access user settings (trade mode, broker info)
 * Caches settings in React Query for quick access across components
 */
export function useSettings() {
	const { data, isLoading, error } = useQuery({
		queryKey: ['settings'],
		queryFn: getSettings,
		staleTime: 5 * 60 * 1000, // Consider data fresh for 5 minutes
		gcTime: 10 * 60 * 1000, // Keep in cache for 10 minutes (gcTime replaces cacheTime in v5)
	});

	const settings: Settings | undefined = data;

	return {
		settings,
		isLoading,
		error,
		isPaperMode: settings?.trade_mode === 'paper',
		isBrokerMode: settings?.trade_mode === 'broker',
		broker: settings?.broker,
		brokerStatus: settings?.broker_status,
		isBrokerConnected: settings?.broker_status === 'Connected',
	};
}
