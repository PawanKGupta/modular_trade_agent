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
