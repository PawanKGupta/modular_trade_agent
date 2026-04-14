import { http, HttpResponse } from 'msw';

const API = (path: string) => `http://localhost:8000/api/v1${path}`;

let mlJobIdCounter = 2;
let mlModelIdCounter = 2;

const mlTrainingJobs = [
	{
		id: 1,
		started_by: 1,
		status: 'completed',
		model_type: 'verdict_classifier',
		algorithm: 'xgboost',
		training_data_path: 'data/training/verdict_classifier.csv',
		started_at: new Date(Date.now() - 60_000).toISOString(),
		completed_at: new Date(Date.now() - 30_000).toISOString(),
		model_path: 'models/verdict_classifier/xgboost-v1.json',
		accuracy: 0.82,
		error_message: null,
		logs: 'Training completed with accuracy 0.82',
	},
];

const mlModels = [
	{
		id: 1,
		model_type: 'verdict_classifier',
		version: 'v1',
		model_path: 'models/verdict_classifier/xgboost-v1.json',
		accuracy: 0.82,
		training_job_id: 1,
		is_active: true,
		created_at: new Date(Date.now() - 30_000).toISOString(),
		created_by: 1,
	},
];

const loggedInUserId = 1;

type ServiceLogMock = {
	id: number;
	user_id: number;
	level: string;
	module: string;
	message: string;
	context: Record<string, unknown> | null;
	timestamp: string;
};

type ErrorLogMock = {
	id: number;
	user_id: number;
	error_type: string;
	error_message: string;
	traceback: string | null;
	context: Record<string, unknown> | null;
	resolved: boolean;
	resolved_at: string | null;
	resolved_by: number | null;
	resolution_notes: string | null;
	occurred_at: string;
};

const serviceLogs: ServiceLogMock[] = [
	{
		id: 1,
		user_id: 1,
		level: 'INFO',
		module: 'scheduler.analysis',
		message: 'Analysis task finished successfully',
		context: { task: 'analysis', duration: '32s' },
		timestamp: new Date(Date.now() - 60_000).toISOString(),
	},
	{
		id: 2,
		user_id: 2,
		level: 'ERROR',
		module: 'scheduler.sell',
		message: 'Sell task failed: insufficient funds',
		context: { task: 'sell' },
		timestamp: new Date(Date.now() - 90_000).toISOString(),
	},
];

const errorLogs: ErrorLogMock[] = [
	{
		id: 1,
		user_id: 1,
		error_type: 'ValueError',
		error_message: 'Unable to parse symbol',
		traceback: 'ValueError: Unable to parse symbol\n    at analysis.py:123',
		context: { symbol: '????' },
		resolved: false,
		resolved_at: null,
		resolved_by: null,
		resolution_notes: null,
		occurred_at: new Date(Date.now() - 120_000).toISOString(),
	},
	{
		id: 2,
		user_id: 2,
		error_type: 'RuntimeError',
		error_message: 'Websocket disconnected',
		traceback: 'RuntimeError: Connection lost\n    at live_price.py:87',
		context: { connection: 'WebSocket' },
		resolved: true,
		resolved_at: new Date(Date.now() - 60_000).toISOString(),
		resolved_by: 1,
		resolution_notes: 'Restarted WS client',
		occurred_at: new Date(Date.now() - 5 * 60_000).toISOString(),
	},
];

// Simple in-memory filter preset store keyed by page
const filterPresets: Record<string, Record<string, Record<string, unknown>>> = {
	signals: {
		'Default Signals': {
			status_filter: 'active',
			limit: 100,
		},
	},
};

const filterServiceLogs = (logs: ServiceLogMock[], url: URL) => {
	const level = url.searchParams.get('level');
	const module = url.searchParams.get('module');
	const search = url.searchParams.get('search')?.toLowerCase();
	const start = url.searchParams.get('start_time');
	const end = url.searchParams.get('end_time');
	const limit = Number(url.searchParams.get('limit') ?? '200');

	let filtered = [...logs];
	if (level) {
		filtered = filtered.filter((log) => log.level === level);
	}
	if (module) {
		filtered = filtered.filter((log) => log.module.includes(module));
	}
	if (search) {
		filtered = filtered.filter(
			(log) =>
				log.message.toLowerCase().includes(search) ||
				log.module.toLowerCase().includes(search)
		);
	}
	if (start) {
		const startTs = Date.parse(start);
		filtered = filtered.filter((log) => Date.parse(log.timestamp) >= startTs);
	}
	if (end) {
		const endTs = Date.parse(end);
		filtered = filtered.filter((log) => Date.parse(log.timestamp) <= endTs);
	}
	return filtered.slice(0, Number.isNaN(limit) ? filtered.length : limit);
};

