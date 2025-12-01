interface ServiceControlsProps {
	isRunning: boolean;
	onStart: () => void;
	onStop: () => void;
	isStarting: boolean;
	isStopping: boolean;
	anyIndividualServiceRunning?: boolean;
	anyRunOnceRunning?: boolean;
}

export function ServiceControls({
	isRunning,
	onStart,
	onStop,
	isStarting,
	isStopping,
	anyIndividualServiceRunning = false,
	anyRunOnceRunning = false
}: ServiceControlsProps) {
	const isDisabled = isRunning || isStarting || isStopping || anyIndividualServiceRunning || anyRunOnceRunning;

	const getDisabledReason = () => {
		if (isRunning) return 'Service is already running';
		if (anyIndividualServiceRunning) return 'Cannot start unified service while individual services are running';
		if (anyRunOnceRunning) return 'Cannot start unified service while run-once tasks are executing';
		return 'Start the unified service';
	};

	return (
		<div className="flex gap-3">
			<button
				onClick={onStart}
				disabled={isDisabled}
				className={`px-4 py-2 rounded font-medium transition-colors ${
					isDisabled
						? 'bg-gray-600 text-gray-400 cursor-not-allowed'
						: 'bg-green-600 hover:bg-green-700 text-white'
				}`}
				title={getDisabledReason()}
			>
				{isStarting ? 'Starting...' : 'Start Service'}
			</button>
			<button
				onClick={onStop}
				disabled={!isRunning || isStarting || isStopping}
				className={`px-4 py-2 rounded font-medium transition-colors ${
					!isRunning || isStarting || isStopping
						? 'bg-gray-600 text-gray-400 cursor-not-allowed'
						: 'bg-red-600 hover:bg-red-700 text-white'
				}`}
			>
				{isStopping ? 'Stopping...' : 'Stop Service'}
			</button>
		</div>
	);
}
