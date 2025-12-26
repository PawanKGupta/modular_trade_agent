import { ReactNode } from 'react';
import { chartTheme } from './chartTheme';

interface ChartContainerProps {
	children: ReactNode;
	title?: string;
	description?: string;
	className?: string;
	height?: number | string;
}

/**
 * Container component for charts with consistent styling
 * Provides a panel-like container matching the app's design system
 */
export function ChartContainer({
	children,
	title,
	description,
	className = '',
	height = 400,
}: ChartContainerProps) {
	return (
		<div
			className={`bg-[var(--panel)] border border-[#1e293b] rounded-lg p-4 sm:p-6 overflow-hidden ${className}`}
			style={{ minHeight: typeof height === 'number' ? `${height}px` : height }}
		>
			{(title || description) && (
				<div className="mb-4">
					{title && (
						<h3 className="text-base sm:text-lg font-semibold text-[var(--text)] mb-1">
							{title}
						</h3>
					)}
					{description && (
						<p className="text-xs sm:text-sm text-[var(--muted)]">{description}</p>
					)}
				</div>
			)}
			<div className="w-full overflow-hidden" style={{ height: typeof height === 'number' ? `${height}px` : height }}>
				{children}
			</div>
		</div>
	);
}
