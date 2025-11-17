interface ServiceControlsProps {
	isRunning: boolean;
	onStart: () => void;
	onStop: () => void;
	isStarting: boolean;
	isStopping: boolean;
}

export function ServiceControls({ isRunning, onStart, onStop, isStarting, isStopping }: ServiceControlsProps) {
	return (
		<div className="flex gap-3">
			<button
				onClick={onStart}
				disabled={isRunning || isStarting || isStopping}
				className={`px-4 py-2 rounded font-medium transition-colors ${
					isRunning || isStarting || isStopping
						? 'bg-gray-600 text-gray-400 cursor-not-allowed'
						: 'bg-green-600 hover:bg-green-700 text-white'
				}`}
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
