/** End-user help navigation (public `/help` routes). */

export interface HelpNavItem {
	slug: string;
	title: string;
	description: string;
}

export const HELP_NAV_ITEMS: HelpNavItem[] = [
	{
		slug: '',
		title: 'Welcome',
		description: 'What Rebound is and what you need to get started',
	},
	{
		slug: 'get-started',
		title: 'Get started',
		description: 'Account, paper vs live, and first steps',
	},
	{
		slug: 'kotak-api',
		title: 'Kotak Neo API',
		description: 'Enable API access on the Kotak side',
	},
	{
		slug: 'connect-kotak',
		title: 'Connect Rebound',
		description: 'Enter credentials in Account Settings',
	},
	{
		slug: 'billing',
		title: 'Performance fees',
		description: 'How live-trading billing works',
	},
	{
		slug: 'faq',
		title: 'FAQ',
		description: 'Common questions',
	},
];

export function helpPath(slug: string): string {
	return slug ? `/help/${slug}` : '/help';
}
