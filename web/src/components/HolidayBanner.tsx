import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getTradingDayInfo, type TradingDayInfo } from '../api/service';

/**
 * Holiday Banner Component
 *
 * Displays a banner on market holidays to inform users that markets are closed.
 * Features mobile-compatible marquee with touch support and accessibility options.
 */
export function HolidayBanner() {
	const [isPaused, setIsPaused] = useState(false);
	const { data: tradingDayInfo, isLoading } = useQuery<TradingDayInfo>({
		queryKey: ['trading-day-info'],
		queryFn: getTradingDayInfo,
		refetchInterval: 3600000, // Refresh every hour (holidays don't change during the day)
		staleTime: 1800000, // Consider data fresh for 30 minutes
	});

	if (isLoading || !tradingDayInfo) {
		return null;
	}

	// Only show banner on holidays (not weekends, as those are obvious)
	if (!tradingDayInfo.is_holiday) {
		return null;
	}

	const holidayName = tradingDayInfo.holiday_name || 'NSE Holiday';
	const message = `NSE Holiday: ${holidayName} - The stock market is closed today. Trading services will not execute, and signals will not be processed until the next trading day.`;

	return (
		<div className="w-full max-w-full bg-amber-500/20 border border-amber-500/50 rounded-lg mb-4 overflow-hidden">
			<div className="flex items-center gap-2 py-2 sm:py-3">
				<div className="flex-shrink-0">
					<svg
						className="w-4 h-4 sm:w-5 sm:h-5 text-amber-400"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							strokeLinecap="round"
							strokeLinejoin="round"
							strokeWidth={2}
							d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
						/>
					</svg>
				</div>
				<div
					className="flex-1 min-w-0 overflow-hidden cursor-pointer touch-manipulation"
					onClick={() => setIsPaused(!isPaused)}
					onTouchStart={() => setIsPaused(!isPaused)}
					role="button"
					tabIndex={0}
					aria-label="Tap to pause/resume holiday message"
				>
					<div
						className={`marquee-content text-sm sm:text-base font-medium text-amber-300 whitespace-nowrap ${
							isPaused ? 'paused' : ''
						}`}
					>
						<span className="inline-block">{message}</span>
						<span className="inline-block ml-8">{message}</span>
						<span className="inline-block ml-8">{message}</span>
					</div>
				</div>
			</div>
			<style>{`
				@keyframes marquee {
					0% { transform: translate3d(0, 0, 0); }
					100% { transform: translate3d(-33.333%, 0, 0); }
				}
				.marquee-content {
					animation: marquee 30s linear infinite;
					will-change: transform;
					display: inline-block;
					width: max-content;
				}
				.marquee-content.paused {
					animation-play-state: paused;
				}
				.marquee-content:hover {
					animation-play-state: paused;
				}
				/* Accessibility: Respect user's motion preferences */
				@media (prefers-reduced-motion: reduce) {
					.marquee-content {
						animation: none;
						width: 100%;
					}
					.marquee-content span {
						display: block;
					}
					.marquee-content span:not(:first-child) {
						display: none;
					}
				}
				/* Better performance on mobile */
				@media (max-width: 640px) {
					.marquee-content {
						animation-duration: 25s;
					}
				}
			`}</style>
		</div>
	);
}
