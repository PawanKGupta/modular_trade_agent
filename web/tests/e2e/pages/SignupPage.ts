import { Page, Locator } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Signup Page Object Model
 */
export class SignupPage extends BasePage {
	// Selectors
	private readonly emailInput: Locator;
	private readonly nameInput: Locator;
	private readonly passwordInput: Locator;
	private readonly signupButton: Locator;
	private readonly loginLink: Locator;
	private readonly errorMessage: Locator;
	private readonly heading: Locator;

	constructor(page: Page) {
		super(page);

		this.emailInput = page.locator('input[type="email"], input#email, input[name="email"]').first();
		this.nameInput = page.locator('input[type="text"], input#name, input[name="name"]').first();
		this.passwordInput = page.locator('input[type="password"], input#password, input[name="password"]').first();
		this.signupButton = page.getByRole('button', { name: /sign up|register|create account/i });
		this.loginLink = page.getByRole('link', { name: /login/i });
		this.errorMessage = page.locator('.text-red-400, [role="alert"]');
		this.heading = page.getByRole('heading', { name: /create account|sign up/i });
	}

	/**
	 * Navigate to signup page
	 */
	async goto(): Promise<void> {
		await this.page.goto('/signup');
		await this.waitForLoad();
		await this.waitForVisible(this.heading);
	}

	/**
	 * Fill signup form
	 */
	async fillForm(email: string, password: string, name?: string): Promise<void> {
		await this.fillWithRetry(this.emailInput, email);
		if (name && (await this.isVisible(this.nameInput))) {
			await this.fillWithRetry(this.nameInput, name);
		}
		await this.fillWithRetry(this.passwordInput, password);
	}

	/**
	 * Click signup button
	 */
	async clickSignup(): Promise<void> {
		await this.clickWithRetry(this.signupButton);
	}

	/**
	 * Complete signup flow
	 */
	async signup(email: string, password: string, name?: string): Promise<void> {
		await this.goto();
		await this.fillForm(email, password, name);
		await this.clickSignup();
	}

	/**
	 * Get error message
	 */
	async getErrorMessage(): Promise<string> {
		if (await this.isVisible(this.errorMessage)) {
			return await this.getText(this.errorMessage);
		}
		return '';
	}
}
