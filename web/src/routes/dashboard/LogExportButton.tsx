import type { ServiceLogEntry } from '@/api/logs';

type Props = {
	logs: ServiceLogEntry[];
};

export function LogExportButton({ logs }: Props) {
	const exportToCSV = () => {
		if (logs.length === 0) {
			alert('No logs to export');
			return;
		}

		// CSV Header
		const headers = ['Timestamp', 'Level', 'Module', 'Message', 'Context'];
		const csvRows = [headers.join(',')];

		// CSV Data
		for (const log of logs) {
			const timestamp = new Date(log.timestamp).toISOString();
			const level = log.level;
			const module = log.module.replace(/,/g, ';'); // Escape commas
			const message = log.message.replace(/,/g, ';').replace(/"/g, '""'); // Escape commas and quotes
			const context = log.context ? JSON.stringify(log.context).replace(/,/g, ';').replace(/"/g, '""') : '';

			csvRows.push(`"${timestamp}","${level}","${module}","${message}","${context}"`);
		}

		const csvContent = csvRows.join('\n');
		const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
		const url = URL.createObjectURL(blob);
		const link = document.createElement('a');
		const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
		link.href = url;
		link.download = `logs_${timestamp}.csv`;
		link.click();
		URL.revokeObjectURL(url);
	};

	const exportToJSON = () => {
		if (logs.length === 0) {
			alert('No logs to export');
			return;
		}

		const jsonContent = JSON.stringify(logs, null, 2);
		const blob = new Blob([jsonContent], { type: 'application/json;charset=utf-8;' });
		const url = URL.createObjectURL(blob);
		const link = document.createElement('a');
		const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
		link.href = url;
		link.download = `logs_${timestamp}.json`;
		link.click();
		URL.revokeObjectURL(url);
	};

	return (
		<div className="flex gap-2">
			<button
				type="button"
				onClick={exportToCSV}
				disabled={logs.length === 0}
				className="px-3 py-1.5 text-xs sm:text-sm bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded transition-colors"
			>
				Export CSV
			</button>
			<button
				type="button"
				onClick={exportToJSON}
				disabled={logs.length === 0}
				className="px-3 py-1.5 text-xs sm:text-sm bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded transition-colors"
			>
				Export JSON
			</button>
		</div>
	);
}
