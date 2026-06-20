/**
 * End-user help navigation (public `/help` routes).
 *
 * Help content must stay self-contained in the app: link only to other `/help/*`
 * pages or in-app routes (`/login`, `/dashboard/...`). Do not link to repo docs,
 * GitHub, or other developer-only URLs — those may be private or inaccessible.
 *
 * Route slugs are broker-neutral so additional brokers can be documented without
 * renaming URLs. Broker-specific steps live on the page body (e.g. Kotak Neo today).
 */

export interface HelpNavItem {
	slug: string;
	title: string;
	description: string;
}

/** Canonical help route slugs (broker-neutral). */
export const HELP_SLUG = {
	welcome: '',
	getStarted: 'get-started',
	brokerApi: 'broker-api',
	connectBroker: 'connect-broker',
	billing: 'billing',
	mlSignals: 'ml-signals',
	faq: 'faq',
} as const;

/** Legacy slugs kept for redirects from earlier help builds. */
export const HELP_LEGACY_SLUG = {
	kotakApi: 'kotak-api',
	connectKotak: 'connect-kotak',
} as const;

export const HELP_NAV_ITEMS: HelpNavItem[] = [
	{
		slug: HELP_SLUG.welcome,
		title: 'Welcome',
		description: 'What Rebound is and what you need to get started',
	},
	{
		slug: HELP_SLUG.getStarted,
		title: 'Get started',
		description: 'Account, paper vs live, and first steps',
	},
	{
		slug: HELP_SLUG.brokerApi,
		title: 'Broker API setup',
		description: 'Enable API access with your broker',
	},
	{
		slug: HELP_SLUG.connectBroker,
		title: 'Connect your broker',
		description: 'Enter credentials in Account Settings',
	},
	{
		slug: HELP_SLUG.billing,
		title: 'Performance fees',
		description: 'How live-trading billing works',
	},
	{
		slug: HELP_SLUG.mlSignals,
		title: 'ML-powered signals',
		description: 'How the AI classifier works and what confidence means',
	},
	{
		slug: HELP_SLUG.faq,
		title: 'FAQ',
		description: 'Common questions',
	},
];

export function helpPath(slug: string): string {
	return slug ? `/help/${slug}` : '/help';
}
