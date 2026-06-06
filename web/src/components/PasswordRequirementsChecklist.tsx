import { clsx } from 'clsx';
import { getPasswordRequirements } from '@/utils/authValidation';

type PasswordRequirementsChecklistProps = {
	password: string;
	className?: string;
};

export function PasswordRequirementsChecklist({ password, className }: PasswordRequirementsChecklistProps) {
	const requirements = getPasswordRequirements(password);
	const showStatus = password.length > 0;

	return (
		<ul
			className={clsx('text-xs sm:text-sm space-y-1 mb-2 mt-1', className)}
			aria-live="polite"
			aria-label="Password requirements"
		>
			{requirements.map((rule) => (
				<li
					key={rule.id}
					className={clsx(
						'flex items-center gap-2',
						showStatus && rule.met && 'text-green-400',
						showStatus && !rule.met && 'text-[var(--muted)]',
						!showStatus && 'text-[var(--muted)]',
					)}
				>
					<span aria-hidden="true" className="w-4 text-center shrink-0">
						{showStatus ? (rule.met ? '✓' : '○') : '•'}
					</span>
					<span>{rule.label}</span>
				</li>
			))}
		</ul>
	);
}

type PasswordConfirmHintProps = {
	password: string;
	confirmPassword: string;
	className?: string;
};

export function PasswordConfirmHint({ password, confirmPassword, className }: PasswordConfirmHintProps) {
	if (!confirmPassword) {
		return null;
	}
	const matches = password === confirmPassword;
	return (
		<p
			className={clsx(
				'text-xs sm:text-sm mb-2 mt-1',
				matches ? 'text-green-400' : 'text-red-400',
				className,
			)}
			aria-live="polite"
		>
			{matches ? '✓ Passwords match' : 'Passwords do not match'}
		</p>
	);
}