const filterErrorLogs = (logs: ErrorLogMock[], url: URL) => {
	const resolvedParam = url.searchParams.get('resolved');
	const search = url.searchParams.get('search')?.toLowerCase();
	const start = url.searchParams.get('start_time');
	const end = url.searchParams.get('end_time');
	const limit = Number(url.searchParams.get('limit') ?? '100');

	let filtered = [...logs];
	if (resolvedParam === 'true') {
		filtered = filtered.filter((log) => log.resolved);
	} else if (resolvedParam === 'false') {
		filtered = filtered.filter((log) => !log.resolved);
	}
	if (search) {
		filtered = filtered.filter((log) =>
			log.error_message.toLowerCase().includes(search)
		);
	}
	if (start) {
		const startTs = Date.parse(start);
		filtered = filtered.filter((log) => Date.parse(log.occurred_at) >= startTs);
	}
	if (end) {
		const endTs = Date.parse(end);
		filtered = filtered.filter((log) => Date.parse(log.occurred_at) <= endTs);
	}
	return filtered.slice(0, Number.isNaN(limit) ? filtered.length : limit);
};

export const handlers = [
	// auth
http.post(API('/auth/login'), async () => {
		return HttpResponse.json({
			access_token: 'test-token',
			refresh_token: 'refresh-token',
			token_type: 'bearer',
		});
	}),
http.post(API('/auth/signup'), async () => {
		return HttpResponse.json({
			access_token: 'test-token',
			refresh_token: 'refresh-token',
			token_type: 'bearer',
		});
	}),
http.post(API('/auth/refresh'), async () => {
		return HttpResponse.json({
			access_token: 'test-token-2',
			refresh_token: 'refresh-token-2',
			token_type: 'bearer',
		});
	}),
	http.get(API('/auth/me'), async () => {
		return HttpResponse.json({ id: 1, email: 'test@example.com', roles: ['admin'] });
	}),
	// settings
	http.get(API('/user/settings'), async () => {
		return HttpResponse.json({ trade_mode: 'paper', broker: null, broker_status: null });
	}),
	http.put(API('/user/settings'), async ({ request }) => {
		const body = (await request.json()) as Partial<{ trade_mode: string; broker: string | null }>;
		return HttpResponse.json({ trade_mode: body.trade_mode ?? 'paper', broker: body.broker ?? null, broker_status: null });
	}),
	// broker
	http.post(API('/user/broker/creds'), async () => {
		return HttpResponse.json({ status: 'ok' });
	}),
	http.post(API('/user/broker/test'), async ({ request }) => {
		const body = (await request.json()) as { api_key?: string; api_secret?: string; mobile_number?: string; mpin?: string; totp_secret?: string };
		if (!body.api_key || !body.api_secret) {
			return HttpResponse.json({ ok: false, message: 'API key and secret are required' }, { status: 400 });
		}
		// Basic test (only api_key/api_secret)
		if (!body.mobile_number || !body.mpin || !body.totp_secret) {
			return HttpResponse.json({
				ok: true,
				message: 'Client initialized successfully (full login test requires mobile, MPIN, and TOTP secret)'
			});
		}
		// Full test (with login credentials)
		// Mock: accept any non-empty values for testing
		if (body.mobile_number && body.mpin && body.totp_secret) {
			return HttpResponse.json({ ok: true, message: 'Connection successful' });
		}
		return HttpResponse.json({ ok: false, message: 'Invalid credentials' }, { status: 400 });
	}),
	http.get(API('/user/broker/status'), async () => {
		return HttpResponse.json({ broker: 'kotak-neo', status: 'Connected' });
	}),
	http.get(API('/user/broker/creds/info'), async ({ request }) => {
		const url = new URL(request.url);
		const showFull = url.searchParams.get('show_full') === 'true';
		if (showFull) {
			return HttpResponse.json({
				has_creds: true,
				api_key: 'test-api-key-1234',
				api_secret: 'test-api-secret-5678',
				mobile_number: '9876543210',
				mpin: '1234',
				totp_secret: 'BASE32SECRET3232',
				environment: 'prod'
			});
		}
		return HttpResponse.json({ has_creds: true, api_key_masked: '****1234', api_secret_masked: '****5678' });
	}),
	// portfolio
	http.get(API('/user/portfolio'), async () => {
		return HttpResponse.json({
			account: {
				initial_capital: 1000000,
				available_cash: 500000,
				total_pnl: 50000,
				realized_pnl: 30000,
				unrealized_pnl: 20000,
				portfolio_value: 550000,
				total_value: 1050000,
				return_percentage: 5.0,
			},
			holdings: [
				{
					symbol: 'RELIANCE.NS',
					quantity: 10,
					average_price: 2500,
					current_price: 2600,
					cost_basis: 25000,
					market_value: 26000,
					pnl: 1000,
					pnl_percentage: 4.0,
					target_price: 2700,
					distance_to_target: 3.7,
				},
				{
					symbol: 'TCS.NS',
					quantity: 5,
					average_price: 3500,
					current_price: 3400,
					cost_basis: 17500,
					market_value: 17000,
					pnl: -500,
					pnl_percentage: -2.86,
					target_price: 3600,
					distance_to_target: 5.6,
				},
			],
			recent_orders: [],
			order_statistics: {
				total_orders: 10,
				buy_orders: 6,
				sell_orders: 4,
				completed_orders: 8,
				pending_orders: 2,
				cancelled_orders: 0,
				rejected_orders: 0,
				success_rate: 80,
				reentry_orders: 2,
			},
		});
	}),
	http.options(API('/user/portfolio'), async () => HttpResponse.json({ ok: true })),
	// portfolio snapshot
	http.post(API('/user/portfolio/snapshot'), async () => {
		return HttpResponse.json({ message: 'Portfolio snapshot created successfully' });
	}),
	http.options(API('/user/portfolio/snapshot'), async () => HttpResponse.json({ ok: true })),
	// orders (paginated)
	...([API('/user/orders'), API('/user/orders/')].map((url) =>
		http.get(url, async ({ request }) => {
			const reqUrl = new URL(request.url);
			const status = reqUrl.searchParams.get('status') ?? 'pending';
			const page = Number(reqUrl.searchParams.get('page') ?? '1');
			const pageSize = Number(reqUrl.searchParams.get('page_size') ?? '50');
			const now = new Date().toISOString();

			const byStatus: Record<string, unknown[]> = {
				pending: [
					{ id: 101, symbol: 'INFY', side: 'buy', quantity: 10, price: 1500, status: 'pending', reason: 'Order placed - waiting for market open', created_at: now, updated_at: now },
					{ id: 250, symbol: 'SUNPHARMA', side: 'buy', quantity: 12, price: 1280, status: 'pending', reason: 'Order placed - waiting for market open', created_at: now, updated_at: now },
				],
				ongoing: [
					{ id: 201, symbol: 'RELIANCE', side: 'buy', quantity: 5, price: 2400, status: 'ongoing', reason: 'Order executed at Rs 2400.00', created_at: now, updated_at: now },
				],
				failed: [
					{ id: 301, symbol: 'TCS', side: 'buy', quantity: 3, price: 3600, status: 'failed', reason: 'Insufficient balance', retry_count: 1, first_failed_at: now, last_retry_attempt: now, created_at: now, updated_at: now },
				],
				closed: [
					{ id: 401, symbol: 'HDFCBANK', side: 'buy', quantity: 2, price: 1500, status: 'closed', reason: 'Order completed', created_at: now, updated_at: now },
				],
				cancelled: [
					{ id: 501, symbol: 'WIPRO', side: 'buy', quantity: 8, price: 450, status: 'cancelled', reason: 'Order cancelled', created_at: now, updated_at: now },
				],
			};

			const itemsAll = byStatus[status] ?? [];
			const start = (page - 1) * pageSize;
			const items = itemsAll.slice(start, start + pageSize);
			const total = itemsAll.length;
			const total_pages = Math.max(1, Math.ceil(total / pageSize));

			return HttpResponse.json({
				items,
				total,
				page,
				page_size: pageSize,
				total_pages,
			});
		})
	)),
	// pnl
	http.get(API('/user/pnl/daily'), async () => {
		return HttpResponse.json([
			{ date: '2025-11-10', pnl: 120.5 },
			{ date: '2025-11-11', pnl: -40.0 },
			{ date: '2025-11-12', pnl: 75.25 },
		]);
	}),
	http.get(API('/user/pnl/summary'), async () => {
		return HttpResponse.json({ totalPnl: 155.75, daysGreen: 2, daysRed: 1 });
	}),
	// service
	http.get(API('/user/service/status'), async () => {
		return HttpResponse.json({
			service_running: true,
			last_heartbeat: new Date().toISOString(),
			last_task_execution: new Date(Date.now() - 60000).toISOString(),
			error_count: 0,
			last_error: null,
			updated_at: new Date().toISOString(),
		});
	}),
	http.post(API('/user/service/start'), async () => {
		return HttpResponse.json({
			success: true,
			message: 'Trading service started successfully',
			service_running: true,
		});
	}),
	http.post(API('/user/service/stop'), async () => {
		return HttpResponse.json({
			success: true,
			message: 'Trading service stopped successfully',
			service_running: false,
		});
	}),
	// service metrics
	http.get(API('/user/service/metrics/position-creation'), async () => {
		return HttpResponse.json({
			success: 10,
			failed_missing_repos: 0,
			failed_missing_symbol: 0,
			failed_exception: 0,
			success_rate: 100.0,
			total_attempts: 10,
		});
	}),
	http.options(API('/user/service/metrics/position-creation'), async () => HttpResponse.json({ ok: true })),
	// positions without sell orders
	http.get(API('/user/service/positions-without-sell'), async () => {
		return HttpResponse.json({
			positions: [],
			count: 0,
		});
	}),
	http.options(API('/user/service/positions-without-sell'), async () => HttpResponse.json({ ok: true })),
	// individual service status
	http.get(API('/user/service/individual/status'), async () => {
		return HttpResponse.json({
			analysis_service: { running: true, last_check: new Date().toISOString() },
			scheduler_service: { running: true, last_check: new Date().toISOString() },
			broker_service: { running: false, last_check: new Date().toISOString() },
		});
	}),
	http.options(API('/user/service/individual/status'), async () => HttpResponse.json({ ok: true })),
	// trading day info
	http.get(API('/trading-day'), async () => {
		return HttpResponse.json({
			is_trading_day: true,
			is_holiday: false,
			holiday_name: null,
			is_weekend: false,
		});
	}),
	http.options(API('/trading-day'), async () => HttpResponse.json({ ok: true })),
	http.get(API('/user/service/tasks'), async ({ request }) => {
		const url = new URL(request.url);
		const taskName = url.searchParams.get('task_name');
		const status = url.searchParams.get('status');
		const now = new Date().toISOString();
		const tasks = [
			{
				id: 1,
				task_name: 'premarket_retry',
				executed_at: now,
				status: 'success',
				duration_seconds: 1.5,
				details: { symbols_processed: 5 },
			},
			{
				id: 2,
				task_name: 'analysis',
				executed_at: new Date(Date.now() - 300000).toISOString(),
				status: 'success',
				duration_seconds: 2.3,
				details: null,
			},
			{
				id: 3,
				task_name: 'buy_orders',
				executed_at: new Date(Date.now() - 600000).toISOString(),
				status: 'failed',
				duration_seconds: 0.5,
				details: { error: 'Network timeout' },
			},
		];
		let filtered = tasks;
		if (taskName) {
			filtered = filtered.filter((t) => t.task_name === taskName);
		}
		if (status) {
			filtered = filtered.filter((t) => t.status === status);
		}
		return HttpResponse.json({ tasks: filtered, total: filtered.length });
	}),
	http.get(API('/user/service/logs'), async ({ request }) => {
		const url = new URL(request.url);
		const level = url.searchParams.get('level');
		const module = url.searchParams.get('module');
		const now = new Date().toISOString();
		const logs = [
			{
				id: 1,
				level: 'INFO',
				module: 'TradingService',
				message: 'Service started successfully',
				context: { action: 'start_service' },
				timestamp: now,
			},
			{
				id: 2,
				level: 'ERROR',
				module: 'TradingService',
				message: 'Failed to place order',
				context: { symbol: 'RELIANCE', error: 'Insufficient funds' },
				timestamp: new Date(Date.now() - 300000).toISOString(),
			},
			{
				id: 3,
				level: 'WARNING',
				module: 'AutoTradeEngine',
				message: 'Low volume detected',
				context: { symbol: 'TCS', volume: 1000 },
				timestamp: new Date(Date.now() - 600000).toISOString(),
			},
		];
		let filtered = logs;
		if (level) {
			filtered = filtered.filter((l) => l.level === level);
		}
		if (module) {
			filtered = filtered.filter((l) => l.module === module);
		}
		return HttpResponse.json({ logs: filtered, total: filtered.length, limit: 100 });
	}),
	http.get(API('/user/logs'), async ({ request }) => {
		const url = new URL(request.url);
		const filtered = serviceLogs.filter((log) => log.user_id === loggedInUserId);
		return HttpResponse.json({ logs: filterServiceLogs(filtered, url) });
	}),
	http.get(API('/user/logs/errors'), async ({ request }) => {
		const url = new URL(request.url);
		const filtered = errorLogs.filter((log) => log.user_id === loggedInUserId);
		return HttpResponse.json({ errors: filterErrorLogs(filtered, url) });
	}),
	http.get(API('/admin/logs'), async ({ request }) => {
		const url = new URL(request.url);
		const userId = url.searchParams.get('user_id');
		let logs = [...serviceLogs];
		if (userId) {
			logs = logs.filter((log) => log.user_id === Number(userId));
		}
		return HttpResponse.json({ logs: filterServiceLogs(logs, url) });
	}),
	http.get(API('/admin/logs/errors'), async ({ request }) => {
		const url = new URL(request.url);
		const userId = url.searchParams.get('user_id');
		let logs = [...errorLogs];
		if (userId) {
			logs = logs.filter((log) => log.user_id === Number(userId));
		}
		return HttpResponse.json({ errors: filterErrorLogs(logs, url) });
	}),
	http.post(API('/admin/logs/errors/:id/resolve'), async ({ params, request }) => {
		const errorId = Number(params.id);
		const payload = (await request.json()) as { notes?: string };
		const error = errorLogs.find((entry) => entry.id === errorId);
		if (!error) {
			return HttpResponse.json({ detail: 'Not found' }, { status: 404 });
		}
		error.resolved = true;
		error.resolved_at = new Date().toISOString();
		error.resolved_by = loggedInUserId;
		error.resolution_notes = payload?.notes ?? null;
		return HttpResponse.json({ message: 'Error marked as resolved', error });
	}),
	// activity
	http.get(API('/user/activity'), async ({ request }) => {
		const url = new URL(request.url);
		const level = url.searchParams.get('level') ?? 'all';
		const now = new Date().toISOString();
		const items = [
			{ id: 1, ts: now, event: 'Login', detail: 'User logged in', level: 'info' },
			{ id: 2, ts: now, event: 'Order Placed', detail: 'BUY INFY x10', level: 'info' },
			{ id: 3, ts: now, event: 'Warning', detail: 'API rate limit near', level: 'warn' },
			{ id: 4, ts: now, event: 'Error', detail: 'Broker connection failed', level: 'error' },
		];
		return HttpResponse.json(level === 'all' ? items : items.filter((i) => i.level === level));
	}),
	// targets
	http.get(API('/user/targets'), async () => {
		const now = new Date().toISOString();
		return HttpResponse.json([
			{ id: 1, symbol: 'TCS', target_price: 3850, note: 'EMA9 bounce target', created_at: now },
			{ id: 2, symbol: 'INFY', target_price: 1600, note: null, created_at: now },
		]);
	}),
	// admin users
	http.get(API('/admin/users'), async () => {
		return HttpResponse.json([
			{ id: 1, email: 'admin@example.com', name: 'Admin', role: 'admin', is_active: true, created_at: new Date().toISOString(), updated_at: new Date().toISOString() },
			{ id: 2, email: 'user@example.com', name: 'User', role: 'user', is_active: true, created_at: new Date().toISOString(), updated_at: new Date().toISOString() },
		]);
	}),
	http.post(API('/admin/users'), async ({ request }) => {
		const body = (await request.json()) as { email?: string; name?: string; role?: string; password?: string };
		return HttpResponse.json({ id: Math.floor(Math.random() * 10000), email: body.email, name: body.name ?? null, role: body.role ?? 'user', is_active: true, created_at: new Date().toISOString(), updated_at: new Date().toISOString() });
	}),
	http.put(API('/admin/users/:id'), async ({ params, request }) => {
		const body = (await request.json()) as { name?: string; role?: string; is_active?: boolean };
		return HttpResponse.json({ id: Number(params.id), email: 'updated@example.com', name: body.name ?? null, role: body.role ?? 'user', is_active: body.is_active ?? true, created_at: new Date().toISOString(), updated_at: new Date().toISOString() });
	}),
	http.patch(API('/admin/users/:id'), async ({ params, request }) => {
		const body = (await request.json()) as { name?: string; role?: string; is_active?: boolean };
		return HttpResponse.json({ id: Number(params.id), email: 'updated@example.com', name: body.name ?? null, role: body.role ?? 'user', is_active: body.is_active ?? true, created_at: new Date().toISOString(), updated_at: new Date().toISOString() });
	}),
	http.delete(API('/admin/users/:id'), async () => {
		return HttpResponse.json({ ok: true });
	}),
	// signals
	http.get(API('/signals/buying-zone'), async () => {
		return HttpResponse.json([
			{
				id: 1,
				symbol: 'TCS',
				status: 'active',
				rsi10: 25.2,
				ema9: 100,
				ema200: 90,
				distance_to_ema9: 5,
				clean_chart: true,
				monthly_support_dist: 1.2,
				confidence: 0.7,
				backtest_score: 75.5,
				combined_score: 80.0,
				strength_score: 65.0,
				priority_score: 70.0,
				ml_verdict: 'buy',
				ml_confidence: 0.85,
				ml_probabilities: { buy: 0.85, avoid: 0.15 },
				buy_range: { low: 95.0, high: 100.0 },
				target: 110.0,
				stop: 90.0,
				last_close: 98.5,
				pe: 25.5,
				pb: 3.2,
				fundamental_assessment: 'good',
				fundamental_ok: true,
				avg_vol: 1000000,
				today_vol: 1200000,
				vol_ok: true,
				volume_ratio: 1.2,
				verdict: 'buy',
				signals: ['rsi_oversold', 'ema_dip'],
				justification: ['RSI below 30', 'Price near EMA9'],
				ts: new Date().toISOString(),
			},
			{
				id: 2,
				symbol: 'INFY',
				status: 'active',
				rsi10: 28.5,
				ema9: 1500,
				ema200: 1450,
				distance_to_ema9: -2.5,
				clean_chart: false,
				monthly_support_dist: 0.8,
				confidence: 0.6,
				backtest_score: 60.0,
				combined_score: 65.0,
				ml_verdict: 'avoid',
				ml_confidence: 0.55,
				last_close: 1495.0,
				verdict: 'avoid',
				ts: new Date().toISOString(),
			},
		]);
	}),
	http.patch(API('/signals/signals/:symbol/reject'), async ({ params }) => {
		return HttpResponse.json({
			message: `Signal for ${params.symbol} marked as REJECTED`,
			symbol: params.symbol,
			status: 'rejected',
		});
	}),
	http.patch(API('/signals/signals/:symbol/activate'), async ({ params }) => {
		return HttpResponse.json({
			message: `Signal for ${params.symbol} marked as ACTIVE`,
			symbol: params.symbol,
			status: 'active',
		});
	}),
	// buying zone columns
	http.get(API('/user/buying-zone-columns'), async () => {
		return HttpResponse.json({ columns: [] });
	}),
	http.put(API('/user/buying-zone-columns'), async ({ request }) => {
		const body = await request.json();
		return HttpResponse.json({ columns: (body as { columns: string[] }).columns });
	}),
	// filter presets (signals/orders, etc.)
	http.get(API('/user/filter-presets/:page'), async ({ params }) => {
		const page = String(params.page);
		return HttpResponse.json({ presets: filterPresets[page] ?? {} });
	}),
	http.post(API('/user/filter-presets'), async ({ request }) => {
		const body = (await request.json()) as {
			page?: string;
			preset_name?: string;
			filters?: Record<string, unknown>;
		};
		const page = body.page ?? 'signals';
		const presetName = body.preset_name ?? 'New Preset';
		const filters = body.filters ?? {};
		if (!filterPresets[page]) filterPresets[page] = {};
		filterPresets[page][presetName] = filters;
		return HttpResponse.json({ presets: filterPresets[page] });
	}),
	http.delete(API('/user/filter-presets/:page/:preset_name'), async ({ params }) => {
		const page = String(params.page);
		const presetName = String(params.preset_name);
		if (filterPresets[page]) {
			delete filterPresets[page][presetName];
		}
		return HttpResponse.json({ presets: filterPresets[page] ?? {} });
	}),
	http.options(API('/user/filter-presets/:page'), async () => HttpResponse.json({ ok: true })),
	http.options(API('/user/filter-presets/:page/:preset_name'), async () => HttpResponse.json({ ok: true })),
	// dashboard metrics
	http.get(API('/dashboard/metrics'), async () => {
		return HttpResponse.json({
			total_trades: 42,
			profitable_trades: 30,
			losing_trades: 12,
			win_rate: 71.4,
			average_profit_per_trade: 1200.5,
			best_trade_profit: 5000,
			worst_trade_loss: -1500,
			total_realized_pnl: 25000,
			best_trade_symbol: 'TCS',
			worst_trade_symbol: 'INFY',
			days_traded: 20,
			avg_holding_period_days: 3.2,
		});
	}),
	http.options(API('/dashboard/metrics'), async () => HttpResponse.json({ ok: true })),
	// portfolio history
	http.get(API('/user/portfolio/history'), async () => {
		const today = new Date();
		const format = (d: Date) => d.toISOString().slice(0, 10);
		return HttpResponse.json([
			{
				date: format(new Date(today.getTime() - 2 * 86_400_000)),
				total_value: 1020000,
				invested_value: 700000,
				available_cash: 320000,
				unrealized_pnl: 15000,
				realized_pnl: 8000,
				open_positions_count: 5,
				closed_positions_count: 12,
				total_return: 4.8,
				daily_return: 0.5,
				snapshot_type: 'daily',
			},
			{
				date: format(new Date(today.getTime() - 1 * 86_400_000)),
				total_value: 1035000,
				invested_value: 705000,
				available_cash: 330000,
				unrealized_pnl: 17000,
				realized_pnl: 9000,
				open_positions_count: 5,
				closed_positions_count: 13,
				total_return: 5.2,
				daily_return: 0.7,
				snapshot_type: 'daily',
			},
		]);
	}),
	http.options(API('/user/portfolio/history'), async () => HttpResponse.json({ ok: true })),
	// trading config
	http.get(API('/user/trading-config'), async () => {
		return HttpResponse.json({
			rsi_period: 10,
			rsi_oversold: 30.0,
			rsi_extreme_oversold: 20.0,
			rsi_near_oversold: 40.0,
			user_capital: 200000.0,
			max_portfolio_size: 6,
			max_position_volume_ratio: 0.1,
			min_absolute_avg_volume: 10000,
			chart_quality_enabled: true,
			chart_quality_min_score: 50.0,
			chart_quality_max_gap_frequency: 25.0,
			chart_quality_min_daily_range_pct: 1.0,
			chart_quality_max_extreme_candle_frequency: 20.0,
			default_stop_loss_pct: 0.08,
			tight_stop_loss_pct: 0.06,
			min_stop_loss_pct: 0.03,
			default_target_pct: 0.1,
			strong_buy_target_pct: 0.12,
			excellent_target_pct: 0.15,
			strong_buy_risk_reward: 3.0,
			buy_risk_reward: 2.5,
			excellent_risk_reward: 3.5,
			default_exchange: 'NSE',
			default_product: 'CNC',
			default_order_type: 'MARKET',
			default_variety: 'AMO',
			default_validity: 'DAY',
			allow_duplicate_recommendations_same_day: false,
			exit_on_ema9_or_rsi50: true,
			min_combined_score: 50,
			news_sentiment_enabled: false,
			news_sentiment_lookback_days: 7,
			news_sentiment_min_articles: 3,
			news_sentiment_pos_threshold: 0.6,
			news_sentiment_neg_threshold: -0.4,
			ml_enabled: false,
			ml_model_version: null,
			ml_confidence_threshold: 0.7,
			ml_combine_with_rules: true,
		});
	}),
	http.put(API('/user/trading-config'), async ({ request }) => {
		const body = (await request.json()) as Record<string, unknown>;
		// Return updated config (merge with defaults)
		return HttpResponse.json({
			rsi_period: body.rsi_period ?? 10,
			rsi_oversold: body.rsi_oversold ?? 30.0,
			rsi_extreme_oversold: body.rsi_extreme_oversold ?? 20.0,
			rsi_near_oversold: body.rsi_near_oversold ?? 40.0,
			user_capital: body.user_capital ?? 200000.0,
			max_portfolio_size: body.max_portfolio_size ?? 6,
			max_position_volume_ratio: body.max_position_volume_ratio ?? 0.1,
			min_absolute_avg_volume: body.min_absolute_avg_volume ?? 10000,
			chart_quality_enabled: body.chart_quality_enabled ?? true,
			chart_quality_min_score: body.chart_quality_min_score ?? 50.0,
			chart_quality_max_gap_frequency: body.chart_quality_max_gap_frequency ?? 25.0,
			chart_quality_min_daily_range_pct: body.chart_quality_min_daily_range_pct ?? 1.0,
			chart_quality_max_extreme_candle_frequency: body.chart_quality_max_extreme_candle_frequency ?? 20.0,
			default_stop_loss_pct: body.default_stop_loss_pct ?? 0.08,
			tight_stop_loss_pct: body.tight_stop_loss_pct ?? 0.06,
			min_stop_loss_pct: body.min_stop_loss_pct ?? 0.03,
			default_target_pct: body.default_target_pct ?? 0.1,
			strong_buy_target_pct: body.strong_buy_target_pct ?? 0.12,
			excellent_target_pct: body.excellent_target_pct ?? 0.15,
			strong_buy_risk_reward: body.strong_buy_risk_reward ?? 3.0,
			buy_risk_reward: body.buy_risk_reward ?? 2.5,
			excellent_risk_reward: body.excellent_risk_reward ?? 3.5,
			default_exchange: body.default_exchange ?? 'NSE',
			default_product: body.default_product ?? 'CNC',
			default_order_type: body.default_order_type ?? 'MARKET',
			default_variety: body.default_variety ?? 'AMO',
			default_validity: body.default_validity ?? 'DAY',
			allow_duplicate_recommendations_same_day: body.allow_duplicate_recommendations_same_day ?? false,
			exit_on_ema9_or_rsi50: body.exit_on_ema9_or_rsi50 ?? true,
			min_combined_score: body.min_combined_score ?? 50,
			news_sentiment_enabled: body.news_sentiment_enabled ?? false,
			news_sentiment_lookback_days: body.news_sentiment_lookback_days ?? 7,
			news_sentiment_min_articles: body.news_sentiment_min_articles ?? 3,
			news_sentiment_pos_threshold: body.news_sentiment_pos_threshold ?? 0.6,
			news_sentiment_neg_threshold: body.news_sentiment_neg_threshold ?? -0.4,
			ml_enabled: body.ml_enabled ?? false,
			ml_model_version: body.ml_model_version ?? null,
			ml_confidence_threshold: body.ml_confidence_threshold ?? 0.7,
			ml_combine_with_rules: body.ml_combine_with_rules ?? true,
		});
	}),
	http.post(API('/user/trading-config/reset'), async () => {
		// Return default config
		return HttpResponse.json({
			rsi_period: 10,
			rsi_oversold: 30.0,
			rsi_extreme_oversold: 20.0,
			rsi_near_oversold: 40.0,
			user_capital: 200000.0,
			max_portfolio_size: 6,
			max_position_volume_ratio: 0.1,
			min_absolute_avg_volume: 10000,
			chart_quality_enabled: true,
			chart_quality_min_score: 50.0,
			chart_quality_max_gap_frequency: 25.0,
			chart_quality_min_daily_range_pct: 1.0,
			chart_quality_max_extreme_candle_frequency: 20.0,
			default_stop_loss_pct: 0.08,
			tight_stop_loss_pct: 0.06,
			min_stop_loss_pct: 0.03,
			default_target_pct: 0.1,
			strong_buy_target_pct: 0.12,
			excellent_target_pct: 0.15,
			strong_buy_risk_reward: 3.0,
			buy_risk_reward: 2.5,
			excellent_risk_reward: 3.5,
			default_exchange: 'NSE',
			default_product: 'CNC',
			default_order_type: 'MARKET',
			default_variety: 'AMO',
			default_validity: 'DAY',
			allow_duplicate_recommendations_same_day: false,
			exit_on_ema9_or_rsi50: true,
			min_combined_score: 50,
			news_sentiment_enabled: false,
			news_sentiment_lookback_days: 7,
			news_sentiment_min_articles: 3,
			news_sentiment_pos_threshold: 0.6,
			news_sentiment_neg_threshold: -0.4,
			ml_enabled: false,
			ml_model_version: null,
			ml_confidence_threshold: 0.7,
			ml_combine_with_rules: true,
		});
	}),
	// admin ml training
	http.get(API('/admin/ml/jobs'), async ({ request }) => {
		const url = new URL(request.url);
		const statusFilter = url.searchParams.get('status');
		const modelType = url.searchParams.get('model_type');
		let jobs = [...mlTrainingJobs];
		if (statusFilter) {
			jobs = jobs.filter((job) => job.status === statusFilter);
		}
		if (modelType) {
			jobs = jobs.filter((job) => job.model_type === modelType);
		}
		return HttpResponse.json({ jobs });
	}),
	http.get(API('/admin/ml/jobs/:id'), async ({ params }) => {
		const job = mlTrainingJobs.find((j) => j.id === Number(params.id));
		if (!job) {
			return HttpResponse.json({ detail: 'Training job not found' }, { status: 404 });
		}
		return HttpResponse.json(job);
	}),
	http.post(API('/admin/ml/train'), async ({ request }) => {
		const body = (await request.json()) as { model_type?: string; algorithm?: string; training_data_path?: string };
		const modelType = typeof body.model_type === 'string' ? body.model_type : 'verdict_classifier';
		const algorithm = typeof body.algorithm === 'string' ? body.algorithm : 'xgboost';
		const trainingDataPath = typeof body.training_data_path === 'string' ? body.training_data_path : 'data/training/verdict_classifier.csv';
		const newJob = {
			id: mlJobIdCounter++,
			started_by: 1,
			status: 'completed',
			model_type: modelType,
			algorithm: algorithm,
			training_data_path: trainingDataPath,
			started_at: new Date().toISOString(),
			completed_at: new Date(Date.now() + 2000).toISOString(),
			model_path: `models/${modelType}/${algorithm}-v${mlModelIdCounter}.json`,
			accuracy: 0.81,
			error_message: null,
			logs: 'Mock training completed.',
		};
		mlTrainingJobs.unshift(newJob);

		const newModel = {
			id: mlModelIdCounter++,
			model_type: newJob.model_type,
			version: `v${mlModelIdCounter - 1}`,
			model_path: newJob.model_path,
			accuracy: newJob.accuracy,
			training_job_id: newJob.id,
			is_active: false,
			created_at: new Date().toISOString(),
			created_by: 1,
		};
		mlModels.unshift(newModel);
		return HttpResponse.json(newJob, { status: 201 });
	}),
	http.get(API('/admin/ml/models'), async ({ request }) => {
		const url = new URL(request.url);
		const modelType = url.searchParams.get('model_type');
		const active = url.searchParams.get('active');
		let models = [...mlModels];
		if (modelType) {
			models = models.filter((model) => model.model_type === modelType);
		}
		if (active !== null) {
			const activeBool = active === 'true';
			models = models.filter((model) => model.is_active === activeBool);
		}
		return HttpResponse.json({ models });
	}),
	http.post(API('/admin/ml/models/:id/activate'), async ({ params }) => {
		const modelId = Number(params.id);
		const model = mlModels.find((m) => m.id === modelId);
		if (!model) {
			return HttpResponse.json({ detail: 'Model not found' }, { status: 404 });
		}
		mlModels.forEach((m) => {
			if (m.model_type === model.model_type) {
				m.is_active = m.id === modelId;
			}
		});
		return HttpResponse.json({
			message: `Model ${model.version} activated for ${model.model_type}`,
			model: { ...model, is_active: true },
		});
	}),
	// notifications
	http.get(API('/user/notifications/count'), async () => {
		return HttpResponse.json({ unread_count: 0 });
	}),
	// pnl summary
	http.get(API('/user/pnl/summary'), async () => {
		return HttpResponse.json({
			totalPnl: 15000.50,
			tradesGreen: 25,
			tradesRed: 8,
			totalRealizedPnl: 12000,
			totalUnrealizedPnl: 3000.50,
			avgTradePnl: 487.5,
			minTradePnl: -1200.50,
			maxTradePnl: 2500.75,
		});
	}),
	http.options(API('/user/pnl/summary'), async () => HttpResponse.json({ ok: true })),
	// daily pnl
	http.get(API('/user/pnl/daily'), async () => {
		const today = new Date();
		const format = (d: Date) => d.toISOString().slice(0, 10);
		return HttpResponse.json([
			{ date: format(new Date(today.getTime() - 2 * 86_400_000)), pnl: 2500.75 },
			{ date: format(new Date(today.getTime() - 1 * 86_400_000)), pnl: -1200.50 },
			{ date: format(today), pnl: 500.0 },
		]);
	}),
	http.options(API('/user/pnl/daily'), async () => HttpResponse.json({ ok: true })),
];
