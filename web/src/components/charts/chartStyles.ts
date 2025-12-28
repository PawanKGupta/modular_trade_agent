import { chartTheme } from './chartTheme';

/**
 * Recharts-compatible style objects for consistent theming
 * These can be passed directly to Recharts components
 */

export const chartStyles = {
	// Line chart styles
	line: {
		stroke: chartTheme.accent,
		strokeWidth: 2,
		dot: {
			fill: chartTheme.accent,
			r: 4,
		},
		activeDot: {
			r: 6,
			fill: chartTheme.accent,
			stroke: chartTheme.background,
			strokeWidth: 2,
		},
	},

	// Area chart styles
	area: {
		fill: chartTheme.accent,
		fillOpacity: 0.2,
		stroke: chartTheme.accent,
		strokeWidth: 2,
	},

	// Bar chart styles
	bar: {
		fill: chartTheme.accent,
		radius: [4, 4, 0, 0], // Rounded top corners
	},

	// Cartesian grid
	grid: {
		stroke: chartTheme.grid,
		strokeWidth: 1,
		strokeDasharray: '3 3',
	},

	// X/Y axis
	axis: {
		stroke: chartTheme.axis,
		strokeWidth: 1,
		tick: {
			fill: chartTheme.textMuted,
			fontSize: 12,
		},
		label: {
			fill: chartTheme.textMuted,
			fontSize: 12,
		},
	},

	// Tooltip
	tooltip: {
		contentStyle: {
			backgroundColor: chartTheme.tooltip.background,
			border: `1px solid ${chartTheme.tooltip.border}`,
			borderRadius: '6px',
			color: chartTheme.tooltip.text,
			boxShadow: chartTheme.tooltip.shadow,
			padding: '8px 12px',
		},
		labelStyle: {
			color: chartTheme.text,
			fontWeight: 600,
		},
		itemStyle: {
			color: chartTheme.text,
		},
		cursor: {
			stroke: chartTheme.accent,
			strokeWidth: 1,
			strokeDasharray: '5 5',
		},
	},

	// Legend
	legend: {
		wrapperStyle: {
			color: chartTheme.legend.text,
			fontSize: 12,
			paddingTop: '16px',
		},
		iconSize: chartTheme.legend.iconSize,
	},

	// Reference lines
	referenceLine: {
		stroke: chartTheme.textMuted,
		strokeWidth: 1,
		strokeDasharray: '5 5',
	},
} as const;

/**
 * Get color from theme by key
 */
export function getChartColor(key: keyof typeof chartTheme.colors): string {
	return chartTheme.colors[key];
}

/**
 * Get a color from the theme's color palette by index
 * Useful for multi-series charts
 */
export function getChartColorByIndex(index: number): string {
	const colors = Object.values(chartTheme.colors);
	return colors[index % colors.length];
}

