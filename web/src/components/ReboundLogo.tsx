interface ReboundLogoProps {
	size?: number;
	className?: string;
	variant?: 'full' | 'icon';
}

export function ReboundLogo({ size = 32, className = '', variant = 'full' }: ReboundLogoProps) {
	const uniqueId = `rebound-${Math.random().toString(36).substr(2, 9)}`;

	return (
		<svg
			width={size}
			height={size}
			viewBox="0 0 32 32"
			fill="none"
			xmlns="http://www.w3.org/2000/svg"
			className={className}
		>
			{/* Gradient definitions */}
			<defs>
				<linearGradient id={`reboundGradient-${uniqueId}`} x1="0%" y1="100%" x2="100%" y2="0%">
					<stop offset="0%" stopColor="#4fc3f7" />
					<stop offset="50%" stopColor="#29b6f6" />
					<stop offset="100%" stopColor="#0288d1" />
				</linearGradient>
				<linearGradient id={`reboundGlow-${uniqueId}`} x1="0%" y1="100%" x2="100%" y2="0%">
					<stop offset="0%" stopColor="#4fc3f7" stopOpacity="0.25" />
					<stop offset="100%" stopColor="#0288d1" stopOpacity="0.4" />
				</linearGradient>
			</defs>

			{/* Subtle background glow (only for full variant) */}
			{variant === 'full' && (
				<circle
					cx="16"
					cy="16"
					r="14"
					fill={`url(#reboundGlow-${uniqueId})`}
				/>
			)}

			{/* Main rebound curve - elegant upward bounce */}
			<path
				d="M 7 23 Q 11 13, 16 15 T 25 9"
				stroke={`url(#reboundGradient-${uniqueId})`}
				strokeWidth="2.5"
				fill="none"
				strokeLinecap="round"
				strokeLinejoin="round"
			/>

			{/* Arrow head pointing upward - momentum indicator */}
			<path
				d="M 23.5 10.5 L 25 9 L 23.5 7.5"
				stroke={`url(#reboundGradient-${uniqueId})`}
				strokeWidth="2.5"
				fill="none"
				strokeLinecap="round"
				strokeLinejoin="round"
			/>

			{/* Starting point - bounce origin */}
			<circle
				cx="7"
				cy="23"
				r="2.5"
				fill={`url(#reboundGradient-${uniqueId})`}
			/>

			{/* Subtle pulse effect at origin */}
			{variant === 'full' && (
				<>
					<circle
						cx="7"
						cy="23"
						r="4"
						fill="none"
						stroke={`url(#reboundGradient-${uniqueId})`}
						strokeWidth="1"
						opacity="0.4"
					/>
					<circle
						cx="7"
						cy="23"
						r="6"
						fill="none"
						stroke={`url(#reboundGradient-${uniqueId})`}
						strokeWidth="0.8"
						opacity="0.2"
					/>
				</>
			)}

			{/* Momentum dots along the curve (subtle) */}
			{variant === 'full' && (
				<>
					<circle
						cx="11"
						cy="19"
						r="1"
						fill={`url(#reboundGradient-${uniqueId})`}
						opacity="0.6"
					/>
					<circle
						cx="16"
						cy="15"
						r="1"
						fill={`url(#reboundGradient-${uniqueId})`}
						opacity="0.7"
					/>
					<circle
						cx="20"
						cy="12"
						r="1"
						fill={`url(#reboundGradient-${uniqueId})`}
						opacity="0.8"
					/>
				</>
			)}
		</svg>
	);
}
