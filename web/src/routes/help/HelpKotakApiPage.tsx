import {
	HelpBullets,
	HelpCallout,
	HelpInternalLink,
	HelpMuted,
	HelpPage,
	HelpSection,
} from './HelpProse';

export function HelpKotakApiPage() {
	return (
		<HelpPage title="Kotak Neo API setup">
			<HelpMuted>
				Rebound needs API credentials from Kotak Neo. You create these in Kotak&apos;s developer or API portal.
				Exact menu names can change — follow Kotak&apos;s latest official instructions.
			</HelpMuted>

			<HelpSection title="Before you begin">
				<HelpBullets
					items={[
						<>Active Kotak Neo trading account</>,
						<>Kotak mobile app login working (MPIN + TOTP)</>,
						<>API trading enabled per Kotak&apos;s policy for your account type</>,
					]}
				/>
			</HelpSection>

			<HelpSection title="Typical setup flow">
				<HelpBullets
					items={[
						<>
							Log in to the <strong className="text-[var(--text)]">Kotak Neo developer / API portal</strong>{' '}
							(link from the Kotak Neo app or Kotak Securities website — use official Kotak sources only).
						</>,
						<>
							Register or create an API application. Note your <strong className="text-[var(--text)]">App
							Token</strong> (API key) and your <strong className="text-[var(--text)]">Client ID (UCC)</strong>.
						</>,
						<>
							Enable permissions Kotak requires for <strong className="text-[var(--text)]">order placement</strong>{' '}
							and <strong className="text-[var(--text)]">portfolio / order read</strong> (names depend on
							Kotak&apos;s portal).
						</>,
						<>
							Keep <strong className="text-[var(--text)]">MPIN</strong> and{' '}
							<strong className="text-[var(--text)]">TOTP secret</strong> ready. Rebound uses REST login with your
							mobile number, MPIN, and TOTP secret — not a one-time 6-digit code.
						</>,
						<>
							For real money, use the <strong className="text-[var(--text)]">production</strong> environment
							(Rebound field: <code className="text-xs bg-[#0f172a] px-1 rounded">prod</code>) unless your
							operator told you otherwise.
						</>,
					]}
				/>
			</HelpSection>

			<HelpSection title="Security tips">
				<HelpBullets
					items={[
						<>Do not share App Token, Client ID, MPIN, or TOTP secret in chat or email.</>,
						<>Revoke or regenerate keys in Kotak if you suspect leakage.</>,
						<>Enter credentials only on the official Rebound Account Settings page inside this app.</>,
					]}
				/>
			</HelpSection>

			<HelpCallout>
				Next: <HelpInternalLink slug="connect-kotak">Connect Rebound to Kotak</HelpInternalLink> — enter the
				values in Account Settings and run a full connection test before going live.
			</HelpCallout>
		</HelpPage>
	);
}
