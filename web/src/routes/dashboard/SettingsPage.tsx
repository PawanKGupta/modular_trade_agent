import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
	getSettings,
	updateSettings,
	type Settings,
	saveBrokerCreds,
	testBrokerConnection,
	getBrokerStatus,
	getBrokerCredsInfo,
	type BrokerTestRequest,
} from '@/api/user';
import { changePassword, updateProfile, mfaSetup, mfaVerify, mfaDisable } from '@/api/auth';
import { useState, useEffect, useCallback } from 'react';
import QRCode from 'qrcode';
import { useNavigate, Link } from 'react-router-dom';
import {
	fieldErrorFor,
	validateChangePasswordForm,
	validateProfileForm,
} from '@/utils/authValidation';
import { getApiErrorMessage } from '@/utils/getApiErrorMessage';
import {
	PasswordConfirmHint,
	PasswordRequirementsChecklist,
} from '@/components/PasswordRequirementsChecklist';
import { PasswordInput } from '@/components/PasswordInput';
import { EmailInput } from '@/components/EmailInput';
import { useSessionStore } from '@/state/sessionStore';

// ── Accordion card ────────────────────────────────────────────────────────────

type SectionCardProps = {
	id: string;
	icon: string;
	title: string;
	badge?: React.ReactNode;
	isOpen: boolean;
	onToggle: () => void;
	children: React.ReactNode;
};

function SectionCard({ id, icon, title, badge, isOpen, onToggle, children }: SectionCardProps) {
	return (
		<div className="rounded-lg border border-[#1e293b] bg-[#0c1521] overflow-hidden transition-shadow hover:shadow-[0_0_0_1px_#334155]">
			<button
				type="button"
				id={`${id}-header`}
				aria-expanded={isOpen}
				aria-controls={`${id}-body`}
				onClick={onToggle}
				className="w-full flex items-center justify-between px-4 py-3.5 text-left gap-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
			>
				<div className="flex items-center gap-3 min-w-0">
					<span className="text-base shrink-0">{icon}</span>
					<span className="font-medium text-sm sm:text-base truncate">{title}</span>
					{badge}
				</div>
				<svg
					className={`w-4 h-4 shrink-0 text-[var(--muted)] transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
					viewBox="0 0 20 20"
					fill="currentColor"
					aria-hidden="true"
				>
					<path
						fillRule="evenodd"
						d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
						clipRule="evenodd"
					/>
				</svg>
			</button>

			{/* Animated body */}
			<div
				id={`${id}-body`}
				role="region"
				aria-labelledby={`${id}-header`}
				className={`transition-all duration-200 ease-in-out ${isOpen ? 'max-h-[9999px] opacity-100' : 'max-h-0 opacity-0 overflow-hidden pointer-events-none'}`}
			>
				<div className="px-4 pb-5 pt-1 border-t border-[#1e293b] space-y-4">{children}</div>
			</div>
		</div>
	);
}

function StatusBadge({
	label,
	variant,
}: {
	label: string;
	variant: 'green' | 'amber' | 'blue' | 'muted';
}) {
	const colours = {
		green: 'bg-emerald-500/15 text-emerald-400 ring-emerald-500/25',
		amber: 'bg-amber-500/15 text-amber-400 ring-amber-500/25',
		blue: 'bg-blue-500/15 text-blue-400 ring-blue-500/25',
		muted: 'bg-[#1e293b] text-[var(--muted)] ring-[#334155]',
	};
	return (
		<span
			className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ring-inset ${colours[variant]} shrink-0`}
		>
			{label}
		</span>
	);
}

// ── Main page ─────────────────────────────────────────────────────────────────

type SectionKey = 'profile' | 'security' | 'password' | 'trading';

