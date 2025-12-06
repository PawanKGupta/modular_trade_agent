import { useQuery } from '@tanstack/react-query';
import { getSettings, getBrokerStatus, type Settings } from '@/api/user';

/**
 * Custom hook to access user settings (trade mode, broker info)
 * Caches settings in React Query for quick access across components
 * Polls broker status when in broker mode
 */
export function useSettings() {
	const { data, isLoading, error } = useQuery({
		queryKey: ['settings'],
		queryFn: getSettings,
		staleTime: 5 * 60 * 1000, // Consider data fresh for 5 minutes
		gcTime: 10 * 60 * 1000, // Keep in cache for 10 minutes (gcTime replaces cacheTime in v5)
		refetchInterval: 30 * 1000, // Refetch every 30 seconds to get updated broker status
	});

	const settings: Settings | undefined = data;
	const isBrokerMode = settings?.trade_mode === 'broker';

	// Poll broker status separately when in broker mode for more frequent updates
	const { data: brokerStatusData } = useQuery({
		queryKey: ['broker-status'],
		queryFn: getBrokerStatus,
		enabled: isBrokerMode, // Only poll when in broker mode
		refetchInterval: 60 * 1000, // Poll every 60 seconds for connection status (reduced from 10s to avoid frequent checks)
		staleTime: 5 * 1000, // Consider stale after 5 seconds
	});

	// Use broker status from dedicated endpoint if available, otherwise fall back to settings
	const effectiveBrokerStatus = brokerStatusData?.status ?? settings?.broker_status;
	const effectiveBroker = brokerStatusData?.broker ?? settings?.broker;

	return {
		settings,
		isLoading,
		error,
		isPaperMode: settings?.trade_mode === 'paper',
		isBrokerMode,
		broker: effectiveBroker,
		brokerStatus: effectiveBrokerStatus,
		isBrokerConnected: effectiveBrokerStatus === 'Connected',
	};
}
