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

export const handlers = [
	// auth
	http.post(API('/auth/login'), async ({ request }) => {
		return HttpResponse.json({ access_token: 'test-token', token_type: 'bearer' });
	}),
	http.post(API('/auth/signup'), async () => {
		return HttpResponse.json({ access_token: 'test-token', token_type: 'bearer' });
	}),
	http.get(API('/auth/me'), async () => {
		return HttpResponse.json({ id: 1, email: 'test@example.com', roles: ['admin'] });
	}),
	// settings
	http.get(API('/user/settings'), async () => {
		return HttpResponse.json({ trade_mode: 'paper', broker: null, broker_status: null });
	}),
	http.put(API('/user/settings'), async ({ request }) => {
		const body = (await request.json()) as any;
		return HttpResponse.json({ trade_mode: body['trade_mode'] ?? 'paper', broker: body['broker'] ?? null, broker_status: null });
	}),
	// broker
	http.post(API('/user/broker/creds'), async () => {
		return HttpResponse.json({ status: 'ok' });
	}),
	http.post(API('/user/broker/test'), async ({ request }) => {
		const body = (await request.json()) as any;
		if (!body.api_key || !body.api_secret) {
			return HttpResponse.json({ ok: false, message: 'API key and secret are required' }, { status: 400 });
		}
		// Basic test (only api_key/api_secret)
		if (!body.mobile_number || !body.password || !body.mpin) {
			return HttpResponse.json({
				ok: true,
				message: 'Client initialized successfully (full login test requires mobile, password, and MPIN)'
			});
		}
		// Full test (with login credentials)
		// Mock: accept any non-empty values for testing
		if (body.mobile_number && body.password && body.mpin) {
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
				password: 'testpassword',
				mpin: '1234',
				environment: 'prod'
			});
		}
		return HttpResponse.json({ has_creds: true, api_key_masked: '****1234', api_secret_masked: '****5678' });
	}),
	// orders
	http.get(API('/user/orders'), async ({ request }) => {
		const url = new URL(request.url);
		const status = url.searchParams.get('status') ?? 'amo';
		const now = new Date().toISOString();
		const byStatus: Record<string, any[]> = {
			amo: [
				{ id: 101, symbol: 'INFY', side: 'buy', qty: 10, price: 1500, status: 'amo', created_at: now, updated_at: now },
			],
			ongoing: [
				{ id: 201, symbol: 'RELIANCE', side: 'buy', qty: 5, price: 2400, status: 'ongoing', created_at: now, updated_at: now },
			],
			sell: [
				{ id: 301, symbol: 'TCS', side: 'sell', qty: 3, price: 3600, status: 'sell', created_at: now, updated_at: now },
			],
			closed: [
				{ id: 401, symbol: 'HDFCBANK', side: 'buy', qty: 2, price: 1500, status: 'closed', created_at: now, updated_at: now },
			],
		};
		return HttpResponse.json(byStatus[status] ?? []);
	}),
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
		const body = (await request.json()) as any;
		return HttpResponse.json({ id: Math.floor(Math.random() * 10000), email: body.email, name: body.name ?? null, role: body.role ?? 'user', is_active: true, created_at: new Date().toISOString(), updated_at: new Date().toISOString() });
	}),
	http.put(API('/admin/users/:id'), async ({ params, request }) => {
		const body = (await request.json()) as any;
		return HttpResponse.json({ id: Number(params.id), email: 'updated@example.com', name: body.name ?? null, role: body.role ?? 'user', is_active: body.is_active ?? true, created_at: new Date().toISOString(), updated_at: new Date().toISOString() });
	}),
	http.patch(API('/admin/users/:id'), async ({ params, request }) => {
		const body = (await request.json()) as any;
		return HttpResponse.json({ id: Number(params.id), email: 'updated@example.com', name: body.name ?? null, role: body.role ?? 'user', is_active: body.is_active ?? true, created_at: new Date().toISOString(), updated_at: new Date().toISOString() });
	}),
	http.delete(API('/admin/users/:id'), async () => {
		return HttpResponse.json({ ok: true });
	}),
	// signals
	http.get(API('/signals/buying-zone'), async () => {
		return HttpResponse.json([
			{ id: 1, symbol: 'TCS', rsi10: 25.2, ema9: 100, ema200: 90, distance_to_ema9: 5, clean_chart: true, monthly_support_dist: 1.2, confidence: 0.7, ts: new Date().toISOString() },
		]);
	}),
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
		const body = (await request.json()) as any;
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
		const body = (await request.json()) as any;
		const newJob = {
			id: mlJobIdCounter++,
			started_by: 1,
			status: 'completed',
			model_type: body.model_type ?? 'verdict_classifier',
			algorithm: body.algorithm ?? 'xgboost',
			training_data_path: body.training_data_path ?? 'data/training/verdict_classifier.csv',
			started_at: new Date().toISOString(),
			completed_at: new Date(Date.now() + 2000).toISOString(),
			model_path: `models/${body.model_type ?? 'verdict_classifier'}/${body.algorithm ?? 'xgboost'}-v${mlModelIdCounter}.json`,
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
];
