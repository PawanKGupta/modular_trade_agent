import {
	HelpBullets,
	HelpCallout,
	HelpCode,
	HelpEmphasis,
	HelpInternalLink,
	HelpMuted,
	HelpPage,
	HelpSection,
} from './HelpProse';
import { HELP_SLUG } from './helpNav';

export function HelpKotakApiPage() {
	return (
		<HelpPage title="Broker API setup">
			<HelpMuted>
				Live trading requires API credentials from your broker. You usually create these in your broker&apos;s
				developer or API portal. Exact menu names vary — follow your broker&apos;s latest official instructions.
			</HelpMuted>

			<HelpCallout>
				<HelpEmphasis>Kotak Neo</HelpEmphasis> is supported for live automation today. The steps below describe
				Kotak Neo; guides for additional brokers will be added as they become available.
			</HelpCallout>

			<HelpSection title="Before you begin">
				<HelpBullets
					items={[
						<>Active trading account with your supported broker</>,
						<>Broker mobile or web login working (including any 2FA your broker requires)</>,
						<>API trading enabled per your broker&apos;s policy for your account type</>,
					]}
				/>
			</HelpSection>

			<HelpSection title="Kotak Neo — enable API access">
				<HelpBullets
					items={[
						<>
							Log in to the <HelpEmphasis>Kotak Neo developer / API portal</HelpEmphasis> (link from the Kotak
							Neo app or Kotak Securities website — use official Kotak sources only).
						</>,
						<>
							Register or create an API application. Note your <HelpEmphasis>App Token</HelpEmphasis> (API key)
							and your <HelpEmphasis>Client ID (UCC)</HelpEmphasis>.
						</>,
						<>
							Enable permissions Kotak requires for <HelpEmphasis>order placement</HelpEmphasis> and{' '}
							<HelpEmphasis>portfolio / order read</HelpEmphasis> (names depend on Kotak&apos;s portal).
						</>,
						<>
							Keep <HelpEmphasis>MPIN</HelpEmphasis> and <HelpEmphasis>TOTP secret</HelpEmphasis> ready.
							Rebound uses REST login with your mobile number, MPIN, and TOTP secret — not a one-time 6-digit
							code.
						</>,
						<>
							For real money, use the <HelpEmphasis>production</HelpEmphasis> environment (Rebound field:{' '}
							<HelpCode>prod</HelpCode>) unless your operator told you otherwise.
						</>,
					]}
				/>
			</HelpSection>

			<HelpSection title="Security tips">
				<HelpBullets
					items={[
						<>Do not share API keys, client IDs, MPIN, or TOTP secrets in chat or email.</>,
						<>Revoke or regenerate keys with your broker if you suspect leakage.</>,
						<>Enter credentials only on the official Rebound Account Settings page inside this app.</>,
					]}
				/>
			</HelpSection>

			<HelpCallout>
				Next: <HelpInternalLink slug={HELP_SLUG.connectBroker}>Connect your broker</HelpInternalLink> — enter the
				values in Account Settings and run a full connection test before going live.
			</HelpCallout>
		</HelpPage>
	);
}
