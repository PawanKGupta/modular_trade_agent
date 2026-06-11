import { vi } from 'vitest';
import {
	formatApiDateTime,
	formatApiTimestampDisplay,
	formatDuration,
	formatTimeAgo,
	secondsAgoFromApiIso,
} from '../time';

describe('formatTimeAgo', () => {
	it('formats seconds less than 60 as "X sec ago"', () => {
		expect(formatTimeAgo(0)).toBe('0 sec ago');
		expect(formatTimeAgo(32)).toBe('32 sec ago');
		expect(formatTimeAgo(59)).toBe('59 sec ago');
	});

	it('formats minutes correctly', () => {
		expect(formatTimeAgo(60)).toBe('1 min ago');
		expect(formatTimeAgo(69)).toBe('1 min ago');
		expect(formatTimeAgo(120)).toBe('2 min ago');
		expect(formatTimeAgo(3599)).toBe('59 min ago');
	});

	it('formats hours correctly', () => {
		expect(formatTimeAgo(3600)).toBe('1 hr ago');
		expect(formatTimeAgo(3678)).toBe('1 hr ago');
		expect(formatTimeAgo(7200)).toBe('2 hrs ago');
		expect(formatTimeAgo(4238)).toBe('1 hr ago');
	});

	it('formats days correctly', () => {
		expect(formatTimeAgo(86400)).toBe('1 day ago');
		expect(formatTimeAgo(172800)).toBe('2 days ago');
	});

	it('handles future times with "in" prefix', () => {
		expect(formatTimeAgo(-30)).toBe('in 30 sec');
		expect(formatTimeAgo(-120)).toBe('in 2 min');
		expect(formatTimeAgo(-3600)).toBe('in 1 hr');
		expect(formatTimeAgo(-86400)).toBe('in 1 day');
	});
});

describe('formatApiDateTime', () => {
	it('formats UTC ISO as IST wall-clock', () => {
		// 18:13:49 UTC = 23:43:49 IST
		expect(formatApiDateTime('2026-06-11T18:13:49.000Z')).toMatch(/11 Jun 2026/i);
		expect(formatApiDateTime('2026-06-11T18:13:49.000Z')).toMatch(/11:43:49\s*pm/i);
	});
});

describe('formatApiTimestampDisplay', () => {
	it('combines IST time and relative age from one instant', () => {
		const now = new Date('2026-06-11T18:14:19.000Z').getTime();
		vi.spyOn(Date, 'now').mockReturnValue(now);
		const iso = '2026-06-11T18:13:49.000Z';
		const display = formatApiTimestampDisplay(iso);
		expect(display).toContain('IST ·');
		expect(display).toMatch(/11:43:49\s*pm/i);
		expect(display).toContain('30 sec ago');
		expect(secondsAgoFromApiIso(iso)).toBe(30);
		vi.restoreAllMocks();
	});

	it('returns Never for null', () => {
		expect(formatApiTimestampDisplay(null)).toBe('Never');
	});
});

describe('formatDuration', () => {
	it('formats seconds less than 60 as "X.Xs"', () => {
		expect(formatDuration(0)).toBe('0.0s');
		expect(formatDuration(32.5)).toBe('32.5s');
		expect(formatDuration(59.9)).toBe('59.9s');
	});

	it('formats minutes correctly as "X.Xm"', () => {
		expect(formatDuration(60)).toBe('1.0m');
		expect(formatDuration(90)).toBe('1.5m');
		expect(formatDuration(125)).toBe('2.1m');
		expect(formatDuration(3599)).toBe('60.0m');
	});

	it('formats hours correctly as "X.Xh"', () => {
		expect(formatDuration(3600)).toBe('1.0h');
		expect(formatDuration(5400)).toBe('1.5h');
		expect(formatDuration(9000)).toBe('2.5h');
		expect(formatDuration(7200)).toBe('2.0h');
	});
});
