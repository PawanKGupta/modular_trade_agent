import type { ReactNode } from 'react';
import {
	HelpAppLink,
	HelpEmphasis,
	HelpFaqList,
	HelpInternalLink,
	HelpMuted,
	HelpPage,
} from './HelpProse';
import { HELP_SLUG } from './helpNav';

const FAQ_ITEMS: { q: string; a: ReactNode }[] = [
	{
		q: 'Do I need a broker for everything?',
		a: (
			<>
				No. Paper mode works without a broker.{' '}
				<HelpEmphasis>Live automation requires a supported broker with API access.</HelpEmphasis>
			</>
		),
	},
	{
		q: 'Is my broker website password stored?',
		a: 'Rebound stores encrypted broker API credentials (for Kotak Neo today: App Token, Client ID, mobile, MPIN, TOTP secret). Your separate Rebound login password is stored securely for app access.',
	},
	{
		q: 'Can I stop automation anytime?',
		a: (
			<>
				Yes. Stop the service under <HelpAppLink to="/dashboard/service">Service Status</HelpAppLink>. You can
				switch to Paper mode in Account Settings.
			</>
		),
	},
	{
		q: 'Where do trading signals come from?',
		a: (
			<>
				Signals appear in <HelpAppLink to="/dashboard/buying-zone">Buying Zone</HelpAppLink>. Who runs market
				analysis depends on your deployment — contact your operator if you are unsure.
			</>
		),
	},
	{
		q: 'Will I always make money?',
		a: 'No. Trading involves risk of loss. Rebound does not guarantee profits.',
	},
	{
		q: 'How do performance fees work?',
		a: (
			<>
				See <HelpInternalLink slug={HELP_SLUG.billing}>Performance fees</HelpInternalLink> for a summary, or open{' '}
				<HelpAppLink to="/dashboard/billing">Billing</HelpAppLink> for your invoices.
			</>
		),
	},
	{
		q: 'Which brokers are supported for live trading?',
		a: (
			<>
				That depends on your operator. <HelpEmphasis>Kotak Neo</HelpEmphasis> is supported today; additional
				brokers are planned. Check Account Settings or ask your operator which live broker appears in your app.
			</>
		),
	},
	{
		q: 'How do I get help with setup?',
		a: (
			<>
				Follow <HelpInternalLink slug={HELP_SLUG.getStarted}>Get started</HelpInternalLink>,{' '}
				<HelpInternalLink slug={HELP_SLUG.brokerApi}>Broker API setup</HelpInternalLink>, and{' '}
				<HelpInternalLink slug={HELP_SLUG.connectBroker}>Connect your broker</HelpInternalLink> in this help
				center. Contact your operator for account-specific support.
			</>
		),
	},
];

export function HelpFaqPage() {
	return (
		<HelpPage title="FAQ">
			<HelpMuted>Quick answers about using Rebound.</HelpMuted>
			<HelpFaqList items={FAQ_ITEMS} />
		</HelpPage>
	);
}
