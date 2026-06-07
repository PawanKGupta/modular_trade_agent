import type { ReactNode } from 'react';
import { HelpAppLink, HelpMuted, HelpPage, HelpSection } from './HelpProse';

const FAQ_ITEMS: { q: string; a: ReactNode }[] = [
	{
		q: 'Do I need Kotak for everything?',
		a: (
			<>
				No. Paper mode works without Kotak. <strong className="text-[var(--text)]">Live automation requires Kotak Neo.</strong>
			</>
		),
	},
	{
		q: 'Is my Kotak website password stored?',
		a: 'Rebound stores encrypted Kotak API credentials (App Token, Client ID, mobile, MPIN, TOTP secret). Your separate Rebound login password is stored securely for app access.',
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
		a: 'See the Performance fees help page for a summary, or open Billing in the app for your invoices.',
	},
	{
		q: 'Which brokers are supported for live trading?',
		a: 'Kotak Neo only today. Other brokers are not supported for automated live orders yet.',
	},
	{
		q: 'How do I get help with setup?',
		a: 'Follow Get started, Kotak Neo API, and Connect Rebound in this help center. Contact your operator for account-specific support.',
	},
];

export function HelpFaqPage() {
	return (
		<HelpPage title="FAQ">
			<HelpMuted>Quick answers about using Rebound.</HelpMuted>
			<div className="space-y-6 pt-2">
				{FAQ_ITEMS.map((item) => (
					<HelpSection key={item.q} title={item.q}>
						<p className="text-[var(--muted)]">{item.a}</p>
					</HelpSection>
				))}
			</div>
		</HelpPage>
	);
}
