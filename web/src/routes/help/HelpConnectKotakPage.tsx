import {
	HelpAppLink,
	HelpBullets,
	HelpInternalLink,
	HelpList,
	HelpMuted,
	HelpPage,
	HelpSection,
	HelpTable,
} from './HelpProse';

export function HelpConnectKotakPage() {
	return (
		<HelpPage title="Connect Rebound to Kotak Neo">
			<HelpMuted>
				Complete <HelpInternalLink slug="kotak-api">Kotak Neo API setup</HelpInternalLink> first, then enter
				credentials in the app.
			</HelpMuted>

			<HelpSection title="1. Open Account Settings">
				<p>
					Sidebar → <HelpAppLink to="/dashboard/settings">Account Settings</HelpAppLink> (
					<code className="text-xs bg-[#0f172a] px-1 rounded">/dashboard/settings</code>).
				</p>
			</HelpSection>

			<HelpSection title="2. Select live mode">
				<HelpBullets
					items={[
						<>
							Under <strong className="text-[var(--text)]">Trading mode</strong>, select{' '}
							<strong className="text-[var(--text)]">Kotak Neo</strong> (not Paper Trade).
						</>,
						<>
							<strong className="text-[var(--text)]">Broker</strong> should be{' '}
							<code className="text-xs bg-[#0f172a] px-1 rounded">kotak-neo</code>.
						</>,
						<>Click Save if you changed trade mode.</>,
					]}
				/>
			</HelpSection>

			<HelpSection title="3. Enter credentials">
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
				<p className="pt-2">
					Click <strong className="text-[var(--text)]">Save Credentials</strong>. You should see credentials
					stored confirmation.
				</p>
			</HelpSection>

			<HelpSection title="4. Test the connection">
				<HelpBullets
					items={[
						<>
							<strong className="text-[var(--text)]">Basic Test</strong> — checks App Token and Client ID only.
						</>,
						<>
							<strong className="text-[var(--text)]">Full Test</strong> — REST login and MPIN validation. Use
							this before going live.
						</>,
					]}
				/>
				<p>Click Test Connection. On success, broker status should show Connected.</p>
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
							'Fill App Token, Client ID, Mobile, MPIN, and TOTP Secret before saving.',
						],
						['Full test fails', 'Verify API is enabled at Kotak; re-check mobile, MPIN, and TOTP secret.'],
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
