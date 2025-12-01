import { useQuery } from '@tanstack/react-query';
import {
	getIndividualServicesStatus,
	type IndividualServicesStatus,
} from '@/api/service';
import { IndividualServiceControls } from './IndividualServiceControls';
import { useSessionStore } from '@/state/sessionStore';

interface IndividualServicesSectionProps {
	unifiedServiceRunning: boolean;
}

export function IndividualServicesSection({
	unifiedServiceRunning,
}: IndividualServicesSectionProps) {
	const { isAdmin } = useSessionStore();
	const { data: individualStatus, isLoading } = useQuery<IndividualServicesStatus>({
		queryKey: ['individualServicesStatus'],
		queryFn: getIndividualServicesStatus,
		refetchInterval: 5000, // Refresh every 5 seconds
	});

	if (isLoading) {
		return (
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-6">
				<div className="text-[var(--text)]">Loading individual services...</div>
			</div>
		);
	}

	const services = individualStatus?.services || {};
	const serviceEntries = Object.entries(services);

	if (serviceEntries.length === 0) {
		return (
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-6">
				<div className="text-[var(--text)]">No individual services available</div>
			</div>
		);
	}

	// Filter out analysis service for non-admin users (admin-only service)
	const userServices = serviceEntries.filter(
		([taskName]) => isAdmin || taskName !== 'analysis'
	);

	return (
		<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-6">
			<div className="mb-4">
				<h2 className="text-lg font-semibold text-[var(--text)] mb-2">
					Individual Service Management
				</h2>
				<p className="text-sm text-[var(--muted)]">
					{unifiedServiceRunning
						? 'Unified service is running. Individual services and most "Run Once" tasks are disabled to prevent broker session conflicts.'
						: 'Start individual services to run specific tasks on their own schedule.'}
				</p>
			</div>

			<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
				{userServices.map(([taskName, service]) => (
					<IndividualServiceControls
						key={taskName}
						service={service}
						unifiedServiceRunning={unifiedServiceRunning}
					/>
				))}
			</div>
		</div>
	);
}
