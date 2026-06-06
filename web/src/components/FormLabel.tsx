import { clsx } from 'clsx';
import type { LabelHTMLAttributes, ReactNode } from 'react';

type FormLabelProps = LabelHTMLAttributes<HTMLLabelElement> & {
	required?: boolean;
	children: ReactNode;
};

export function FormLabel({ required, children, className, ...props }: FormLabelProps) {
	return (
		<label
			{...props}
			className={clsx('block text-xs sm:text-sm mb-1', className)}
		>
			{children}
			{required ? (
				<>
					<span className="text-red-400 ml-0.5" aria-hidden="true">
						*
					</span>
					<span className="sr-only"> (required)</span>
				</>
			) : null}
		</label>
	);
}
