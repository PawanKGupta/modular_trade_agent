/**
 * Formats a duration in seconds to a human-readable "time ago" string.
 * Examples:
 * - 32 seconds -> "32 sec ago"
 * - 69 seconds -> "1 min ago"
 * - 3678 seconds -> "1hr ago"
 */
export function formatTimeAgo(seconds: number): string {
	const isFuture = seconds < 0;
	const absSeconds = Math.abs(seconds);

	let value: number;
	let unit: string;

	if (absSeconds < 60) {
		value = Math.floor(absSeconds);
		unit = 'sec';
	} else if (absSeconds < 3600) {
		value = Math.floor(absSeconds / 60);
		unit = 'min';
	} else if (absSeconds < 86400) {
		value = Math.floor(absSeconds / 3600);
		unit = 'hr';
	} else {
		value = Math.floor(absSeconds / 86400);
		unit = 'day';
	}

	const needsPlural = value !== 1 && (unit === 'hr' || unit === 'day');
	const pluralizedUnit = needsPlural ? `${unit}s` : unit;

	if (isFuture) {
		return `in ${value} ${pluralizedUnit}`;
	}
	return `${value} ${pluralizedUnit} ago`;
}

/**
 * Formats a duration in seconds to a human-readable duration string.
 * Examples:
 * - 32.5 seconds -> "32.5s"
 * - 69 seconds -> "1.2m"
 * - 3678 seconds -> "1.0h"
 * - 125 seconds -> "2.1m"
 */
export function formatDuration(seconds: number): string {
	if (seconds < 60) {
		return `${seconds.toFixed(1)}s`;
	} else if (seconds < 3600) {
		return `${(seconds / 60).toFixed(1)}m`;
	} else {
		return `${(seconds / 3600).toFixed(1)}h`;
	}
}
