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
	private readonly confirmPasswordInput: Locator;
	private readonly signupButton: Locator;
	private readonly loginLink: Locator;
	private readonly errorMessage: Locator;
	private readonly heading: Locator;

	constructor(page: Page) {
		super(page);

		this.emailInput = page.locator('#email');
		this.nameInput = page.locator('#name');
		this.passwordInput = page.locator('#password');
		this.confirmPasswordInput = page.locator('#confirmPassword');
		this.signupButton = page.getByRole('button', { name: /^sign up$/i });
		this.loginLink = page.getByRole('link', { name: /login/i });
		this.errorMessage = page.locator('form div.text-red-400.mb-3');
		this.heading = page.getByRole('heading', { name: /create account/i });
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
		if (name) {
			await this.fillWithRetry(this.nameInput, name);
		}
		await this.fillWithRetry(this.passwordInput, password);
		await this.fillWithRetry(this.confirmPasswordInput, password);
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
		await Promise.all([
			this.page.waitForResponse(
				(response) => response.url().includes('/auth/signup') && response.status() < 500,
			),
			this.clickSignup(),
		]);
		await this.page.getByRole('heading', { name: /check your email/i }).waitFor({
			state: 'visible',
			timeout: this.config.timeouts.navigation,
		});
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
