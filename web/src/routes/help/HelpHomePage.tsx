import {
	HelpBullets,
	HelpCallout,
	HelpEmphasis,
	HelpInternalLink,
	HelpMuted,
	HelpPage,
	HelpParagraph,
	HelpSection,
	HelpAppLink,
} from './HelpProse';
import { HELP_SLUG } from './helpNav';

export function HelpHomePage() {
	return (
		<HelpPage title="Welcome to Rebound">
			<HelpMuted>
				Rebound is a web platform that connects to your <HelpEmphasis>broker</HelpEmphasis> trading account and
				can automate order placement and monitoring using rules you configure in the app.
			</HelpMuted>

			<HelpSection title="How it works">
				<HelpBullets
					items={[
						<>Your money stays in your broker account — Rebound does not hold your funds.</>,
						<>You sign in to Rebound in your browser and choose Paper (practice) or live broker mode.</>,
						<>Broker API details are stored encrypted and used only when you start the trading service.</>,
					]}
				/>
			</HelpSection>

			<HelpSection title="What you need">
				<HelpBullets
					items={[
						<>A Rebound account with a verified email address</>,
						<>
							For <HelpEmphasis>live trading</HelpEmphasis>: a supported broker account with API access, plus the
							credentials your broker requires for automated login (often mobile, MPIN, and TOTP)
						</>,
					]}
				/>
				<HelpCallout>
					Supported brokers and live automation depend on your operator. See{' '}
					<HelpInternalLink slug={HELP_SLUG.connectBroker}>Connect your broker</HelpInternalLink> for setup
					steps that apply to your deployment.
				</HelpCallout>
			</HelpSection>

			<HelpSection title="Performance fees (live trading)">
				<HelpParagraph>
					On live broker mode, Rebound may invoice a <HelpEmphasis>performance fee</HelpEmphasis> each month — a
					percentage of net realized profit after losses are recovered. See{' '}
					<HelpInternalLink slug="billing">Performance fees</HelpInternalLink> for details.
				</HelpParagraph>
			</HelpSection>

			<HelpSection title="AI-powered analysis">
				<HelpParagraph>
					Every stock that passes the rule-based scanner is also evaluated by a trained{' '}
					<HelpEmphasis>machine-learning classifier</HelpEmphasis>. Signals only reach your{' '}
					<HelpAppLink to="/dashboard/buying-zone">Buying Zone</HelpAppLink> when{' '}
					both the rules <HelpEmphasis>and</HelpEmphasis> the model agree — reducing noise and
					surfacing higher-confidence ideas. Each signal shows an ML confidence percentage so you
					can prioritise accordingly. Learn more in{' '}
					<HelpInternalLink slug={HELP_SLUG.mlSignals}>ML-powered signals</HelpInternalLink>.
				</HelpParagraph>
			</HelpSection>

			<HelpSection title="Start here">
				<HelpParagraph>
					New user? Follow the <HelpInternalLink slug="get-started">Get started</HelpInternalLink> guide. Going
					live? Read <HelpInternalLink slug={HELP_SLUG.brokerApi}>Broker API setup</HelpInternalLink> then{' '}
					<HelpInternalLink slug={HELP_SLUG.connectBroker}>Connect your broker</HelpInternalLink>.
				</HelpParagraph>
			</HelpSection>

			<HelpCallout>
				Trading involves risk of loss. Rebound does not guarantee profits. This guide is for product setup only —
				not investment advice.
			</HelpCallout>
		</HelpPage>
	);
}
