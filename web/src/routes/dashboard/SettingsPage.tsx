import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSettings, updateSettings, type Settings, saveBrokerCreds, testBrokerConnection, getBrokerStatus, getBrokerCredsInfo, type BrokerTestRequest } from '@/api/user';
import { changePassword, updateProfile, mfaSetup, mfaVerify, mfaDisable } from '@/api/auth';
import { useState, useEffect } from 'react';
import QRCode from 'qrcode';
import { useNavigate, Link } from 'react-router-dom';
import { fieldErrorFor, validateChangePasswordForm, validateProfileForm } from '@/utils/authValidation';
import { getApiErrorMessage } from '@/utils/getApiErrorMessage';
import { PasswordConfirmHint, PasswordRequirementsChecklist } from '@/components/PasswordRequirementsChecklist';
import { PasswordInput } from '@/components/PasswordInput';
import { EmailInput } from '@/components/EmailInput';
import { useSessionStore } from '@/state/sessionStore';

export function SettingsPage() {
	const qc = useQueryClient();
	const navigate = useNavigate();
	const { user, refresh, logout } = useSessionStore();
	const { data, isLoading } = useQuery<Settings>({ queryKey: ['settings'], queryFn: getSettings });
	const [showFullCreds, setShowFullCreds] = useState(false);
	const { data: credsInfo } = useQuery({
		queryKey: ['brokerCredsInfo', showFullCreds],
		queryFn: () => getBrokerCredsInfo(showFullCreds)
	});
	const [form, setForm] = useState<Settings>({ trade_mode: 'paper', broker: null, broker_status: null });
	const mutation = useMutation({
		mutationFn: (input: Partial<Settings>) => updateSettings(input),
		onSuccess: () => qc.invalidateQueries({ queryKey: ['settings'] }),
	});
	const [apiKey, setApiKey] = useState('');
	const [apiSecret, setApiSecret] = useState('');
	const [mobileNumber, setMobileNumber] = useState('');
	const [mpin, setMpin] = useState('');
	const [totpSecret, setTotpSecret] = useState('');
	const [environment, setEnvironment] = useState('prod');
	const [testMode, setTestMode] = useState<'basic' | 'full'>('basic');
	const [brokerMsg, setBrokerMsg] = useState<string | null>(null);
	const [testing, setTesting] = useState(false);
	const [status, setStatus] = useState<{ broker: string | null; status: string | null } | null>(null);
	const [currentPassword, setCurrentPassword] = useState('');
	const [newPassword, setNewPassword] = useState('');
	const [confirmNewPassword, setConfirmNewPassword] = useState('');
	const [passwordFieldErrors, setPasswordFieldErrors] = useState<
		ReturnType<typeof validateChangePasswordForm>
	>([]);
	const [passwordMsg, setPasswordMsg] = useState<string | null>(null);
	const [passwordSaving, setPasswordSaving] = useState(false);
	const [profileName, setProfileName] = useState('');
	const [profileEmail, setProfileEmail] = useState('');
	const [profileMobile, setProfileMobile] = useState('');
	const [profileCurrentPassword, setProfileCurrentPassword] = useState('');
	const [profileFieldErrors, setProfileFieldErrors] = useState<ReturnType<typeof validateProfileForm>>([]);
	const [profileMsg, setProfileMsg] = useState<string | null>(null);
	const [profileSaving, setProfileSaving] = useState(false);
	const [mfaSetupData, setMfaSetupData] = useState<{
		secret: string;
		provisioning_uri: string;
		backup_codes: string[];
	} | null>(null);
	const [mfaQrDataUrl, setMfaQrDataUrl] = useState<string | null>(null);
	const [mfaCode, setMfaCode] = useState('');
	const [mfaMsg, setMfaMsg] = useState<string | null>(null);
	const [mfaLoading, setMfaLoading] = useState(false);

	useEffect(() => {
		if (user) {
			setProfileName(user.name ?? '');
			setProfileEmail(user.email);
			setProfileMobile(user.mobile_number ?? '');
		}
	}, [user]);

	useEffect(() => {
		getBrokerStatus().then(setStatus).catch(() => {});
	}, []);

	// Load stored credentials when showFullCreds is true or when credsInfo changes
	useEffect(() => {
		if (credsInfo?.has_creds && showFullCreds) {
			// Load full credentials into form fields
			if (credsInfo.api_key) setApiKey(credsInfo.api_key);
			if (credsInfo.api_secret) setApiSecret(credsInfo.api_secret);
			if (credsInfo.mobile_number) setMobileNumber(credsInfo.mobile_number);
			if (credsInfo.mpin) setMpin(credsInfo.mpin);
			if (credsInfo.totp_secret) setTotpSecret(credsInfo.totp_secret);
			if (credsInfo.environment) setEnvironment(credsInfo.environment);
		} else if (credsInfo?.has_creds && !showFullCreds) {
			// Clear fields when hiding
			setApiKey('');
			setApiSecret('');
			setMobileNumber('');
			setMpin('');
			setTotpSecret('');
			setEnvironment('prod');
		}
	}, [credsInfo, showFullCreds]);

	useEffect(() => {
		if (data) setForm(data);
	}, [data]);

	if (isLoading) return <div className="p-2 sm:p-4 text-sm sm:text-base">Loading settings...</div>;

	const isBroker = form.trade_mode === 'broker';
	const profileEmailChanging =
		(profileEmail.trim().toLowerCase() || '') !== (user?.email?.trim().toLowerCase() || '');

	return (
		<div className="p-2 sm:p-4 max-w-xl">
			<h1 className="text-lg sm:text-xl font-semibold mb-1">Account settings</h1>
			<p className="text-xs sm:text-sm text-[var(--muted)] mb-4 sm:mb-6">
				Update your email, mobile number, password, and broker connection.
			</p>
			<h2 id="account-profile" className="text-base sm:text-lg font-semibold mb-3 sm:mb-4">
				Account profile
			</h2>
			<div className="space-y-3 mb-6 pb-6 border-b border-[#1e293b]/50">
				<div>
					<label className="block text-xs sm:text-sm mb-1" htmlFor="profileName">
						Name
					</label>
					<input
						id="profileName"
						className="w-full px-3 py-2.5 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0 opacity-70"
						value={profileName}
						readOnly
						disabled
					/>
					<p className="text-xs text-[var(--muted)] mt-1">Contact support if you need to change your name.</p>
				</div>
				<div>
					<label className="block text-xs sm:text-sm mb-1" htmlFor="profileEmail">
						Email
					</label>
					<EmailInput
						id="profileEmail"
						className="w-full px-3 py-2.5 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
						value={profileEmail}
						onChange={(e) => setProfileEmail(e.target.value)}
						autoComplete="email"
					/>
					{fieldErrorFor(profileFieldErrors, 'profileEmail') && (
						<div className="text-red-400 text-xs mt-1">{fieldErrorFor(profileFieldErrors, 'profileEmail')}</div>
					)}
					<p className="text-xs text-[var(--muted)] mt-1">Changing email requires verifying the new address and your current password.</p>
				</div>
				{profileEmailChanging ? (
					<div>
						<label className="block text-xs sm:text-sm mb-1" htmlFor="profileCurrentPassword">
							Current password
						</label>
						<PasswordInput
							id="profileCurrentPassword"
							className="w-full px-3 py-2.5 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
							value={profileCurrentPassword}
							onChange={(e) => setProfileCurrentPassword(e.target.value)}
							autoComplete="current-password"
						/>
						{fieldErrorFor(profileFieldErrors, 'profileCurrentPassword') && (
							<div className="text-red-400 text-xs mt-1">
								{fieldErrorFor(profileFieldErrors, 'profileCurrentPassword')}
							</div>
						)}
					</div>
				) : null}
				<div>
					<label className="block text-xs sm:text-sm mb-1" htmlFor="profileMobile">
						Mobile number
					</label>
					<input
						id="profileMobile"
						type="tel"
						inputMode="numeric"
						className="w-full px-3 py-2.5 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
						value={profileMobile}
						onChange={(e) => setProfileMobile(e.target.value)}
						autoComplete="tel"
						placeholder="10-digit mobile (optional)"
					/>
					{fieldErrorFor(profileFieldErrors, 'profileMobile') && (
						<div className="text-red-400 text-xs mt-1">{fieldErrorFor(profileFieldErrors, 'profileMobile')}</div>
					)}
					<p className="text-xs text-[var(--muted)] mt-1">
						Your contact number for account purposes — not the Kotak broker login mobile below.
					</p>
				</div>
				<button
					type="button"
					disabled={profileSaving}
					onClick={async () => {
						setProfileMsg(null);
						const errors = validateProfileForm({
							email: profileEmail,
							originalEmail: user?.email ?? profileEmail,
							mobile: profileMobile,
							currentPassword: profileCurrentPassword,
						});
						setProfileFieldErrors(errors);
						if (errors.length > 0) {
							return;
						}
						setProfileSaving(true);
						try {
							const result = await updateProfile({
								email: profileEmail.trim(),
								mobile_number: profileMobile.trim() ? profileMobile : null,
								...(profileEmailChanging
									? { current_password: profileCurrentPassword }
									: {}),
							});
							setProfileMsg(result.message);
							if (result.verification_required) {
								logout();
								navigate(
									`/resend-verification?email=${encodeURIComponent(result.email)}`,
									{ replace: true, state: { profileMessage: result.message } },
								);
								return;
							}
							await refresh();
						} catch (err: unknown) {
							setProfileMsg(getApiErrorMessage(err, 'Profile update failed'));
						} finally {
							setProfileSaving(false);
						}
					}}
					className="bg-[var(--accent)] text-black px-4 py-3 sm:py-2 rounded text-sm sm:text-base min-h-[44px] sm:min-h-0 disabled:opacity-60"
				>
					{profileSaving ? 'Saving...' : 'Save profile'}
				</button>
				{profileMsg && (
					<div
						className={`text-xs sm:text-sm ${profileMsg.includes('successfully') || profileMsg.includes('Check your new email') ? 'text-green-400' : 'text-red-400'}`}
					>
						{profileMsg}
					</div>
				)}
			</div>
			<h2 className="text-base sm:text-lg font-semibold mb-3 sm:mb-4">Two-factor authentication</h2>
			<div className="space-y-3 mb-6 pb-6 border-b border-[#1e293b]/50">
				<p className="text-xs sm:text-sm text-[var(--muted)]">
					{user?.mfa_enabled
						? 'MFA is enabled on your account.'
						: 'Add an authenticator app for stronger account protection.'}
				</p>
				{!user?.mfa_enabled && !mfaSetupData && (
					<button
						type="button"
						className="px-4 py-2 rounded bg-[#1e293b] text-sm"
						disabled={mfaLoading}
						onClick={async () => {
							setMfaLoading(true);
							setMfaMsg(null);
							try {
								const data = await mfaSetup();
								setMfaSetupData(data);
								const dataUrl = await QRCode.toDataURL(data.provisioning_uri, {
									width: 200,
									margin: 2,
									color: { dark: '#000000', light: '#ffffff' },
								});
								setMfaQrDataUrl(dataUrl);
							} catch (e) {
								setMfaMsg(getApiErrorMessage(e, 'MFA setup failed'));
							} finally {
								setMfaLoading(false);
							}
						}}
					>
						{mfaLoading ? 'Starting...' : 'Set up MFA'}
					</button>
				)}
				{mfaSetupData && !user?.mfa_enabled && (
					<div className="space-y-3 text-xs sm:text-sm">
						<p className="font-medium">Scan the QR code with your authenticator app (Google Authenticator, Authy, etc.)</p>
						{mfaQrDataUrl ? (
							<div className="flex justify-center">
								<img
									src={mfaQrDataUrl}
									alt="MFA QR code — scan with your authenticator app"
									width={200}
									height={200}
									className="rounded border border-[#1e293b] bg-white p-2"
								/>
							</div>
						) : (
							<p className="text-[var(--muted)]">Generating QR code...</p>
						)}
						<details className="text-[var(--muted)]">
							<summary className="cursor-pointer select-none hover:text-[var(--fg)] transition-colors">
								Can't scan? Enter secret manually
							</summary>
							<p className="mt-1 font-mono break-all bg-[#0f1720] rounded px-2 py-1 text-xs select-all">
								{mfaSetupData.secret}
							</p>
						</details>
						<div className="bg-[#0f1720] rounded px-3 py-2 border border-[#1e293b]">
							<p className="font-medium mb-1 text-amber-400">⚠ Save your backup codes</p>
							<p className="text-[var(--muted)] mb-1">Store these somewhere safe — each can be used once if you lose your authenticator:</p>
							<p className="font-mono text-xs break-all select-all">{mfaSetupData.backup_codes.join('  ')}</p>
						</div>
						<div>
							<label className="block mb-1" htmlFor="mfaConfirmCode">Enter the 6-digit code from your app to confirm</label>
							<input
								id="mfaConfirmCode"
								className="w-full px-3 py-2 rounded bg-[#0f1720] border border-[#1e293b] font-mono tracking-widest"
								placeholder="000000"
								maxLength={6}
								inputMode="numeric"
								value={mfaCode}
								onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
							/>
						</div>
						<button
							type="button"
							className="px-4 py-2 rounded bg-blue-600 text-sm disabled:opacity-60"
							disabled={mfaCode.length !== 6}
							onClick={async () => {
								try {
									await mfaVerify(mfaCode);
									setMfaMsg('MFA enabled successfully.');
									setMfaSetupData(null);
									setMfaQrDataUrl(null);
									setMfaCode('');
									await refresh();
								} catch (e) {
									setMfaMsg(getApiErrorMessage(e, 'Invalid code'));
								}
							}}
						>
							Confirm & Enable MFA
						</button>
					</div>
				)}
				{user?.mfa_enabled && (
					<div className="space-y-2">
						<input
							className="w-full px-3 py-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm"
							type="password"
							placeholder="Current password"
							value={currentPassword}
							onChange={(e) => setCurrentPassword(e.target.value)}
						/>
						<input
							className="w-full px-3 py-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm"
							placeholder="MFA or backup code"
							value={mfaCode}
							onChange={(e) => setMfaCode(e.target.value)}
						/>
						<button
							type="button"
							className="px-4 py-2 rounded bg-red-900/50 text-sm"
							onClick={async () => {
								try {
									await mfaDisable(currentPassword, mfaCode);
									setMfaMsg('MFA disabled');
									setMfaCode('');
									await refresh();
								} catch (e) {
									setMfaMsg(getApiErrorMessage(e, 'Could not disable MFA'));
								}
							}}
						>
							Disable MFA
						</button>
					</div>
				)}
				{mfaMsg && <div className="text-xs sm:text-sm text-green-400">{mfaMsg}</div>}
			</div>
			<h2 className="text-base sm:text-lg font-semibold mb-3 sm:mb-4">Account password</h2>
			<div className="space-y-3 mb-6 pb-6 border-b border-[#1e293b]/50">
				<div>
					<label className="block text-xs sm:text-sm mb-1" htmlFor="currentPassword">
						Current password
					</label>
					<PasswordInput
						id="currentPassword"
						autoComplete="current-password"
						className="w-full px-3 py-2.5 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
						value={currentPassword}
						onChange={(e) => setCurrentPassword(e.target.value)}
					/>
					{fieldErrorFor(passwordFieldErrors, 'currentPassword') && (
						<div className="text-red-400 text-xs mt-1">{fieldErrorFor(passwordFieldErrors, 'currentPassword')}</div>
					)}
				</div>
				<div>
					<label className="block text-xs sm:text-sm mb-1" htmlFor="newPassword">
						New password
					</label>
					<PasswordInput
						id="newPassword"
						autoComplete="new-password"
						className="w-full px-3 py-2.5 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
						value={newPassword}
						onChange={(e) => setNewPassword(e.target.value)}
					/>
					{fieldErrorFor(passwordFieldErrors, 'newPassword') && (
						<div className="text-red-400 text-xs mt-1">{fieldErrorFor(passwordFieldErrors, 'newPassword')}</div>
					)}
					<PasswordRequirementsChecklist password={newPassword} />
				</div>
				<div>
					<label className="block text-xs sm:text-sm mb-1" htmlFor="confirmNewPassword">
						Confirm new password
					</label>
					<PasswordInput
						id="confirmNewPassword"
						autoComplete="new-password"
						className="w-full px-3 py-2.5 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
						value={confirmNewPassword}
						onChange={(e) => setConfirmNewPassword(e.target.value)}
					/>
					{fieldErrorFor(passwordFieldErrors, 'confirmPassword') && (
						<div className="text-red-400 text-xs mt-1">{fieldErrorFor(passwordFieldErrors, 'confirmPassword')}</div>
					)}
					<PasswordConfirmHint password={newPassword} confirmPassword={confirmNewPassword} />
				</div>
				<button
					type="button"
					disabled={passwordSaving}
					onClick={async () => {
						setPasswordMsg(null);
						const errors = validateChangePasswordForm({
							currentPassword,
							newPassword,
							confirmPassword: confirmNewPassword,
						});
						setPasswordFieldErrors(errors);
						if (errors.length > 0) {
							return;
						}
						setPasswordSaving(true);
						try {
							await changePassword(currentPassword, newPassword);
							setPasswordMsg('Password updated successfully.');
							setCurrentPassword('');
							setNewPassword('');
							setConfirmNewPassword('');
						} catch (err: unknown) {
							setPasswordMsg(getApiErrorMessage(err, 'Password update failed'));
						} finally {
							setPasswordSaving(false);
						}
					}}
					className="bg-[var(--accent)] text-black px-4 py-3 sm:py-2 rounded text-sm sm:text-base min-h-[44px] sm:min-h-0 disabled:opacity-60"
				>
					{passwordSaving ? 'Updating...' : 'Update password'}
				</button>
				{passwordMsg && (
					<div
						className={`text-xs sm:text-sm ${passwordMsg.includes('successfully') ? 'text-green-400' : 'text-red-400'}`}
					>
						{passwordMsg}
					</div>
				)}
			</div>
			<h2 className="text-base sm:text-lg font-semibold mb-3 sm:mb-4">Trading mode</h2>
			<p className="text-xs sm:text-sm text-[var(--muted)] mb-3">
				Setting up Kotak for live trading? See the{' '}
				<Link to="/help/connect-broker" className="text-[var(--accent)] hover:underline">
					Help — Connect your broker
				</Link>{' '}
				guide.
			</p>
			<div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4 mb-4 sm:mb-6">
				<label className="flex items-center gap-2 min-h-[44px] sm:min-h-0">
					<input type="radio" checked={form.trade_mode === 'paper'} onChange={() => setForm({ ...form, trade_mode: 'paper' })} className="w-4 h-4" />
					<span className="text-sm sm:text-base">Paper Trade (default)</span>
				</label>
				<label className="flex items-center gap-2 min-h-[44px] sm:min-h-0">
					<input type="radio" checked={form.trade_mode === 'broker'} onChange={() => setForm({ ...form, trade_mode: 'broker' })} className="w-4 h-4" />
					<span className="text-sm sm:text-base">Kotak Neo</span>
				</label>
			</div>
			{isBroker && (
				<div className="space-y-3 mb-6">
					<div>
						<label className="block text-xs sm:text-sm mb-1">Broker</label>
						<input className="w-full px-3 py-2.5 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0" value={form.broker ?? ''} onChange={(e) => setForm({ ...form, broker: e.target.value })} placeholder="kotak-neo" />
					</div>
					<div className="space-y-3">
						<div className="flex items-center justify-between mt-4">
							<h3 className="text-xs sm:text-sm font-semibold">Basic Credentials</h3>
							{credsInfo?.has_creds && (
								<button
									type="button"
									onClick={() => {
										setShowFullCreds(!showFullCreds);
										qc.invalidateQueries({ queryKey: ['brokerCredsInfo'] });
									}}
									className="text-xs sm:text-sm text-blue-400 hover:text-blue-300 underline min-h-[44px] sm:min-h-0"
								>
									{showFullCreds ? 'Hide' : 'Show'} Full Credentials
								</button>
							)}
						</div>
						{credsInfo?.has_creds && (
							<div className="text-xs sm:text-sm text-green-400 mb-2">
								[OK] Credentials stored {showFullCreds ? '(showing full values)' : '(click Show to view/edit)'}
							</div>
						)}
						<div>
							<label className="block text-xs sm:text-sm mb-1">App Token (API Key)</label>
							<input
								className="w-full px-3 py-2.5 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
								value={apiKey}
								onChange={(e) => setApiKey(e.target.value)}
								placeholder={credsInfo?.has_creds && !showFullCreds ? `Stored: ${credsInfo.api_key_masked}` : "Enter App Token"}
							/>
							{credsInfo?.has_creds && !showFullCreds && (
								<div className="text-xs text-[var(--muted)] mt-1">
									Current: {credsInfo.api_key_masked} (click Show to view/edit)
								</div>
							)}
						</div>
						<div>
							<label className="block text-xs sm:text-sm mb-1">Client ID (UCC)</label>
							<PasswordInput
								className="w-full px-3 py-2.5 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
								value={apiSecret}
								onChange={(e) => setApiSecret(e.target.value)}
								placeholder={credsInfo?.has_creds && !showFullCreds ? `Stored: ${credsInfo.api_secret_masked}` : "Enter Client ID (UCC)"}
								autoComplete="off"
							/>
							{credsInfo?.has_creds && !showFullCreds && (
								<div className="text-xs text-[var(--muted)] mt-1">
									Current: {credsInfo.api_secret_masked} (click Show to view/edit)
								</div>
							)}
						</div>

						<div className="mt-4">
							<label className="block text-xs sm:text-sm font-semibold mb-2">Connection Test Mode</label>
							<div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4 mb-3">
								<label className="flex items-center gap-2 min-h-[44px] sm:min-h-0">
									<input type="radio" checked={testMode === 'basic'} onChange={() => setTestMode('basic')} className="w-4 h-4" />
									<span className="text-xs sm:text-sm">Basic Test (API Key/Secret only)</span>
								</label>
								<label className="flex items-center gap-2 min-h-[44px] sm:min-h-0">
									<input type="radio" checked={testMode === 'full'} onChange={() => setTestMode('full')} className="w-4 h-4" />
									<span className="text-xs sm:text-sm">Full Test (REST login + MPIN validate)</span>
								</label>
							</div>
						</div>

						<div className="space-y-3 mt-4 p-3 sm:p-4 border border-[#1e293b] rounded">
							<h4 className="text-xs sm:text-sm font-semibold">Required for REST Login</h4>
							{credsInfo?.has_creds && !showFullCreds && (
								<div className="text-xs text-[var(--muted)] mb-2">
									Stored credentials available. Click "Show Full Credentials" above to view/edit.
								</div>
							)}
							<div>
								<label className="block text-xs sm:text-sm mb-1">Mobile Number</label>
								<input
									className="w-full px-3 py-2.5 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
									type="tel"
									value={mobileNumber}
									onChange={(e) => setMobileNumber(e.target.value)}
									placeholder={credsInfo?.has_creds && !showFullCreds ? "Stored (click Show to view)" : "Enter mobile number"}
									disabled={credsInfo?.has_creds && !showFullCreds}
								/>
							</div>
							<div>
								<label className="block text-xs sm:text-sm mb-1">MPIN (for 2FA)</label>
								<PasswordInput
									className="w-full px-3 py-2.5 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
									value={mpin}
									onChange={(e) => setMpin(e.target.value)}
									placeholder={credsInfo?.has_creds && !showFullCreds ? "Stored (click Show to view)" : "Enter MPIN"}
									disabled={credsInfo?.has_creds && !showFullCreds}
									autoComplete="off"
								/>
							</div>
							<div>
								<label className="block text-xs sm:text-sm mb-1">TOTP Secret</label>
								<PasswordInput
									className="w-full px-3 py-2.5 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
									value={totpSecret}
									onChange={(e) => setTotpSecret(e.target.value)}
									placeholder={credsInfo?.has_creds && !showFullCreds ? "Stored (click Show to view)" : "Enter TOTP Secret"}
									disabled={credsInfo?.has_creds && !showFullCreds}
									autoComplete="off"
								/>
							</div>
							<div>
								<label className="block text-xs sm:text-sm mb-1">Environment</label>
								<input
									className="w-full px-3 py-2.5 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
									value={environment}
									onChange={(e) => setEnvironment(e.target.value)}
									placeholder="prod"
									disabled={credsInfo?.has_creds && !showFullCreds}
								/>
							</div>
						</div>

						<div className="flex flex-col sm:flex-row gap-2 mt-4">
							<button
								className="bg-blue-600 text-white px-4 py-3 sm:py-2 rounded disabled:opacity-50 min-h-[44px] sm:min-h-0 text-sm sm:text-base"
								onClick={async () => {
									setBrokerMsg(null);
									if (!apiKey || !apiSecret || !mobileNumber || !mpin || !totpSecret) {
										setBrokerMsg('Please enter App Token, Client ID (UCC), Mobile Number, MPIN, and TOTP Secret');
										return;
									}

									await saveBrokerCreds({
										broker: form.broker ?? 'kotak-neo',
										api_key: apiKey,
										api_secret: apiSecret,
										mobile_number: mobileNumber || undefined,
										mpin: mpin || undefined,
										totp_secret: totpSecret || undefined,
										environment: environment || undefined,
									});
									setBrokerMsg('Credentials saved');
									qc.invalidateQueries({ queryKey: ['brokerCredsInfo'] });
									// Refresh to show updated credentials
									setShowFullCreds(true);
								}}
								disabled={!apiKey || !apiSecret}
							>
								{credsInfo?.has_creds ? 'Update Credentials' : 'Save Credentials'}
							</button>
							<button
								className="bg-emerald-600 text-white px-4 py-3 sm:py-2 rounded disabled:opacity-50 min-h-[44px] sm:min-h-0 text-sm sm:text-base"
								onClick={async () => {
									setTesting(true);
									setBrokerMsg(null);
									try {
										// Load full credentials if needed for full test
										let fullCredsInfo = credsInfo;
										if (testMode === 'full' && credsInfo?.has_creds && !showFullCreds) {
											// Fetch full credentials for testing
											fullCredsInfo = await getBrokerCredsInfo(true);
										}

										// Use form values if entered, otherwise use stored values
										const payload: BrokerTestRequest = {
											broker: form.broker ?? 'kotak-neo',
											api_key: apiKey || fullCredsInfo?.api_key || '',
											api_secret: apiSecret || fullCredsInfo?.api_secret || '',
										};

										if (testMode === 'full') {
											payload.mobile_number = mobileNumber || fullCredsInfo?.mobile_number || '';
											payload.mpin = mpin || fullCredsInfo?.mpin || '';
											payload.totp_secret = totpSecret || fullCredsInfo?.totp_secret || '';
											payload.environment = environment || fullCredsInfo?.environment || 'prod';
										}

										const res = await testBrokerConnection(payload);
										setBrokerMsg(res.message ?? (res.ok ? 'Connection successful!' : 'Connection failed'));
										const s = await getBrokerStatus().catch(() => null);
										if (s) setStatus(s);
									} catch (error: unknown) {
										const errorMessage = error instanceof Error ? error.message : 'Test failed';
										setBrokerMsg(errorMessage);
									} finally {
										setTesting(false);
									}
								}}
								disabled={
									testing ||
									// Basic test: need api_key and api_secret (from form or stored)
									(!apiKey && !credsInfo?.has_creds) ||
									(!apiSecret && !credsInfo?.has_creds) ||
									// Full test: need all credentials (from form or stored)
									(testMode === 'full' &&
										(
											(!mobileNumber && !credsInfo?.has_creds) ||
											(!mpin && !credsInfo?.has_creds) ||
											(!totpSecret && !credsInfo?.has_creds)
										))
								}
							>
								{testing ? 'Testing...' : testMode === 'full' ? 'Test Full Connection' : 'Test Basic Connection'}
							</button>
							{testMode === 'full' && credsInfo?.has_creds && !showFullCreds && (
								<div className="text-xs text-[var(--muted)] mt-1">
									Note: Will use stored credentials if fields are empty
								</div>
							)}
						</div>
						{brokerMsg && (
							<div className={`text-xs sm:text-sm mt-2 ${brokerMsg.includes('successful') || brokerMsg.includes('OK') ? 'text-green-400' : 'text-red-400'}`}>
								{brokerMsg}
							</div>
						)}
						{status && <div className="text-sm text-[var(--muted)] mt-2">Status: {status.status ?? 'Unknown'}</div>}
					</div>
				</div>
			)}
			<button
				onClick={() => mutation.mutate({ trade_mode: form.trade_mode, broker: form.broker ?? undefined })}
				className="bg-[var(--accent)] text-black px-4 py-3 sm:py-2 rounded text-sm sm:text-base min-h-[44px] sm:min-h-0"
				disabled={mutation.isPending}
			>
				{mutation.isPending ? 'Saving...' : 'Save settings'}
			</button>
		</div>
	);
}
