export type FieldError = {
	field: string;
	message: string;
};

export type PasswordRequirement = {
	id: string;
	label: string;
	met: boolean;
};

export const PASSWORD_MIN_LENGTH = 8;

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

/** Live checklist rules for email fields (signup, login, etc.). */
export function getEmailRequirements(email: string): PasswordRequirement[] {
	const trimmed = email.trim();
	return [
		{
			id: 'present',
			label: 'Email address entered',
			met: trimmed.length > 0,
		},
		{
			id: 'format',
			label: 'Valid format (name@example.com)',
			met: trimmed.length > 0 && EMAIL_PATTERN.test(trimmed),
		},
	];
}

export function isEmailValid(email: string): boolean {
	return getEmailRequirements(email).every((rule) => rule.met);
}

const INDIAN_MOBILE_PATTERN = /^[6-9]\d{9}$/;

export function normalizeMobileDigits(mobile: string): string {
	return mobile.replace(/\D/g, '');
}

export function validateMobile(mobile: string): string | null {
	const trimmed = mobile.trim();
	if (!trimmed) {
		return null;
	}
	const digits = normalizeMobileDigits(trimmed);
	if (!INDIAN_MOBILE_PATTERN.test(digits)) {
		return 'Enter a valid 10-digit Indian mobile number';
	}
	return null;
}

export function validateName(name: string): string | null {
	const trimmed = name.trim();
	if (!trimmed) {
		return 'Name is required';
	}
	if (trimmed.length > 255) {
		return 'Name must be 255 characters or fewer';
	}
	return null;
}

export function getPasswordRequirements(password: string): PasswordRequirement[] {
	return [
		{
			id: 'length',
			label: `At least ${PASSWORD_MIN_LENGTH} characters`,
			met: password.length >= PASSWORD_MIN_LENGTH,
		},
		{
			id: 'letter',
			label: 'At least one letter',
			met: /[a-zA-Z]/.test(password),
		},
		{
			id: 'uppercase',
			label: 'At least one capital letter',
			met: /[A-Z]/.test(password),
		},
		{
			id: 'number',
			label: 'At least one number',
			met: /[0-9]/.test(password),
		},
		{
			id: 'special',
			label: 'At least one special character',
			met: /[^a-zA-Z0-9]/.test(password),
		},
	];
}

export function isPasswordValid(password: string): boolean {
	return getPasswordRequirements(password).every((rule) => rule.met);
}

export function validatePassword(password: string): string | null {
	if (!password) {
		return 'Password is required';
	}
	if (!isPasswordValid(password)) {
		const unmet = getPasswordRequirements(password)
			.filter((rule) => !rule.met)
			.map((rule) => rule.label.toLowerCase());
		return `Password must include ${unmet.join(', ')}`;
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

export function validateSignupForm(input: {
	name: string;
	email: string;
	password: string;
	confirmPassword: string;
	mobile?: string;
}): FieldError[] {
	const errors: FieldError[] = [];
	const nameError = validateName(input.name);
	if (nameError) {
		errors.push({ field: 'name', message: nameError });
	}
	const emailError = validateEmail(input.email);
	if (emailError) {
		errors.push({ field: 'email', message: emailError });
	}
	const mobileError = validateMobile(input.mobile ?? '');
	if (mobileError) {
		errors.push({ field: 'mobile', message: mobileError });
	}
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

export function validateAdminCreateUserForm(input: {
	email: string;
	name: string;
	password: string;
}): FieldError[] {
	const errors: FieldError[] = [];
	const nameError = validateName(input.name);
	if (nameError) {
		errors.push({ field: 'name', message: nameError });
	}
	const emailError = validateEmail(input.email);
	if (emailError) {
		errors.push({ field: 'email', message: emailError });
	}
	const passwordError = validatePassword(input.password);
	if (passwordError) {
		errors.push({ field: 'password', message: passwordError });
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

export function validateProfileForm(input: { email: string; mobile?: string }): FieldError[] {
	const errors: FieldError[] = [];
	const emailError = validateEmail(input.email);
	if (emailError) {
		errors.push({ field: 'profileEmail', message: emailError });
	}
	const mobileError = validateMobile(input.mobile ?? '');
	if (mobileError) {
		errors.push({ field: 'profileMobile', message: mobileError });
	}
	return errors;
}

export function fieldErrorFor(errors: FieldError[], field: string): string | null {
	return errors.find((e) => e.field === field)?.message ?? null;
}
