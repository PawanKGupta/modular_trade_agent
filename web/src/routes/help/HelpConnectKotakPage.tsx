import {
	HelpAppLink,
	HelpBullets,
	HelpCallout,
	HelpCode,
	HelpEmphasis,
	HelpInternalLink,
	HelpList,
	HelpMuted,
	HelpPage,
	HelpParagraph,
	HelpSection,
	HelpTable,
} from './HelpProse';
import { HELP_SLUG } from './helpNav';

export function HelpConnectKotakPage() {
	return (
		<HelpPage title="Connect your broker">
			<HelpMuted>
				Complete <HelpInternalLink slug={HELP_SLUG.brokerApi}>Broker API setup</HelpInternalLink> with your broker
				first, then enter credentials in the app.
			</HelpMuted>

			<HelpCallout>
				Account Settings shows the broker name your operator supports (e.g. <HelpEmphasis>Kotak Neo</HelpEmphasis>{' '}
				today). Field labels may differ when additional brokers are added.
			</HelpCallout>

			<HelpSection title="1. Open Account Settings">
				<HelpParagraph>
					Sidebar → <HelpAppLink to="/dashboard/settings">Account Settings</HelpAppLink> (
					<HelpCode>/dashboard/settings</HelpCode>).
				</HelpParagraph>
			</HelpSection>

			<HelpSection title="2. Select live broker mode">
				<HelpBullets
					items={[
						<>
							Under <HelpEmphasis>Trading mode</HelpEmphasis>, select your live broker (not Paper Trade). The
							label matches what your deployment supports — e.g. <HelpEmphasis>Kotak Neo</HelpEmphasis>.
						</>,
						<>
							<HelpEmphasis>Broker</HelpEmphasis> should match your operator (e.g. <HelpCode>kotak-neo</HelpCode>{' '}
							for Kotak Neo).
						</>,
						<>Click Save if you changed trade mode.</>,
					]}
				/>
			</HelpSection>

			<HelpSection title="3. Enter credentials (Kotak Neo)">
				<HelpParagraph>
					For Kotak Neo, map your API portal values to these Account Settings fields:
				</HelpParagraph>
				<HelpTable
					headers={['Rebound field (Account Settings)', 'What to enter']}
					rows={[
						[
							'App Token (API Key)',
							'App Token / API key from Kotak developer portal',
						],
						['Client ID (UCC)', 'Your Kotak client ID (UCC)'],
						['Mobile Number', 'Mobile registered with Kotak Neo'],
						['MPIN (for 2FA)', 'Your Kotak trading MPIN'],
						['TOTP Secret', 'TOTP secret for API login (from Kotak setup — not a single 6-digit code)'],
						['Environment', 'prod for live trading (unless told otherwise)'],
					]}
				/>
				<HelpParagraph>
					Click <HelpEmphasis>Save Credentials</HelpEmphasis>. You should see credentials stored confirmation.
				</HelpParagraph>
			</HelpSection>

			<HelpSection title="4. Test the connection">
				<HelpBullets
					items={[
						<>
							<HelpEmphasis>Basic Test</HelpEmphasis> — checks App Token and Client ID only.
						</>,
						<>
							<HelpEmphasis>Full Test</HelpEmphasis> — REST login and MPIN validation. Use this before going
							live.
						</>,
					]}
				/>
				<HelpParagraph>
					Choose Full Test, then click <HelpEmphasis>Test Full Connection</HelpEmphasis>. On success, broker
					status should show Connected.
				</HelpParagraph>
			</HelpSection>

			<HelpSection title="5. Start automation">
				<HelpList
					items={[
						<>
							<HelpAppLink to="/dashboard/trading-config">Trading Config</HelpAppLink> — set limits → Save.
						</>,
						<>
							<HelpAppLink to="/dashboard/service">Service Status</HelpAppLink> — start the trading service.
						</>,
						<>
							<HelpAppLink to="/dashboard/orders">Orders</HelpAppLink> — confirm activity when the system
							trades.
						</>,
						<>
							<HelpAppLink to="/dashboard/billing">Billing</HelpAppLink> — understand performance fees on live
							mode.
						</>,
					]}
				/>
			</HelpSection>

			<HelpSection title="Troubleshooting">
				<HelpTable
					headers={['Issue', 'What to try']}
					rows={[
						[
							'Missing field error on save',
							'Fill all required broker fields before saving (for Kotak Neo: App Token, Client ID, Mobile, MPIN, TOTP Secret).',
						],
						[
							'Full test fails',
							'Verify API is enabled at your broker; for Kotak Neo, re-check mobile, MPIN, and TOTP secret.',
						],
						[
							'Connected but no orders',
							'Confirm Service Status is running, Trading Config has capital, and signals are available.',
						],
						[
							'Saved creds but test fails',
							'Click Show Full Credentials, re-enter values, Save, then run Full Test again.',
						],
					]}
				/>
			</HelpSection>
		</HelpPage>
	);
}
