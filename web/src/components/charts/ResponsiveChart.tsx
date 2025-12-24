import { ReactNode } from 'react';
import { ResponsiveContainer } from 'recharts';

interface ResponsiveChartProps {
	children: ReactNode;
	height?: number | string;
	aspect?: number;
	className?: string;
}

/**
 * Wrapper for Recharts ResponsiveContainer with consistent styling
 * Ensures charts are responsive and match the app's design
 */
export function ResponsiveChart({
	children,
	height = 400,
	aspect,
	className = '',
}: ResponsiveChartProps) {
	return (
		<div className={className} style={{ height: typeof height === 'number' ? `${height}px` : height }}>
			<ResponsiveContainer width="100%" height="100%" aspect={aspect}>
				{children}
			</ResponsiveContainer>
		</div>
	);
}

