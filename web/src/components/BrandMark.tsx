import { ReboundLogo } from '@/components/ReboundLogo';
import { APP_VERSION } from '@/appVersion';

interface BrandMarkProps {
	/** Logo graphic size in px */
	logoSize?: number;
	className?: string;
}

export function BrandMark({ logoSize = 28, className = '' }: BrandMarkProps) {
	return (
		<div className={['flex items-center gap-3', className].filter(Boolean).join(' ')}>
			<div className="w-9 h-9 shrink-0 rounded-lg bg-gradient-to-br from-[var(--accent)]/10 to-blue-600/10 flex items-center justify-center p-1.5 border border-[var(--accent)]/20 hover:border-[var(--accent)]/40 transition-colors">
				<ReboundLogo size={logoSize} variant="full" />
			</div>
			<div className="min-w-0">
				<div className="font-semibold text-sm sm:text-base text-[var(--text)] leading-tight">Rebound</div>
				<div className="text-xs text-[var(--muted)] flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
					<span>Modular Trade Agent</span>
					<span className="text-[var(--muted)]/80 tabular-nums" title={`Version ${APP_VERSION}`}>
						v{APP_VERSION}
					</span>
				</div>
			</div>
		</div>
	);
}