export function SettingsPage() {
	const qc = useQueryClient();
	const navigate = useNavigate();
	const { user, refresh, logout } = useSessionStore();
	const { data, isLoading } = useQuery<Settings>({ queryKey: ['settings'], queryFn: getSettings });
	const [showFullCreds, setShowFullCreds] = useState(false);
	const { data: credsInfo } = useQuery({
		queryKey: ['brokerCredsInfo', showFullCreds],
		queryFn: () => getBrokerCredsInfo(showFullCreds),
	});
	const [form, setForm] = useState<Settings>({ trade_mode: 'paper', broker: null, broker_status: null });
	const mutation = useMutation({
		mutationFn: (input: Partial<Settings>) => updateSettings(input),
		onSuccess: () => qc.invalidateQueries({ queryKey: ['settings'] }),
	});

	// Accordion open state — all sections collapsed by default
	const [openSection, setOpenSection] = useState<SectionKey>('' as SectionKey);
	const toggle = useCallback(
		(key: SectionKey) => setOpenSection((prev) => (prev === key ? ('' as SectionKey) : key)),
		[],
	);

	// Broker creds form
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

	// Password form
	const [currentPassword, setCurrentPassword] = useState('');
	const [newPassword, setNewPassword] = useState('');
	const [confirmNewPassword, setConfirmNewPassword] = useState('');
	const [passwordFieldErrors, setPasswordFieldErrors] = useState<
		ReturnType<typeof validateChangePasswordForm>
	>([]);
	const [passwordMsg, setPasswordMsg] = useState<string | null>(null);
	const [passwordSaving, setPasswordSaving] = useState(false);

	// Profile form
	const [profileName, setProfileName] = useState('');
	const [profileEmail, setProfileEmail] = useState('');
	const [profileMobile, setProfileMobile] = useState('');
	const [profileCurrentPassword, setProfileCurrentPassword] = useState('');
	const [profileFieldErrors, setProfileFieldErrors] = useState<ReturnType<typeof validateProfileForm>>([]);
	const [profileMsg, setProfileMsg] = useState<string | null>(null);
	const [profileSaving, setProfileSaving] = useState(false);

	// MFA state
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

	useEffect(() => {
		if (credsInfo?.has_creds && showFullCreds) {
			if (credsInfo.api_key) setApiKey(credsInfo.api_key);
			if (credsInfo.api_secret) setApiSecret(credsInfo.api_secret);
			if (credsInfo.mobile_number) setMobileNumber(credsInfo.mobile_number);
			if (credsInfo.mpin) setMpin(credsInfo.mpin);
			if (credsInfo.totp_secret) setTotpSecret(credsInfo.totp_secret);
			if (credsInfo.environment) setEnvironment(credsInfo.environment);
		} else if (credsInfo?.has_creds && !showFullCreds) {
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

	const inputCls =
		'w-full px-3 py-2.5 sm:py-2 rounded bg-[#070e17] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0 focus:outline-none focus:border-[var(--accent)] transition-colors';

	return (
		<div className="p-2 sm:p-4 max-w-xl">
			<h1 className="text-lg sm:text-xl font-semibold mb-1">Account settings</h1>
			<p className="text-xs sm:text-sm text-[var(--muted)] mb-5">
				Manage your profile, security, and trading configuration.
			</p>

			<div className="space-y-3">
				{/* ── Profile ───────────────────────────────────────────────── */}
				<SectionCard
					id="section-profile"
					icon="👤"
					title="Account profile"
					badge={
						user?.email_verified ? (
							<StatusBadge label="Verified" variant="green" />
						) : (
							<StatusBadge label="Unverified" variant="amber" />
						)
					}
					isOpen={openSection === 'profile'}
					onToggle={() => toggle('profile')}
				>
					<div>
						<label className="block text-xs sm:text-sm mb-1" htmlFor="profileName">
							Name
						</label>
						<input
							id="profileName"
							className={`${inputCls} opacity-60`}
							value={profileName}
							readOnly
							disabled
						/>
						<p className="text-xs text-[var(--muted)] mt-1">
							Contact support if you need to change your name.
						</p>
					</div>

					<div>
						<label className="block text-xs sm:text-sm mb-1" htmlFor="profileEmail">
							Email
						</label>
						<EmailInput
							id="profileEmail"
							className={inputCls}
							value={profileEmail}
							onChange={(e) => setProfileEmail(e.target.value)}
							autoComplete="email"
						/>
						{fieldErrorFor(profileFieldErrors, 'profileEmail') && (
							<div className="text-red-400 text-xs mt-1">
								{fieldErrorFor(profileFieldErrors, 'profileEmail')}
							</div>
						)}
						<p className="text-xs text-[var(--muted)] mt-1">
							Changing email requires verifying the new address and your current password.
						</p>
					</div>

					{profileEmailChanging && (
						<div>
							<label className="block text-xs sm:text-sm mb-1" htmlFor="profileCurrentPassword">
								Current password
							</label>
							<PasswordInput
								id="profileCurrentPassword"
								className={inputCls}
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
					)}

					<div>
						<label className="block text-xs sm:text-sm mb-1" htmlFor="profileMobile">
							Mobile number
						</label>
						<input
							id="profileMobile"
							type="tel"
							inputMode="numeric"
							className={inputCls}
							value={profileMobile}
							onChange={(e) => setProfileMobile(e.target.value)}
							autoComplete="tel"
							placeholder="10-digit mobile (optional)"
						/>
						{fieldErrorFor(profileFieldErrors, 'profileMobile') && (
							<div className="text-red-400 text-xs mt-1">
								{fieldErrorFor(profileFieldErrors, 'profileMobile')}
							</div>
						)}
						<p className="text-xs text-[var(--muted)] mt-1">
							Your contact number for account purposes — not the Kotak broker login mobile below.
						</p>
					</div>

					<div className="flex items-center gap-3 pt-1">
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
								if (errors.length > 0) return;
								setProfileSaving(true);
								try {
									const result = await updateProfile({
										email: profileEmail.trim(),
										mobile_number: profileMobile.trim() ? profileMobile : null,
										...(profileEmailChanging ? { current_password: profileCurrentPassword } : {}),
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
							className="bg-[var(--accent)] text-black px-4 py-2 rounded text-sm min-h-[40px] disabled:opacity-60 font-medium"
						>
							{profileSaving ? 'Saving…' : 'Save profile'}
						</button>
						{profileMsg && (
							<span
								className={`text-xs sm:text-sm ${profileMsg.includes('successfully') || profileMsg.includes('Check your new email') ? 'text-emerald-400' : 'text-red-400'}`}
							>
								{profileMsg}
							</span>
						)}
					</div>
				</SectionCard>

				{/* ── Security (MFA) ────────────────────────────────────────── */}
				<SectionCard
					id="section-security"
					icon="🔐"
					title="Security &amp; two-factor auth"
					badge={
						user?.mfa_enabled ? (
							<StatusBadge label="MFA On" variant="green" />
						) : (
							<StatusBadge label="MFA Off" variant="muted" />
						)
					}
					isOpen={openSection === 'security'}
					onToggle={() => toggle('security')}
				>
					{/* MFA not enabled — setup flow */}
					{!user?.mfa_enabled && !mfaSetupData && (
						<div className="space-y-3">
							<p className="text-xs sm:text-sm text-[var(--muted)]">
								Add an authenticator app (Google Authenticator, Authy…) for stronger account
								protection.
							</p>
							<button
								type="button"
								className="px-4 py-2 rounded bg-[#1e293b] hover:bg-[#263348] text-sm transition-colors min-h-[40px] disabled:opacity-60"
								disabled={mfaLoading}
								onClick={async () => {
									setMfaLoading(true);
									setMfaMsg(null);
									try {
										const setupData = await mfaSetup();
										setMfaSetupData(setupData);
										const dataUrl = await QRCode.toDataURL(setupData.provisioning_uri, {
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
								{mfaLoading ? 'Starting…' : 'Set up MFA'}
							</button>
						</div>
					)}

					{/* MFA setup wizard */}
					{mfaSetupData && !user?.mfa_enabled && (
						<div className="space-y-4 text-sm">
							<p className="font-medium">
								Scan the QR code with your authenticator app, then confirm with the 6-digit code.
							</p>

							{mfaQrDataUrl ? (
								<div className="flex justify-center">
									<img
										src={mfaQrDataUrl}
										alt="MFA QR code — scan with your authenticator app"
										width={200}
										height={200}
										className="rounded-lg border border-[#1e293b] bg-white p-2"
									/>
								</div>
							) : (
								<p className="text-[var(--muted)] text-xs">Generating QR code…</p>
							)}

							<details className="text-[var(--muted)] text-xs">
								<summary className="cursor-pointer select-none hover:text-[var(--fg)] transition-colors">
									Can't scan? Enter secret manually
								</summary>
								<p className="mt-1 font-mono break-all bg-[#070e17] rounded px-2 py-1 select-all">
									{mfaSetupData.secret}
								</p>
							</details>

							<div className="bg-amber-950/30 rounded-lg px-3 py-3 border border-amber-500/20">
								<p className="font-medium text-amber-400 text-xs mb-1">⚠ Save your backup codes</p>
								<p className="text-[var(--muted)] text-xs mb-2">
									Store these somewhere safe — each works once if you lose your authenticator:
								</p>
								<p className="font-mono text-xs break-all select-all text-[var(--fg)]">
									{mfaSetupData.backup_codes.join('  ')}
								</p>
							</div>

							<div>
								<label className="block text-xs mb-1" htmlFor="mfaConfirmCode">
									Enter the 6-digit code to confirm
								</label>
								<input
									id="mfaConfirmCode"
									className={`${inputCls} font-mono tracking-widest`}
									placeholder="000000"
									maxLength={6}
									inputMode="numeric"
									value={mfaCode}
									onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
								/>
							</div>

							<button
								type="button"
								className="w-full px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-sm font-medium min-h-[40px] disabled:opacity-60 transition-colors"
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
								Confirm &amp; Enable MFA
							</button>
						</div>
					)}

					{/* MFA enabled — disable flow */}
					{user?.mfa_enabled && (
						<div className="space-y-3">
							<p className="text-xs sm:text-sm text-[var(--muted)]">
								MFA is active on your account. To disable it, enter your password and a current
								authenticator code.
							</p>
							<input
								className={`${inputCls}`}
								type="password"
								placeholder="Current password"
								value={currentPassword}
								onChange={(e) => setCurrentPassword(e.target.value)}
								autoComplete="current-password"
							/>
							<input
								className={`${inputCls} font-mono tracking-widest`}
								placeholder="6-digit authenticator or backup code"
								value={mfaCode}
								onChange={(e) => setMfaCode(e.target.value)}
								inputMode="numeric"
							/>
							<button
								type="button"
								className="px-4 py-2 rounded bg-red-900/60 hover:bg-red-900/80 border border-red-500/20 text-sm font-medium min-h-[40px] transition-colors"
								onClick={async () => {
									try {
										await mfaDisable(currentPassword, mfaCode);
										setMfaMsg('MFA disabled.');
										setMfaCode('');
										setCurrentPassword('');
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

					{mfaMsg && (
						<div
							className={`text-xs sm:text-sm ${mfaMsg.toLowerCase().includes('disabled') ? 'text-amber-400' : mfaMsg.toLowerCase().includes('failed') || mfaMsg.toLowerCase().includes('invalid') ? 'text-red-400' : 'text-emerald-400'}`}
						>
							{mfaMsg}
						</div>
					)}
				</SectionCard>

				{/* ── Password ─────────────────────────────────────────────── */}
				<SectionCard
					id="section-password"
					icon="🔑"
					title="Account password"
					isOpen={openSection === 'password'}
					onToggle={() => toggle('password')}
				>
					<div>
						<label className="block text-xs sm:text-sm mb-1" htmlFor="currentPassword">
							Current password
						</label>
						<PasswordInput
							id="currentPassword"
							autoComplete="current-password"
							className={inputCls}
							value={currentPassword}
							onChange={(e) => setCurrentPassword(e.target.value)}
						/>
						{fieldErrorFor(passwordFieldErrors, 'currentPassword') && (
							<div className="text-red-400 text-xs mt-1">
								{fieldErrorFor(passwordFieldErrors, 'currentPassword')}
							</div>
						)}
					</div>

					<div>
						<label className="block text-xs sm:text-sm mb-1" htmlFor="newPassword">
							New password
						</label>
						<PasswordInput
							id="newPassword"
							autoComplete="new-password"
							className={inputCls}
							value={newPassword}
							onChange={(e) => setNewPassword(e.target.value)}
						/>
						{fieldErrorFor(passwordFieldErrors, 'newPassword') && (
							<div className="text-red-400 text-xs mt-1">
								{fieldErrorFor(passwordFieldErrors, 'newPassword')}
							</div>
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
							className={inputCls}
							value={confirmNewPassword}
							onChange={(e) => setConfirmNewPassword(e.target.value)}
						/>
						{fieldErrorFor(passwordFieldErrors, 'confirmPassword') && (
							<div className="text-red-400 text-xs mt-1">
								{fieldErrorFor(passwordFieldErrors, 'confirmPassword')}
							</div>
						)}
						<PasswordConfirmHint password={newPassword} confirmPassword={confirmNewPassword} />
					</div>

					<div className="flex items-center gap-3 pt-1">
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
								if (errors.length > 0) return;
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
							className="bg-[var(--accent)] text-black px-4 py-2 rounded text-sm min-h-[40px] disabled:opacity-60 font-medium"
						>
							{passwordSaving ? 'Updating…' : 'Update password'}
						</button>
						{passwordMsg && (
							<span
								className={`text-xs sm:text-sm ${passwordMsg.includes('successfully') ? 'text-emerald-400' : 'text-red-400'}`}
							>
								{passwordMsg}
							</span>
						)}
					</div>
				</SectionCard>

				{/* ── Trading account ──────────────────────────────────────── */}
				<SectionCard
					id="section-trading"
					icon="📈"
					title="Trading account"
					badge={
						form.trade_mode === 'broker' ? (
							<StatusBadge
								label={status?.status === 'connected' ? 'Live · Connected' : 'Live · Broker'}
								variant={status?.status === 'connected' ? 'green' : 'blue'}
							/>
						) : (
							<StatusBadge label="Paper Trade" variant="muted" />
						)
					}
					isOpen={openSection === 'trading'}
					onToggle={() => toggle('trading')}
				>
					<p className="text-xs sm:text-sm text-[var(--muted)]">
						Setting up Kotak for live trading? See the{' '}
						<Link to="/help/connect-broker" className="text-[var(--accent)] hover:underline">
							Help — Connect your broker
						</Link>{' '}
						guide.
					</p>

					{/* Mode selector */}
					<div>
						<p className="text-xs sm:text-sm font-medium mb-2">Trading mode</p>
						<div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
							<label className="flex items-center gap-2 min-h-[40px] sm:min-h-0 cursor-pointer">
								<input
									type="radio"
									checked={form.trade_mode === 'paper'}
									onChange={() => setForm({ ...form, trade_mode: 'paper' })}
									className="w-4 h-4"
								/>
								<span className="text-sm">Paper Trade (default)</span>
							</label>
							<label className="flex items-center gap-2 min-h-[40px] sm:min-h-0 cursor-pointer">
								<input
									type="radio"
									checked={form.trade_mode === 'broker'}
									onChange={() => setForm({ ...form, trade_mode: 'broker' })}
									className="w-4 h-4"
								/>
								<span className="text-sm">Kotak Neo (live)</span>
							</label>
						</div>
					</div>

					{isBroker && (
						<div className="space-y-4 border-t border-[#1e293b] pt-4">
							{/* Broker name */}
							<div>
								<label className="block text-xs sm:text-sm mb-1">Broker identifier</label>
								<input
									className={inputCls}
									value={form.broker ?? ''}
									onChange={(e) => setForm({ ...form, broker: e.target.value })}
									placeholder="kotak-neo"
								/>
							</div>

							{/* Creds header */}
							<div className="flex items-center justify-between">
								<p className="text-xs sm:text-sm font-medium">API credentials</p>
								{credsInfo?.has_creds && (
									<button
										type="button"
										onClick={() => {
											setShowFullCreds(!showFullCreds);
											qc.invalidateQueries({ queryKey: ['brokerCredsInfo'] });
										}}
										className="text-xs text-blue-400 hover:text-blue-300 underline min-h-[36px] sm:min-h-0"
									>
										{showFullCreds ? 'Hide' : 'Show'} full credentials
									</button>
								)}
							</div>

							{credsInfo?.has_creds && (
								<div className="text-xs text-emerald-400">
									✓ Credentials stored{' '}
									{showFullCreds ? '(showing full values)' : '— click Show to view / edit'}
								</div>
							)}

							<div>
								<label className="block text-xs sm:text-sm mb-1">App Token (API Key)</label>
								<input
									className={inputCls}
									value={apiKey}
									onChange={(e) => setApiKey(e.target.value)}
									placeholder={
										credsInfo?.has_creds && !showFullCreds
											? `Stored: ${credsInfo.api_key_masked}`
											: 'Enter App Token'
									}
								/>
								{credsInfo?.has_creds && !showFullCreds && (
									<div className="text-xs text-[var(--muted)] mt-1">
										Current: {credsInfo.api_key_masked}
									</div>
								)}
							</div>

							<div>
								<label className="block text-xs sm:text-sm mb-1">Client ID (UCC)</label>
								<PasswordInput
									className={inputCls}
									value={apiSecret}
									onChange={(e) => setApiSecret(e.target.value)}
									placeholder={
										credsInfo?.has_creds && !showFullCreds
											? `Stored: ${credsInfo.api_secret_masked}`
											: 'Enter Client ID (UCC)'
									}
									autoComplete="off"
								/>
								{credsInfo?.has_creds && !showFullCreds && (
									<div className="text-xs text-[var(--muted)] mt-1">
										Current: {credsInfo.api_secret_masked}
									</div>
								)}
							</div>

							{/* REST login credentials */}
							<div className="rounded-lg border border-[#1e293b] p-3 sm:p-4 space-y-3">
								<p className="text-xs sm:text-sm font-medium">Required for REST login</p>
								{credsInfo?.has_creds && !showFullCreds && (
									<p className="text-xs text-[var(--muted)]">
										Stored credentials available — click &quot;Show full credentials&quot; above to
										view / edit.
									</p>
								)}
								<div>
									<label className="block text-xs sm:text-sm mb-1">Mobile Number</label>
									<input
										className={inputCls}
										type="tel"
										value={mobileNumber}
										onChange={(e) => setMobileNumber(e.target.value)}
										placeholder={
											credsInfo?.has_creds && !showFullCreds
												? 'Stored (click Show to view)'
												: 'Enter mobile number'
										}
										disabled={!!(credsInfo?.has_creds && !showFullCreds)}
									/>
								</div>
								<div>
									<label className="block text-xs sm:text-sm mb-1">MPIN (for 2FA)</label>
									<PasswordInput
										className={inputCls}
										value={mpin}
										onChange={(e) => setMpin(e.target.value)}
										placeholder={
											credsInfo?.has_creds && !showFullCreds
												? 'Stored (click Show to view)'
												: 'Enter MPIN'
										}
										disabled={!!(credsInfo?.has_creds && !showFullCreds)}
										autoComplete="off"
									/>
								</div>
								<div>
									<label className="block text-xs sm:text-sm mb-1">TOTP Secret</label>
									<PasswordInput
										className={inputCls}
										value={totpSecret}
										onChange={(e) => setTotpSecret(e.target.value)}
										placeholder={
											credsInfo?.has_creds && !showFullCreds
												? 'Stored (click Show to view)'
												: 'Enter TOTP Secret'
										}
										disabled={!!(credsInfo?.has_creds && !showFullCreds)}
										autoComplete="off"
									/>
								</div>
								<div>
									<label className="block text-xs sm:text-sm mb-1">Environment</label>
									<input
										className={inputCls}
										value={environment}
										onChange={(e) => setEnvironment(e.target.value)}
										placeholder="prod"
										disabled={!!(credsInfo?.has_creds && !showFullCreds)}
									/>
								</div>
							</div>

							{/* Test mode */}
							<div>
								<p className="text-xs sm:text-sm font-medium mb-2">Connection test mode</p>
								<div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-3">
									<label className="flex items-center gap-2 min-h-[40px] sm:min-h-0 cursor-pointer">
										<input
											type="radio"
											checked={testMode === 'basic'}
											onChange={() => setTestMode('basic')}
											className="w-4 h-4"
										/>
										<span className="text-xs sm:text-sm">Basic (API Key / Secret only)</span>
									</label>
									<label className="flex items-center gap-2 min-h-[40px] sm:min-h-0 cursor-pointer">
										<input
											type="radio"
											checked={testMode === 'full'}
											onChange={() => setTestMode('full')}
											className="w-4 h-4"
										/>
										<span className="text-xs sm:text-sm">Full (REST login + MPIN validate)</span>
									</label>
								</div>
							</div>

							{/* Actions */}
							<div className="flex flex-col sm:flex-row gap-2">
								<button
									className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded disabled:opacity-50 min-h-[40px] text-sm font-medium transition-colors"
									onClick={async () => {
										setBrokerMsg(null);
										if (!apiKey || !apiSecret || !mobileNumber || !mpin || !totpSecret) {
											setBrokerMsg(
												'Please enter App Token, Client ID (UCC), Mobile Number, MPIN, and TOTP Secret',
											);
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
										setBrokerMsg('Credentials saved.');
										qc.invalidateQueries({ queryKey: ['brokerCredsInfo'] });
										setShowFullCreds(true);
									}}
									disabled={!apiKey || !apiSecret}
								>
									{credsInfo?.has_creds ? 'Update credentials' : 'Save credentials'}
								</button>

								<button
									className="bg-emerald-700 hover:bg-emerald-600 text-white px-4 py-2 rounded disabled:opacity-50 min-h-[40px] text-sm font-medium transition-colors"
									onClick={async () => {
										setTesting(true);
										setBrokerMsg(null);
										try {
											let fullCredsInfo = credsInfo;
											if (testMode === 'full' && credsInfo?.has_creds && !showFullCreds) {
												fullCredsInfo = await getBrokerCredsInfo(true);
											}
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
											setBrokerMsg(
												res.message ?? (res.ok ? 'Connection successful!' : 'Connection failed'),
											);
											const s = await getBrokerStatus().catch(() => null);
											if (s) setStatus(s);
										} catch (error: unknown) {
											setBrokerMsg(error instanceof Error ? error.message : 'Test failed');
										} finally {
											setTesting(false);
										}
									}}
									disabled={
										testing ||
										(!apiKey && !credsInfo?.has_creds) ||
										(!apiSecret && !credsInfo?.has_creds) ||
										(testMode === 'full' &&
											((!mobileNumber && !credsInfo?.has_creds) ||
												(!mpin && !credsInfo?.has_creds) ||
												(!totpSecret && !credsInfo?.has_creds)))
									}
								>
									{testing
										? 'Testing…'
										: testMode === 'full'
											? 'Test full connection'
											: 'Test basic connection'}
								</button>
							</div>

							{testMode === 'full' && credsInfo?.has_creds && !showFullCreds && (
								<p className="text-xs text-[var(--muted)]">
									Note: will use stored credentials if fields are empty.
								</p>
							)}

							{brokerMsg && (
								<div
									className={`text-xs sm:text-sm ${brokerMsg.includes('successful') || brokerMsg.includes('OK') || brokerMsg.includes('saved') ? 'text-emerald-400' : 'text-red-400'}`}
								>
									{brokerMsg}
								</div>
							)}
							{status && (
								<div className="text-xs text-[var(--muted)]">Status: {status.status ?? 'Unknown'}</div>
							)}
						</div>
					)}

					{/* Save trading mode button (always visible in section) */}
					<div className="pt-2 border-t border-[#1e293b]">
						<button
							onClick={() =>
								mutation.mutate({ trade_mode: form.trade_mode, broker: form.broker ?? undefined })
							}
							className="bg-[var(--accent)] text-black px-4 py-2 rounded text-sm min-h-[40px] disabled:opacity-60 font-medium"
							disabled={mutation.isPending}
						>
							{mutation.isPending ? 'Saving…' : 'Save trading settings'}
						</button>
					</div>
				</SectionCard>
			</div>
		</div>
	);
}
