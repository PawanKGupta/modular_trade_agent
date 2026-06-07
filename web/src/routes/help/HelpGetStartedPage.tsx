import {
	HelpAppLink,
	HelpBullets,
	HelpInternalLink,
	HelpList,
	HelpMuted,
	HelpPage,
	HelpSection,
} from './HelpProse';

export function HelpGetStartedPage() {
	return (
		<HelpPage title="Get started">
			<HelpMuted>Follow these steps to create your account and choose paper or live trading.</HelpMuted>

			<HelpSection title="Step 1 — Create your account">
				<HelpList
					items={[
						<>Open this Rebound site and click <HelpAppLink to="/signup">Sign up</HelpAppLink>.</>,
						<>Enter your name, email, and password (contact mobile is optional).</>,
						<>Open the verification email and click the link — required before you can log in.</>,
						<>
							Log in at <HelpAppLink to="/login">Login</HelpAppLink>. Use{' '}
							<HelpAppLink to="/resend-verification">Resend verification</HelpAppLink> if the email did not
							arrive (check spam).
						</>,
					]}
				/>
			</HelpSection>

			<HelpSection title="Step 2 — Choose paper or live">
				<HelpList
					items={[
						<>
							Go to <HelpAppLink to="/dashboard/settings">Account Settings</HelpAppLink>.
						</>,
						<>
							Under <strong className="text-[var(--text)]">Trading mode</strong>, choose:
							<ul className="list-disc list-inside mt-2 space-y-1 text-[var(--muted)]">
								<li>
									<strong className="text-[var(--text)]">Paper Trade</strong> — simulated money, no Kotak
									needed
								</li>
								<li>
									<strong className="text-[var(--text)]">Kotak Neo</strong> — real orders on your broker
									account
								</li>
							</ul>
						</>,
						<>Click Save if you changed trade mode.</>,
					]}
				/>
			</HelpSection>

			<HelpSection title="Step 3 — Paper trading (optional)">
				<HelpList
					items={[
						<>
							Sidebar → <HelpAppLink to="/dashboard/paper-trading">Paper Trading</HelpAppLink> — review virtual
							portfolio and capital.
						</>,
						<>
							Sidebar → <HelpAppLink to="/dashboard/service">Service Status</HelpAppLink> — start the service when
							you are ready to simulate automation.
						</>,
					]}
				/>
				<p className="text-[var(--muted)]">No Kotak setup is required for paper mode.</p>
			</HelpSection>

			<HelpSection title="Step 4 — Live trading with Kotak">
				<HelpList
					items={[
						<>
							Complete <HelpInternalLink slug="kotak-api">Kotak Neo API setup</HelpInternalLink> on the Kotak
							side.
						</>,
						<>
							Complete <HelpInternalLink slug="connect-kotak">Connect Rebound to Kotak</HelpInternalLink> in
							Account Settings.
						</>,
						<>
							<HelpAppLink to="/dashboard/trading-config">Trading Config</HelpAppLink> — set capital and risk
							limits → Save.
						</>,
						<>
							<HelpAppLink to="/dashboard/service">Service Status</HelpAppLink> — start the unified trading
							service (or the tasks your operator recommends).
						</>,
						<>
							Watch <HelpAppLink to="/dashboard/orders">Orders</HelpAppLink> and{' '}
							<HelpAppLink to="/dashboard/buying-zone">Buying Zone</HelpAppLink> for activity.
						</>,
					]}
				/>
			</HelpSection>

			<HelpSection title="Step 5 — Notifications (recommended)">
				<p>
					Open <HelpAppLink to="/dashboard/notification-preferences">Notification Settings</HelpAppLink> and
					enable in-app and/or Telegram alerts for order placed, filled, rejected, and similar events.
				</p>
			</HelpSection>

			<HelpSection title="Step 6 — Billing (live users)">
				<p>
					Read <HelpInternalLink slug="billing">Performance fees</HelpInternalLink> and keep{' '}
					<HelpAppLink to="/dashboard/billing">Billing</HelpAppLink> invoices paid on time.
				</p>
			</HelpSection>
		</HelpPage>
	);
}
