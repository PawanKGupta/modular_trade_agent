import { Page, Locator } from '@playwright/test';
import { BasePage } from './BasePage';
import { TestConfig } from '../config/test-config';

/**
 * Login Page Object Model
 */
export class LoginPage extends BasePage {
	// Selectors
	private readonly emailInput: Locator;
	private readonly passwordInput: Locator;
	private readonly loginButton: Locator;
	private readonly signupLink: Locator;
	private readonly errorMessage: Locator;
	private readonly heading: Locator;

	constructor(page: Page) {
		super(page);

		this.emailInput = page.locator('#email');
		this.passwordInput = page.locator('#password');
		this.loginButton = page.getByRole('button', { name: /^login$/i });
		this.signupLink = page.getByRole('link', { name: /sign up/i });
		// API errors use mb-3; field validation and required-field markers use mb-2 or inline asterisks.
		this.errorMessage = page.locator('form div.text-red-400.mb-3');
		this.heading = page.getByRole('heading', { name: /login/i });
	}

	/**
	 * Navigate to login page
	 */
	async goto(): Promise<void> {
		await this.page.goto('/');
		await this.waitForLoad();
		await this.waitForVisible(this.heading);
	}

	/**
	 * Fill email input
	 */
	async fillEmail(email: string): Promise<void> {
		await this.fillWithRetry(this.emailInput, email);
	}

	/**
	 * Fill password input
	 */
	async fillPassword(password: string): Promise<void> {
		await this.fillWithRetry(this.passwordInput, password);
	}

	/**
	 * Click login button
	 */
	async clickLogin(): Promise<void> {
		await this.clickWithRetry(this.loginButton);
	}

	/**
	 * Click signup link
	 */
	async clickSignup(): Promise<void> {
		await this.clickWithRetry(this.signupLink);
	}

	/**
	 * Login with credentials
	 */
	async login(email: string = TestConfig.users.admin.email, password: string = TestConfig.users.admin.password): Promise<void> {
		await this.goto();
		await this.fillEmail(email);
		await this.fillPassword(password);
		await Promise.all([
			this.page.waitForResponse(
				(response) =>
					response.url().includes('/auth/login') &&
					(response.status() === 200 || response.status() === 403),
			),
			this.clickLogin(),
		]);
		// Wait for navigation to dashboard after login
		await this.page.waitForURL(/\/dashboard/, { timeout: this.config.timeouts.navigation });
		await this.page.waitForLoadState('domcontentloaded');
	}

	/**
	 * Login as admin
	 */
	async loginAsAdmin(): Promise<void> {
		await this.login(TestConfig.users.admin.email, TestConfig.users.admin.password);
	}

	/**
	 * Login as regular user
	 */
	async loginAsUser(): Promise<void> {
		await this.login(TestConfig.users.user.email, TestConfig.users.user.password);
	}

	/**
	 * Get error message text
	 */
	async getErrorMessage(): Promise<string> {
		if (await this.isVisible(this.errorMessage)) {
			return await this.getText(this.errorMessage);
		}
		return '';
	}

	/**
	 * Check if error message is visible
	 * Waits for error message to appear with timeout
	 */
	async hasError(timeout: number = 5000): Promise<boolean> {
		try {
			await this.waitForVisible(this.errorMessage, timeout);
			return true;
		} catch {
			return false;
		}
	}

	/**
	 * Wait for login form to be ready
	 */
	async waitForFormReady(): Promise<void> {
		await this.page.waitForSelector('form', { timeout: this.config.timeouts.element });
		await this.waitForVisible(this.heading);
		await this.waitForVisible(this.emailInput);
		await this.waitForVisible(this.passwordInput);
	}
}
