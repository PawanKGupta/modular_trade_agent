import { Page, Locator } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Dashboard Page Object Model
 */
export class DashboardPage extends BasePage {
	// Selectors
	private readonly overviewHeading: Locator;
	private readonly navigationMenu: Locator;
	private readonly mainContent: Locator;

	constructor(page: Page) {
		super(page);

		this.overviewHeading = page.getByText(/Dashboard|Overview/i);
		this.navigationMenu = page.locator('nav, aside');
		this.mainContent = page.locator('main, [role="main"]');
	}

	/**
	 * Navigate to dashboard
	 */
	async goto(): Promise<void> {
		await this.page.goto('/dashboard');
		await this.waitForLoad();
		await this.waitForVisible(this.mainContent);
	}

	/**
	 * Check if dashboard is loaded
	 */
	async isLoaded(): Promise<boolean> {
		return await this.isVisible(this.overviewHeading);
	}

	/**
	 * Navigate to a menu item
	 */
	async navigateToMenuItem(itemName: string | RegExp): Promise<void> {
		const menuItem = this.page.getByRole('link', { name: itemName });
		await this.clickWithRetry(menuItem);
		await this.waitForLoad();
	}

	/**
	 * Expand menu category
	 */
	async expandCategory(categoryName: string | RegExp): Promise<void> {
		const category = this.page.getByText(categoryName).first();
		if (await this.isVisible(category)) {
			await category.click();
		}
	}

	/**
	 * Check if menu item is active
	 */
	async isMenuItemActive(itemName: string | RegExp): Promise<boolean> {
		const menuItem = this.page.getByRole('link', { name: itemName });
		const classes = await menuItem.getAttribute('class');
		return classes?.includes('active') || classes?.includes('bg-') || false;
	}
}
