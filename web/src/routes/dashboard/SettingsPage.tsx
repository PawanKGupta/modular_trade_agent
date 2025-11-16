import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSettings, updateSettings, type Settings, saveBrokerCreds, testBrokerConnection, getBrokerStatus } from '@/api/user';
import { useState, useEffect } from 'react';

export function SettingsPage() {
	const qc = useQueryClient();
	const { data, isLoading } = useQuery<Settings>({ queryKey: ['settings'], queryFn: getSettings });
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
						<h3 className="text-sm font-semibold mt-4">Basic Credentials</h3>
						<div>
							<label className="block text-sm mb-1">API Key (Consumer Key)</label>
							<input className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="Enter API Key" />
						</div>
						<div>
							<label className="block text-sm mb-1">API Secret (Consumer Secret)</label>
							<input className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]" type="password" value={apiSecret} onChange={(e) => setApiSecret(e.target.value)} placeholder="Enter API Secret" />
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

						{testMode === 'full' && (
							<div className="space-y-3 mt-4 p-4 border border-[#1e293b] rounded">
								<h4 className="text-sm font-semibold">Full Authentication Credentials</h4>
								<div>
									<label className="block text-sm mb-1">Mobile Number</label>
									<input className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]" type="tel" value={mobileNumber} onChange={(e) => setMobileNumber(e.target.value)} placeholder="Enter mobile number" />
								</div>
								<div>
									<label className="block text-sm mb-1">Password</label>
									<input className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Enter password" />
								</div>
								<div>
									<label className="block text-sm mb-1">MPIN (for 2FA)</label>
									<input className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]" type="password" value={mpin} onChange={(e) => setMpin(e.target.value)} placeholder="Enter MPIN" />
								</div>
							</div>
						)}

						<div className="flex gap-2 mt-4">
							<button
								className="bg-blue-600 text-white px-3 py-2 rounded disabled:opacity-50"
								onClick={async () => {
									setBrokerMsg(null);
									await saveBrokerCreds(form.broker ?? 'kotak-neo', apiKey, apiSecret);
									setBrokerMsg('Credentials saved');
								}}
								disabled={!apiKey || !apiSecret}
							>
								Save Credentials
							</button>
							<button
								className="bg-emerald-600 text-white px-3 py-2 rounded disabled:opacity-50"
								onClick={async () => {
									setTesting(true);
									setBrokerMsg(null);
									try {
										const payload: any = {
											broker: form.broker ?? 'kotak-neo',
											api_key: apiKey,
											api_secret: apiSecret,
										};
										if (testMode === 'full') {
											payload.mobile_number = mobileNumber;
											payload.password = password;
											payload.mpin = mpin;
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
									!apiKey ||
									!apiSecret ||
									testing ||
									(testMode === 'full' && (!mobileNumber || !password || !mpin))
								}
							>
								{testing ? 'Testing...' : testMode === 'full' ? 'Test Full Connection' : 'Test Basic Connection'}
							</button>
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
