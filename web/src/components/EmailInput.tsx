import { clsx } from 'clsx';
import type { InputHTMLAttributes } from 'react';
import { isEmailValid } from '@/utils/authValidation';

type EmailInputProps = InputHTMLAttributes<HTMLInputElement> & {
	wrapperClassName?: string;
};

function ValidEmailIcon() {
	return (
		<svg
			className="w-5 h-5"
			viewBox="0 0 20 20"
			fill="currentColor"
			aria-hidden="true"
		>
			<path
				fillRule="evenodd"
				d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"
				clipRule="evenodd"
			/>
		</svg>
	);
}

export function EmailInput({ className, wrapperClassName, value, ...props }: EmailInputProps) {
	const valid = isEmailValid(String(value ?? ''));

	return (
		<div className={clsx('relative', wrapperClassName)}>
			<input
				{...props}
				type="email"
				value={value}
				className={clsx(className, valid && 'pr-10')}
				aria-invalid={value && !valid ? true : undefined}
			/>
			{valid ? (
				<span
					className="absolute right-3 top-1/2 -translate-y-1/2 text-green-400 pointer-events-none"
					aria-label="Valid email address"
					role="status"
				>
					<ValidEmailIcon />
				</span>
			) : null}
		</div>
	);
}
