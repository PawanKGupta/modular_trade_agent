import { Page, Locator } from '@playwright/test';
import { TestConfig } from '../config/test-config';

/**
 * Base Page Object Model
 * Provides common functionality for all page objects
 */
export abstract class BasePage {
	readonly page: Page;
	readonly config = TestConfig;

	constructor(page: Page) {
		this.page = page;
	}

	/**
	 * Navigate to the page
	 */
	abstract goto(): Promise<void>;

	/**
	 * Wait for page to be loaded
	 */
	async waitForLoad(): Promise<void> {
		await this.page.waitForLoadState('domcontentloaded');
	}

	/**
	 * Wait for network to be idle
	 */
	async waitForNetworkIdle(): Promise<void> {
		await this.page.waitForLoadState('networkidle');
	}

	/**
	 * Wait for element to be visible
	 */
	async waitForVisible(locator: Locator, timeout?: number): Promise<void> {
		await locator.waitFor({ state: 'visible', timeout: timeout || this.config.timeouts.element });
	}

	/**
	 * Wait for element to be hidden
	 */
	async waitForHidden(locator: Locator, timeout?: number): Promise<void> {
		await locator.waitFor({ state: 'hidden', timeout: timeout || this.config.timeouts.element });
	}

	/**
	 * Click element with retry
	 */
	async clickWithRetry(locator: Locator, timeout?: number): Promise<void> {
		await this.waitForVisible(locator, timeout);
		await locator.click({ timeout: timeout || this.config.timeouts.action });
	}

	/**
	 * Fill input with retry
	 */
	async fillWithRetry(locator: Locator, value: string, timeout?: number): Promise<void> {
		await this.waitForVisible(locator, timeout);
		await locator.fill(value, { timeout: timeout || this.config.timeouts.action });
	}

	/**
	 * Get text content safely
	 */
	async getText(locator: Locator): Promise<string> {
		await this.waitForVisible(locator);
		return (await locator.textContent()) || '';
	}

	/**
	 * Check if element is visible
	 */
	async isVisible(locator: Locator): Promise<boolean> {
		try {
			return await locator.isVisible({ timeout: 2000 });
		} catch {
			return false;
		}
	}

	/**
	 * Take screenshot
	 */
	async screenshot(name: string): Promise<void> {
		await this.page.screenshot({ path: `test-results/screenshots/${name}.png` });
	}
}
