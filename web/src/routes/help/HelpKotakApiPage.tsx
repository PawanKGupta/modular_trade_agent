import {
	HelpBullets,
	HelpCallout,
	HelpCode,
	HelpEmphasis,
	HelpInternalLink,
	HelpMuted,
	HelpPage,
	HelpParagraph,
	HelpSection,
	HelpSubBullets,
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

			<HelpSection title="Kotak Neo — Step-by-Step Credentials Guide">
				<HelpBullets
					items={[
						<>
							<HelpEmphasis>App Token (API Key / Consumer Key)</HelpEmphasis>:
							<HelpSubBullets
								items={[
									<>Log in to the Kotak Neo mobile app or web portal.</>,
									<>Navigate to the <HelpEmphasis>More</HelpEmphasis> tab &rarr; <HelpEmphasis>TradeAPI</HelpEmphasis> &rarr; <HelpEmphasis>API Dashboard</HelpEmphasis>.</>,
									<>Click the <HelpEmphasis>Create Application</HelpEmphasis> button.</>,
									<>Copy the generated token (e.g. <HelpCode>ec6a746c-e44b-455e-abf2-c13352b2fc45</HelpCode>).</>
								]}
							/>
						</>,
						<>
							<HelpEmphasis>Client ID (UCC / Consumer Secret)</HelpEmphasis>:
							<HelpSubBullets
								items={[
									<>Go to your <HelpEmphasis>Profile</HelpEmphasis> section in the Kotak Neo app or portal.</>,
									<>Copy the 5-character alphanumeric <HelpEmphasis>Client Code</HelpEmphasis> (also known as UCC).</>
								]}
							/>
						</>,
						<>
							<HelpEmphasis>TOTP Secret Key</HelpEmphasis>:
							<HelpSubBullets
								items={[
									<>In the API Dashboard, click on <HelpEmphasis>TOTP Registration</HelpEmphasis> in the top-right menu.</>,
									<>Complete the verification by entering your mobile number, OTP, and client code.</>,
									<>When the QR code is displayed, find and copy the <HelpEmphasis>setup key (Base32 secret string)</HelpEmphasis>.</>,
									<>
										<HelpEmphasis>Warning:</HelpEmphasis> Do not enter a temporary 6-digit dynamic code. The setup key is a long, static code (e.g. <HelpCode>6WZMFIPODQGDKQ5SZQN4U2YXQ4</HelpCode>) which enables Rebound to generate OTPs dynamically.
									</>,
									<>Scan the QR code with your authenticator app (Google or Microsoft Authenticator) and complete the registration on the Kotak Neo screen.</>
								]}
							/>
						</>,
						<>
							<HelpEmphasis>MPIN</HelpEmphasis>:
							<HelpSubBullets
								items={[
									<>This is the 6-digit PIN used to login and trade within the Kotak Neo app.</>,
									<>If you forget it, you can reset it via <HelpEmphasis>Profile</HelpEmphasis> &rarr; <HelpEmphasis>Settings</HelpEmphasis> &rarr; <HelpEmphasis>Change MPIN</HelpEmphasis> in the Neo mobile app.</>
								]}
							/>
						</>,
						<>
							<HelpEmphasis>Mobile Number</HelpEmphasis>:
							<HelpSubBullets
								items={[
									<>Use your Kotak Securities registered mobile number.</>,
									<>Make sure to enter it in the format <HelpCode>+91XXXXXXXXXX</HelpCode> in Rebound settings.</>
								]}
							/>
						</>
					]}
				/>
			</HelpSection>

			<HelpSection title="Kotak Neo — Static IP Whitelisting">
				<HelpParagraph>
					Kotak Neo enforces strict static IP validation for all order placement APIs. You must whitelist your server or local environment&apos;s static IP to trade:
				</HelpParagraph>
				<HelpCallout>
					<HelpEmphasis>Deployment Server IP:</HelpEmphasis> <HelpCode>140.245.249.135</HelpCode>. Copy this address and whitelist it in your Kotak Neo dashboard.
				</HelpCallout>
				<HelpBullets
					items={[
						<>
							<HelpEmphasis>Whitelisting Steps</HelpEmphasis>:
							<HelpSubBullets
								items={[
									<>Log in to the Kotak Neo mobile app or web portal.</>,
									<>Go to the <HelpEmphasis>More</HelpEmphasis> tab &rarr; <HelpEmphasis>Trade API</HelpEmphasis> &rarr; <HelpEmphasis>API Dashboard</HelpEmphasis>.</>,
									<>Click on your API application, then click on <HelpEmphasis>Add IP</HelpEmphasis>.</>,
									<>Enter your <HelpEmphasis>Primary Static IP</HelpEmphasis> (and optional Secondary Static IP for backup).</>
								]}
							/>
						</>,
						<>
							<HelpEmphasis>Important Rules</HelpEmphasis>:
							<HelpSubBullets
								items={[
									<>You can whitelist a maximum of 2 IP addresses (Primary and Secondary).</>,
									<>IP changes are allowed only once every <HelpEmphasis>7 days</HelpEmphasis>.</>,
									<>IP validation is strictly enforced on order APIs (Place, Modify, Cancel). It is not enforced on login, data feed, or websocket APIs.</>,
									<>Your Rebound trading instance must run on the whitelisted IP, and the login session must be initiated from that same IP.</>
								]}
							/>
						</>
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
