/**
 * Formats a duration in seconds to a human-readable "time ago" string.
 * Examples:
 * - 32 seconds -> "32 sec ago"
 * - 69 seconds -> "1 min ago"
 * - 3678 seconds -> "1hr ago"
 */
export function formatTimeAgo(seconds: number): string {
	if (seconds < 60) {
		return `${seconds} sec ago`;
	}
	if (seconds < 3600) {
		const minutes = Math.floor(seconds / 60);
		return `${minutes} min ago`;
	}
	const hours = Math.floor(seconds / 3600);
	return `${hours}hr ago`;
}
