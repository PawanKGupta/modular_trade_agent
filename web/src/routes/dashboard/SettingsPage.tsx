import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSettings, updateSettings, type Settings, saveBrokerCreds, testBrokerConnection, getBrokerStatus, getBrokerCredsInfo } from '@/api/user';
import { useState, useEffect } from 'react';

export function SettingsPage() {
	const qc = useQueryClient();
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
	const [password, setPassword] = useState('');
	const [mpin, setMpin] = useState('');
	const [testMode, setTestMode] = useState<'basic' | 'full'>('basic');
	const [brokerMsg, setBrokerMsg] = useState<string | null>(null);
	const [testing, setTesting] = useState(false);
	const [status, setStatus] = useState<{ broker: string | null; status: string | null } | null>(null);

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
			if (credsInfo.password) setPassword(credsInfo.password);
			if (credsInfo.mpin) setMpin(credsInfo.mpin);
		} else if (credsInfo?.has_creds && !showFullCreds) {
			// Clear fields when hiding
			setApiKey('');
			setApiSecret('');
			setMobileNumber('');
			setPassword('');
			setMpin('');
		}
	}, [credsInfo, showFullCreds]);

	useEffect(() => {
		if (data) setForm(data);
	}, [data]);

	if (isLoading) return <div>Loading settings...</div>;

	const isBroker = form.trade_mode === 'broker';

	return (
		<div className="max-w-xl">
			<h2 className="text-lg font-semibold mb-4">Trading mode</h2>
			<div className="flex items-center gap-4 mb-6">
				<label className="flex items-center gap-2">
					<input type="radio" checked={form.trade_mode === 'paper'} onChange={() => setForm({ ...form, trade_mode: 'paper' })} />
					<span>Paper Trade (default)</span>
				</label>
				<label className="flex items-center gap-2">
					<input type="radio" checked={form.trade_mode === 'broker'} onChange={() => setForm({ ...form, trade_mode: 'broker' })} />
					<span>Kotak Neo</span>
				</label>
			</div>
			{isBroker && (
				<div className="space-y-3 mb-6">
					<div>
						<label className="block text-sm mb-1">Broker</label>
						<input className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]" value={form.broker ?? ''} onChange={(e) => setForm({ ...form, broker: e.target.value })} placeholder="kotak-neo" />
					</div>
					<div className="space-y-3">
						<div className="flex items-center justify-between mt-4">
							<h3 className="text-sm font-semibold">Basic Credentials</h3>
							{credsInfo?.has_creds && (
								<button
									type="button"
									onClick={() => {
										setShowFullCreds(!showFullCreds);
										qc.invalidateQueries({ queryKey: ['brokerCredsInfo'] });
									}}
									className="text-xs text-blue-400 hover:text-blue-300 underline"
								>
									{showFullCreds ? 'Hide' : 'Show'} Full Credentials
								</button>
							)}
						</div>
						{credsInfo?.has_creds && (
							<div className="text-sm text-green-400 mb-2">
								✓ Credentials stored {showFullCreds ? '(showing full values)' : '(click Show to view/edit)'}
							</div>
						)}
						<div>
							<label className="block text-sm mb-1">API Key (Consumer Key)</label>
							<input
								className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
								value={apiKey}
								onChange={(e) => setApiKey(e.target.value)}
								placeholder={credsInfo?.has_creds && !showFullCreds ? `Stored: ${credsInfo.api_key_masked}` : "Enter API Key"}
							/>
							{credsInfo?.has_creds && !showFullCreds && (
								<div className="text-xs text-[var(--muted)] mt-1">
									Current: {credsInfo.api_key_masked} (click Show to view/edit)
								</div>
							)}
						</div>
						<div>
							<label className="block text-sm mb-1">API Secret (Consumer Secret)</label>
							<input
								className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
								type="password"
								value={apiSecret}
								onChange={(e) => setApiSecret(e.target.value)}
								placeholder={credsInfo?.has_creds && !showFullCreds ? `Stored: ${credsInfo.api_secret_masked}` : "Enter API Secret"}
							/>
							{credsInfo?.has_creds && !showFullCreds && (
								<div className="text-xs text-[var(--muted)] mt-1">
									Current: {credsInfo.api_secret_masked} (click Show to view/edit)
								</div>
							)}
						</div>

						<div className="mt-4">
							<label className="block text-sm font-semibold mb-2">Connection Test Mode</label>
							<div className="flex items-center gap-4 mb-3">
								<label className="flex items-center gap-2">
									<input type="radio" checked={testMode === 'basic'} onChange={() => setTestMode('basic')} />
									<span className="text-sm">Basic Test (API Key/Secret only)</span>
								</label>
								<label className="flex items-center gap-2">
									<input type="radio" checked={testMode === 'full'} onChange={() => setTestMode('full')} />
									<span className="text-sm">Full Test (with Login & 2FA)</span>
								</label>
							</div>
						</div>

						<div className="space-y-3 mt-4 p-4 border border-[#1e293b] rounded">
							<h4 className="text-sm font-semibold">Full Authentication Credentials</h4>
							{credsInfo?.has_creds && !showFullCreds && (
								<div className="text-xs text-[var(--muted)] mb-2">
									Stored credentials available. Click "Show Full Credentials" above to view/edit.
								</div>
							)}
							<div>
								<label className="block text-sm mb-1">Mobile Number</label>
								<input
									className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
									type="tel"
									value={mobileNumber}
									onChange={(e) => setMobileNumber(e.target.value)}
									placeholder={credsInfo?.has_creds && !showFullCreds ? "Stored (click Show to view)" : "Enter mobile number"}
									disabled={credsInfo?.has_creds && !showFullCreds}
								/>
							</div>
							<div>
								<label className="block text-sm mb-1">Password</label>
								<input
									className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
									type="password"
									value={password}
									onChange={(e) => setPassword(e.target.value)}
									placeholder={credsInfo?.has_creds && !showFullCreds ? "Stored (click Show to view)" : "Enter password"}
									disabled={credsInfo?.has_creds && !showFullCreds}
								/>
							</div>
							<div>
								<label className="block text-sm mb-1">MPIN (for 2FA)</label>
								<input
									className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
									type="password"
									value={mpin}
									onChange={(e) => setMpin(e.target.value)}
									placeholder={credsInfo?.has_creds && !showFullCreds ? "Stored (click Show to view)" : "Enter MPIN"}
									disabled={credsInfo?.has_creds && !showFullCreds}
								/>
							</div>
						</div>

						<div className="flex gap-2 mt-4">
							<button
								className="bg-blue-600 text-white px-3 py-2 rounded disabled:opacity-50"
								onClick={async () => {
									setBrokerMsg(null);
									if (!apiKey || !apiSecret) {
										setBrokerMsg('Please enter API Key and Secret');
										return;
									}

									await saveBrokerCreds({
										broker: form.broker ?? 'kotak-neo',
										api_key: apiKey,
										api_secret: apiSecret,
										mobile_number: mobileNumber || undefined,
										password: password || undefined,
										mpin: mpin || undefined,
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
								className="bg-emerald-600 text-white px-3 py-2 rounded disabled:opacity-50"
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
										const payload: any = {
											broker: form.broker ?? 'kotak-neo',
											api_key: apiKey || fullCredsInfo?.api_key || '',
											api_secret: apiSecret || fullCredsInfo?.api_secret || '',
										};

										if (testMode === 'full') {
											payload.mobile_number = mobileNumber || fullCredsInfo?.mobile_number || '';
											payload.password = password || fullCredsInfo?.password || '';
											payload.mpin = mpin || fullCredsInfo?.mpin || '';
										}

										const res = await testBrokerConnection(payload);
										setBrokerMsg(res.message ?? (res.ok ? 'Connection successful!' : 'Connection failed'));
										const s = await getBrokerStatus().catch(() => null);
										if (s) setStatus(s);
									} catch (error: any) {
										setBrokerMsg(error?.message || 'Test failed');
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
										!mobileNumber &&
										!password &&
										!mpin &&
										!credsInfo?.has_creds)
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
							<div className={`text-sm mt-2 ${brokerMsg.includes('successful') || brokerMsg.includes('OK') ? 'text-green-400' : 'text-red-400'}`}>
								{brokerMsg}
							</div>
						)}
						{status && <div className="text-sm text-[var(--muted)] mt-2">Status: {status.status ?? 'Unknown'}</div>}
					</div>
				</div>
			)}
			<button
				onClick={() => mutation.mutate({ trade_mode: form.trade_mode, broker: form.broker ?? undefined })}
				className="bg-[var(--accent)] text-black px-4 py-2 rounded"
				disabled={mutation.isPending}
			>
				{mutation.isPending ? 'Saving...' : 'Save settings'}
			</button>
		</div>
	);
}
