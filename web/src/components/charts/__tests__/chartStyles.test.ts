import { describe, it, expect } from 'vitest';
import { chartStyles, getChartColor, getChartColorByIndex } from '../chartStyles';

describe('chartStyles', () => {
	it('exports themed style objects', () => {
		expect(chartStyles.line.strokeWidth).toBe(2);
		expect(chartStyles.grid.strokeDasharray).toBe('3 3');
		expect(chartStyles.tooltip.contentStyle.borderRadius).toBe('6px');
	});

	it('returns colors from theme helpers', () => {
		expect(getChartColor('primary')).toBeTruthy();
		expect(getChartColorByIndex(0)).toBeTruthy();
		expect(getChartColorByIndex(99)).toBeTruthy();
	});
});
