import {
	HelpAppLink,
	HelpEmphasis,
	HelpInternalLink,
	HelpList,
	HelpMuted,
	HelpPage,
	HelpParagraph,
	HelpSection,
	HelpSubBullets,
} from './HelpProse';
import { HELP_SLUG } from './helpNav';

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
							Under <HelpEmphasis>Trading mode</HelpEmphasis>, choose:
							<HelpSubBullets
								items={[
									<>
										<HelpEmphasis>Paper Trade</HelpEmphasis> — simulated money, no broker setup needed
									</>,
									<>
										<HelpEmphasis>Live broker</HelpEmphasis> — real orders on your broker account (label
										in the app matches your supported broker, e.g. Kotak Neo)
									</>,
								]}
							/>
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
				<HelpParagraph>No broker setup is required for paper mode.</HelpParagraph>
			</HelpSection>

			<HelpSection title="Step 4 — Live trading with your broker">
				<HelpList
					items={[
						<>
							Complete <HelpInternalLink slug={HELP_SLUG.brokerApi}>Broker API setup</HelpInternalLink> on the
							broker side.
						</>,
						<>
							Complete <HelpInternalLink slug={HELP_SLUG.connectBroker}>Connect your broker</HelpInternalLink> in
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
				<HelpParagraph>
					Open <HelpAppLink to="/dashboard/notification-preferences">Notification Settings</HelpAppLink> and
					enable in-app and/or Telegram alerts for order placed, filled, rejected, and similar events.
				</HelpParagraph>
			</HelpSection>

			<HelpSection title="Step 6 — ML-powered signals (optional)">
				<HelpParagraph>
					Rebound ships with a pre-trained machine-learning classifier that runs on every analysis
					and filters signals by confidence. It is on by default — no setup needed.
				</HelpParagraph>
				<HelpList
					items={[
						<>
							Open <HelpAppLink to="/dashboard/trading-config">Trading Config</HelpAppLink> →{' '}
							<HelpEmphasis>ML Configuration</HelpEmphasis> to see whether{' '}
							<HelpEmphasis>Enable ML Predictions</HelpEmphasis> is on.
						</>,
						<>
							In <HelpAppLink to="/dashboard/buying-zone">Buying Zone</HelpAppLink>, enable the{' '}
							<HelpEmphasis>ML Verdict</HelpEmphasis> and{' '}
							<HelpEmphasis>ML Confidence</HelpEmphasis> columns via the column selector to see
							the AI score alongside each signal.
						</>,
						<>
							Read <HelpInternalLink slug={HELP_SLUG.mlSignals}>ML-powered signals</HelpInternalLink>{' '}
							to understand what the confidence threshold means and how to tune it.
						</>,
					]}
				/>
			</HelpSection>

			<HelpSection title="Step 7 — Billing (live users)">
				<HelpParagraph>
					Read <HelpInternalLink slug={HELP_SLUG.billing}>Performance fees</HelpInternalLink> and keep{' '}
					<HelpAppLink to="/dashboard/billing">Billing</HelpAppLink> invoices paid on time.
				</HelpParagraph>
			</HelpSection>

		</HelpPage>
	);
}
