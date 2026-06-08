import { HelpAppLink, HelpBullets, HelpEmphasis, HelpMuted, HelpPage, HelpParagraph, HelpSection } from './HelpProse';

export function HelpBillingPage() {
	return (
		<HelpPage title="Performance fees">
			<HelpMuted>
				If you use <HelpEmphasis>live broker</HelpEmphasis> mode, Rebound may bill a performance fee each calendar
				month.
			</HelpMuted>

			<HelpSection title="In simple terms">
				<HelpBullets
					items={[
						<>The fee applies to net realized profit on closed live trades in that month.</>,
						<>Losing months usually mean no fee; losses may carry forward before fees apply again.</>,
						<>The percentage is set by your operator — check amounts on your Billing page (often around 10% of chargeable profit).</>,
						<>Pay using UPI/QR or Razorpay as shown under Billing when your operator enables those methods.</>,
					]}
				/>
			</HelpSection>

			<HelpSection title="If an invoice is overdue">
				<HelpParagraph>
					Unpaid performance bills past the due date may <HelpEmphasis>pause new buy orders</HelpEmphasis>. Sell
					monitoring continues so you can exit open positions. Pay from{' '}
					<HelpAppLink to="/dashboard/billing">Billing</HelpAppLink> to restore new entries.
				</HelpParagraph>
			</HelpSection>

			<HelpSection title="View your invoices">
				<HelpParagraph>
					Open <HelpAppLink to="/dashboard/billing">Billing</HelpAppLink> for open bills, payment history, and
					payment instructions (offline UPI or online checkout when enabled).
				</HelpParagraph>
			</HelpSection>
		</HelpPage>
	);
}
