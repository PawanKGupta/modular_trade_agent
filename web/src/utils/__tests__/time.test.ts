import { describe, it, expect } from 'vitest';
import { formatTimeAgo } from '../time';

describe('formatTimeAgo', () => {
	it('formats seconds less than 60 as "X sec ago"', () => {
		expect(formatTimeAgo(0)).toBe('0 sec ago');
		expect(formatTimeAgo(32)).toBe('32 sec ago');
		expect(formatTimeAgo(59)).toBe('59 sec ago');
	});

	it('formats seconds between 60 and 3599 as "X min ago"', () => {
		expect(formatTimeAgo(60)).toBe('1 min ago');
		expect(formatTimeAgo(69)).toBe('1 min ago');
		expect(formatTimeAgo(120)).toBe('2 min ago');
		expect(formatTimeAgo(3599)).toBe('59 min ago');
	});

	it('formats seconds 3600 and above as "Xhr ago"', () => {
		expect(formatTimeAgo(3600)).toBe('1hr ago');
		expect(formatTimeAgo(3678)).toBe('1hr ago');
		expect(formatTimeAgo(7200)).toBe('2hr ago');
		expect(formatTimeAgo(4238)).toBe('1hr ago');
	});
});
