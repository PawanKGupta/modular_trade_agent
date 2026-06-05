export type FieldError = {
	field: string;
	message: string;
};

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateEmail(email: string): string | null {
	const trimmed = email.trim();
	if (!trimmed) {
		return 'Email is required';
	}
	if (!EMAIL_PATTERN.test(trimmed)) {
		return 'Enter a valid email address';
	}
	return null;
}

export function validatePassword(password: string): string | null {
	if (!password) {
		return 'Password is required';
	}
	if (password.length < 8) {
		return 'Password must be at least 8 characters';
	}
	if (!/[a-zA-Z]/.test(password)) {
		return 'Password must include at least one letter';
	}
	if (!/[0-9]/.test(password)) {
		return 'Password must include at least one number';
	}
	return null;
}

export function validatePasswordConfirm(password: string, confirmPassword: string): string | null {
	if (!confirmPassword) {
		return 'Please confirm your password';
	}
	if (password !== confirmPassword) {
		return 'Passwords do not match';
	}
	return null;
}

export function validateLoginForm(input: { email: string; password: string }): FieldError[] {
	const errors: FieldError[] = [];
	const emailError = validateEmail(input.email);
	if (emailError) {
		errors.push({ field: 'email', message: emailError });
	}
	if (!input.password) {
		errors.push({ field: 'password', message: 'Password is required' });
	}
	return errors;
}

export function validateResetPasswordForm(input: {
	password: string;
	confirmPassword: string;
}): FieldError[] {
	const errors: FieldError[] = [];
	const passwordError = validatePassword(input.password);
	if (passwordError) {
		errors.push({ field: 'password', message: passwordError });
	}
	const confirmError = validatePasswordConfirm(input.password, input.confirmPassword);
	if (confirmError) {
		errors.push({ field: 'confirmPassword', message: confirmError });
	}
	return errors;
}

export function validateChangePasswordForm(input: {
	currentPassword: string;
	newPassword: string;
	confirmPassword: string;
}): FieldError[] {
	const errors: FieldError[] = [];
	if (!input.currentPassword) {
		errors.push({ field: 'currentPassword', message: 'Current password is required' });
	}
	const passwordError = validatePassword(input.newPassword);
	if (passwordError) {
		errors.push({ field: 'newPassword', message: passwordError });
	}
	const confirmError = validatePasswordConfirm(input.newPassword, input.confirmPassword);
	if (confirmError) {
		errors.push({ field: 'confirmPassword', message: confirmError });
	}
	return errors;
}

export function fieldErrorFor(errors: FieldError[], field: string): string | null {
	return errors.find((e) => e.field === field)?.message ?? null;
}
