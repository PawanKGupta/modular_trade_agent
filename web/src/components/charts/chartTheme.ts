/**
 * Chart theme configuration matching the application's dark theme
 * Used by Recharts components to ensure consistent styling
 */

export const chartTheme = {
	// Background colors
	background: '#121923', // --panel
	backgroundSecondary: '#0f1720', // Darker panel variant
	backgroundTertiary: '#0b0f14', // --bg

	// Text colors
	text: '#e6edf3', // --text
	textMuted: '#9aa4af', // --muted
	textSecondary: '#cbd5e1',

	// Accent color
	accent: '#4fc3f7', // --accent

	// Border colors
	border: '#1e293b',
	borderLight: '#334155',

	// Grid and axis colors
	grid: '#1e293b',
	axis: '#9aa4af',

	// Chart colors (for multi-series charts)
	colors: {
		primary: '#4fc3f7', // --accent
		success: '#10b981', // Green for profits
		danger: '#ef4444', // Red for losses
		warning: '#f59e0b', // Orange/yellow
		info: '#3b82f6', // Blue
		purple: '#8b5cf6',
		pink: '#ec4899',
		teal: '#14b8a6',
	},

	// Tooltip styling
	tooltip: {
		background: '#1e293b',
		border: '#334155',
		text: '#e6edf3',
		shadow: '0 4px 6px -1px rgba(0, 0, 0, 0.3)',
	},

	// Legend styling
	legend: {
		text: '#9aa4af',
		iconSize: 12,
	},

	// Responsive breakpoints (matching Tailwind defaults)
	breakpoints: {
		sm: 640,
		md: 768,
		lg: 1024,
		xl: 1280,
	},
} as const;

export type ChartTheme = typeof chartTheme;

