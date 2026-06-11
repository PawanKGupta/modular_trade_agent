/** API timestamps are UTC ISO strings; display in IST for NSE trading context. */
export const API_DISPLAY_TIME_ZONE = 'Asia/Kolkata';

const apiDateTimeFormatter = new Intl.DateTimeFormat('en-IN', {
	timeZone: API_DISPLAY_TIME_ZONE,
	day: '2-digit',
	month: 'short',
	year: 'numeric',
	hour: '2-digit',
	minute: '2-digit',
	second: '2-digit',
	hour12: true,
});

/** Parse a UTC ISO timestamp from the API. */
export function parseApiUtcIso(iso: string): Date {
	return new Date(iso);
}

/** Format API UTC ISO as IST wall-clock for display. */
export function formatApiDateTime(iso: string): string {
	return apiDateTimeFormatter.format(parseApiUtcIso(iso));
}

/** Seconds elapsed since an API UTC ISO timestamp (negative if in the future). */
export function secondsAgoFromApiIso(iso: string): number {
	return Math.floor((Date.now() - parseApiUtcIso(iso).getTime()) / 1000);
}

/**
 * Single-line API timestamp: IST clock + relative age from the same instant.
 * Avoids showing two conflicting times via browser locale + manual age math.
 */
export function formatApiTimestampDisplay(iso: string | null | undefined): string {
	if (!iso) {
		return 'Never';
	}
	return `${formatApiDateTime(iso)} IST · ${formatTimeAgo(secondsAgoFromApiIso(iso))}`;
}

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
