import type { ReactNode } from 'react';
import {
	HelpAppLink,
	HelpCode,
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
		q: 'How are my broker credentials protected on the server?',
		a: (
			<>
				All broker credentials (App Token, Client ID, mobile number, MPIN, and TOTP secret key) are encrypted at rest in the database using <HelpEmphasis>AES-128/Fernet symmetric encryption</HelpEmphasis>. The decryption key (<HelpCode>APP_DATA_ENCRYPTION_KEY</HelpCode>) resides exclusively in the server environment, and credentials are decrypted strictly in-memory during authentication.
			</>
		),
	},
	{
		q: 'Could my API tokens or secrets leak into log files?',
		a: (
			<>
				No. Rebound uses automated log sanitization filters. All logging outputs are parsed by security middleware that automatically masks sensitive keys (such as passwords, tokens, JWTs, and MPINs) using regular expression patterns before they are written to disk.
			</>
		),
	},
	{
		q: 'How does Rebound handle session and brute-force security?',
		a: (
			<>
				In production mode, Rebound uses secure <HelpEmphasis>httpOnly and Secure session cookies</HelpEmphasis> to protect session tokens against XSS. Additionally, a built-in rate-limiting firewall blocks brute-force login attempts by implementing a temporary lockout window on client IPs after repeated authentication failures.
			</>
		),
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
		q: 'What does the ML confidence percentage mean?',
		a: (
			<>
				Each signal in Buying Zone shows an <HelpEmphasis>ML Confidence</HelpEmphasis> percentage — the
				probability the trained classifier assigns to the stock being a good buy at this point. A higher
				percentage means the model is more certain. Signals only appear when confidence clears the
				configured threshold (default 60 %). You can tune this under{' '}
				<HelpAppLink to="/dashboard/trading-config">Trading Config → ML Configuration</HelpAppLink>.
			</>
		),
	},
	{
		q: 'Does the ML model replace the rule-based analysis?',
		a: (
			<>
				No — it works <HelpEmphasis>alongside</HelpEmphasis> it. By default both must agree (Combine ML with
				Rule-Based Logic is on). If you disable that option the ML verdict alone decides, but most users
				leave it on for an extra layer of filtering.
			</>
		),
	},
	{
		q: 'What happens if a signal\'s verdict changes after I see it?',
		a: (
			<>
				If re-analysis produces a <HelpEmphasis>watch</HelpEmphasis> or{' '}
				<HelpEmphasis>avoid</HelpEmphasis> verdict for a stock already in your Buying Zone, the signal is
				automatically expired and removed. Your buying zone always reflects the current view of both the
				rules and the model — you never need to manually clean up stale signals.
			</>
		),
	},
	{
		q: 'Can I turn off ML predictions?',
		a: (
			<>
				Yes. In <HelpAppLink to="/dashboard/trading-config">Trading Config</HelpAppLink> under{' '}
				<HelpEmphasis>ML Configuration</HelpEmphasis>, uncheck <HelpEmphasis>Enable ML Predictions</HelpEmphasis>.
				The system falls back to rule-based signals only — nothing else changes.
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
