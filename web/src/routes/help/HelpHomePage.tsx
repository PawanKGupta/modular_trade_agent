import {
	HelpBullets,
	HelpCallout,
	HelpEmphasis,
	HelpInternalLink,
	HelpMuted,
	HelpPage,
	HelpParagraph,
	HelpSection,
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
