import {
	HelpAppLink,
	HelpBullets,
	HelpCallout,
	HelpInternalLink,
	HelpMuted,
	HelpPage,
	HelpSection,
} from './HelpProse';

export function HelpHomePage() {
	return (
		<HelpPage title="Welcome to Rebound">
			<HelpMuted>
				Rebound is a web platform that connects to your <strong className="text-[var(--text)]">Kotak Neo</strong>{' '}
				trading account and can automate order placement and monitoring using rules you configure in the app.
			</HelpMuted>

			<HelpSection title="How it works">
				<HelpBullets
					items={[
						<>Your money stays in your Kotak account — Rebound does not hold your funds.</>,
						<>You sign in to Rebound in your browser and choose Paper (practice) or Kotak Neo (live).</>,
						<>Broker API details are stored encrypted and used only when you start the trading service.</>,
					]}
				/>
			</HelpSection>

			<HelpSection title="What you need">
				<HelpBullets
					items={[
						<>A Rebound account with a verified email address</>,
						<>
							For <strong className="text-[var(--text)]">live trading</strong>: an active Kotak Neo account with
							API access, plus mobile number, MPIN, and TOTP secret (same family of credentials you use for
							Kotak login)
						</>,
					]}
				/>
				<HelpCallout>
					Live automated trading is <strong className="text-[var(--text)]">Kotak Neo only</strong> today. Other
					brokers are not supported for live orders yet.
				</HelpCallout>
			</HelpSection>

			<HelpSection title="Performance fees (live trading)">
				<p>
					On live Kotak mode, Rebound may invoice a <strong className="text-[var(--text)]">performance fee</strong>{' '}
					each month — a percentage of net realized profit after losses are recovered. See{' '}
					<HelpInternalLink slug="billing">Performance fees</HelpInternalLink> for details.
				</p>
			</HelpSection>

			<HelpSection title="Start here">
				<p>
					New user? Follow the <HelpInternalLink slug="get-started">Get started</HelpInternalLink> guide. Going
					live? Read <HelpInternalLink slug="kotak-api">Kotak Neo API</HelpInternalLink> then{' '}
					<HelpInternalLink slug="connect-kotak">Connect Rebound</HelpInternalLink>.
				</p>
			</HelpSection>

			<HelpCallout>
				Trading involves risk of loss. Rebound does not guarantee profits. This guide is for product setup only —
				not investment advice.
			</HelpCallout>
		</HelpPage>
	);
}
