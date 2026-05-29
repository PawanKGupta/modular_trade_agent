import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const hoisted = vi.hoisted(() => ({
	api: {
		get: vi.fn(),
		post: vi.fn(),
		patch: vi.fn(),
		put: vi.fn(),
		delete: vi.fn(),
	},
}));

vi.mock('../client', () => ({
	api: hoisted.api,
}));

import * as admin from '../admin';
import * as billing from '../billing';
import * as broker from '../broker';
import * as exportApi from '../export';
import * as logs from '../logs';
import * as metrics from '../metrics';
import * as mlTraining from '../ml-training';
import * as monitoring from '../monitoring';
import * as notificationPreferences from '../notification-preferences';
import * as notifications from '../notifications';
import * as orders from '../orders';
import * as paperTrading from '../paper-trading';
import * as pnl from '../pnl';
import * as portfolio from '../portfolio';
import * as reports from '../reports';
import * as service from '../service';
import * as signals from '../signals';
import * as targets from '../targets';
import * as tradingConfig from '../trading-config';
import * as user from '../user';

function setupDefaultMocks() {
	hoisted.api.get.mockResolvedValue({ data: [], headers: {} });
	hoisted.api.post.mockResolvedValue({ data: {} });
	hoisted.api.patch.mockResolvedValue({ data: {} });
	hoisted.api.put.mockResolvedValue({ data: {} });
	hoisted.api.delete.mockResolvedValue({ data: { message: 'ok' } });
}

beforeEach(() => {
	hoisted.api.get.mockReset();
	hoisted.api.post.mockReset();
	hoisted.api.patch.mockReset();
	hoisted.api.put.mockReset();
	hoisted.api.delete.mockReset();
	setupDefaultMocks();
});

describe('api wrappers (mocked client)', () => {
	it('admin', async () => {
		await admin.listUsers();
		await admin.listUsers({ q: '  ' });
		await admin.listUsers({ q: 'alice', limit: 10 });
		await admin.createUser({ email: 'a@b.com', password: 'x' });
		await admin.updateUser(1, { name: 'N' });
		await admin.deleteUser(2);
		await admin.listServiceSchedules();
		await admin.getServiceSchedule('task');
		await admin.updateServiceSchedule('task', { schedule_time: '09:30' });
		await admin.enableServiceSchedule('task');
		await admin.disableServiceSchedule('task');
		expect(hoisted.api.delete).toHaveBeenCalled();
	});

	it('billing', async () => {
		await billing.getMyBillingTransactions(5);
		await billing.getPerformanceFeeArrears();
		await billing.getPerformanceBills(10);
		await billing.checkoutPerformanceBill(3);
		await billing.createRazorpayOrder({ amount_paise: 100 });
		await billing.verifyRazorpayPayment({
			razorpay_order_id: 'o',
			razorpay_payment_id: 'p',
			razorpay_signature: 's',
		});
		await billing.getAdminBillingSettings();
		await billing.patchAdminBillingSettings({ payment_card_enabled: true });
		await billing.patchAdminRazorpayCredentials({ razorpay_key_id: 'k' });
		await billing.getAdminTransactions({ user_id: 1, failed_only: true });
		await billing.runBillingReconcile();
		await billing.postAdminRefund({ billing_transaction_id: 1 });
	});

	it('broker', async () => {
		hoisted.api.get.mockResolvedValueOnce({
			data: {
				transactions: [],
				closed_positions: [],
				statistics: {
					total_trades: 0,
					closed_positions: 0,
					win_rate: 0,
					realized_pnl: 0,
				},
			},
			headers: {},
		});
		await broker.getBrokerHistory({ from: '2026-01-01', limit: 5 });
	});

	it('targets and paper-trading', async () => {
		await targets.listTargets();
		await paperTrading.getPaperTradingPortfolio();
		await paperTrading.getPaperTradingHistory({ positions_page: 1 });
	});

	it('pnl', async () => {
		await pnl.getDailyPnl(new Date(2026, 0, 1), '2026-01-31', 'paper', true);
		await pnl.getPnlSummary();
		await pnl.triggerPnlCalculation('2026-01-01', 'paper');
		await pnl.backfillPnlData('2026-01-01', '2026-01-02');
		await pnl.getClosedPositions(2, 20, 'broker', 'realized_pnl', 'asc');
	});

	it('portfolio', async () => {
		hoisted.api.get.mockResolvedValueOnce({ data: null, headers: {} });
		const hist = await portfolio.getPortfolioHistory(new Date(2026, 0, 1));
		expect(hist).toEqual([]);
		await portfolio.createPortfolioSnapshot('2026-01-15');
		await portfolio.createPortfolioSnapshot();
	});

	it('orders', async () => {
		await orders.listOrders({ status: 'pending', page: 1 });
		await orders.retryOrder(9);
		await orders.dropOrder(9);
		await orders.syncOrderStatus();
		await orders.syncOrderStatus(42);
	});

	it('logs', async () => {
		hoisted.api.get.mockResolvedValue({ data: { logs: [], errors: [] }, headers: {} });
		await logs.getUserLogs({ limit: 5 });
		await logs.getUserErrorLogs({ resolved: false });
		await logs.getAdminLogs({ user_id: 1 });
		await logs.getAdminErrorLogs({ user_id: 2 });
		hoisted.api.post.mockResolvedValueOnce({
			data: { message: 'ok', error: { id: 1 } as logs.ErrorLogEntry },
		});
		await logs.resolveErrorLog(1, { notes: 'fixed' });
	});

	it('metrics', async () => {
		await metrics.getDashboardMetrics(30, 'paper');
		await metrics.getDailyMetrics('2026-01-01', 'broker');
	});

	it('ml-training', async () => {
		await mlTraining.startTrainingJob({
			model_type: 'verdict_classifier',
			algorithm: 'random_forest',
			training_data_path: '/tmp/x.csv',
		});
		await mlTraining.getTrainingJobs({ limit: 5 });
		await mlTraining.getMLModels({ active_only: true });
		await mlTraining.activateModel(1);
	});

	it('monitoring', async () => {
		await monitoring.getServicesHealth();
		await monitoring.getTaskExecutions({ page: 1 });
		await monitoring.getRunningTasks(3);
		await monitoring.getRunningTasks();
		await monitoring.getTaskMetrics({ period_days: 7 });
		await monitoring.getScheduleCompliance();
		await monitoring.getActiveSessions();
		await monitoring.getReauthHistory({ page_size: 10 });
		await monitoring.getAuthErrors({});
		await monitoring.getReauthStatistics({ period_days: 30 });
		await monitoring.getMonitoringDashboard();
	});

	it('notifications', async () => {
		hoisted.api.get.mockResolvedValue({ data: [], headers: {} });
		await notifications.getNotifications({ read: false, limit: 10 });
		await notifications.getUnreadNotifications(5);
		hoisted.api.get.mockResolvedValueOnce({ data: { unread_count: 0 }, headers: {} });
		await notifications.getNotificationCount();
		hoisted.api.post.mockResolvedValueOnce({ data: { id: 1 } as notifications.Notification, headers: {} });
		await notifications.markNotificationRead(1);
		await notifications.markAllNotificationsRead();
	});

	it('notification-preferences', async () => {
		hoisted.api.get.mockResolvedValueOnce({ data: { telegram_enabled: false }, headers: {} });
		await notificationPreferences.getNotificationPreferences();
		hoisted.api.put.mockResolvedValueOnce({ data: { telegram_enabled: true }, headers: {} });
		await notificationPreferences.updateNotificationPreferences({ telegram_enabled: true });
	});

	it('service', async () => {
		await service.startService();
		await service.stopService();
		await service.getServiceStatus();
		await service.getTaskHistory({ limit: 3 });
		await service.getServiceLogs({ level: 'ERROR' });
		await service.getPositionCreationMetrics();
		hoisted.api.get.mockResolvedValueOnce({ data: { positions: [], count: 0 }, headers: {} });
		await service.getPositionsWithoutSellOrders();
		const abortErr = new Error('aborted');
		abortErr.name = 'AbortError';
		hoisted.api.get.mockRejectedValueOnce(abortErr);
		const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
		const empty = await service.getPositionsWithoutSellOrders();
		expect(empty).toEqual({ positions: [], count: 0 });
		warnSpy.mockRestore();
		await service.getIndividualServicesStatus();
		await service.startIndividualService({ task_name: 't' });
		await service.stopIndividualService({ task_name: 't' });
		await service.runTaskOnce({ task_name: 't' });
		await service.getTradingDayInfo();
	});

	it('signals', async () => {
		await signals.getBuyingZone(10, 'today', 'active');
		await signals.getBuyingZoneColumns();
		hoisted.api.put.mockResolvedValueOnce({ data: { columns: ['a'] }, headers: {} });
		await signals.saveBuyingZoneColumns(['a']);
		hoisted.api.patch.mockResolvedValueOnce({ data: undefined, headers: {} });
		await signals.rejectSignal('INFY');
		await signals.activateSignal('INFY');
	});

	it('trading-config', async () => {
		await tradingConfig.getTradingConfig();
		await tradingConfig.updateTradingConfig({ rsi_period: 14 });
		await tradingConfig.resetTradingConfig();
	});

	it('user', async () => {
		await user.getSettings();
		await user.updateSettings({ trade_mode: 'paper' });
		await user.saveBrokerCreds({ broker: 'kotak', api_key: 'k', api_secret: 's' });
		await user.testBrokerConnection({ broker: 'kotak', api_key: 'k', api_secret: 's' });
		await user.getBrokerStatus();
		await user.getBrokerCredsInfo(false);
		await user.getBrokerCredsInfo(true);
		hoisted.api.get.mockResolvedValueOnce({ data: { positions: [] }, headers: {} });
		await user.getPortfolio();
		hoisted.api.get.mockResolvedValueOnce({ data: { positions: [] }, headers: {} });
		await user.getBrokerSystemHoldings();
		hoisted.api.get.mockResolvedValueOnce({ data: [], headers: {} });
		await user.getBrokerOrders();
	});
});

describe('export and reports (blob + DOM)', () => {
	beforeEach(() => {
		vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock');
		vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
		const link = { click: vi.fn(), href: '', download: '' };
		vi.spyOn(document, 'createElement').mockReturnValue(link as unknown as HTMLAnchorElement);
		vi.spyOn(document.body, 'appendChild').mockImplementation(() => link);
		vi.spyOn(document.body, 'removeChild').mockImplementation(() => link);
		setupDefaultMocks();
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	it('exportCsv variants', async () => {
		hoisted.api.get.mockResolvedValue({
			data: new Blob(['x']),
			headers: { 'content-disposition': 'attachment; filename="custom.csv"' },
		});
		await exportApi.exportPnl({ startDate: '2026-01-01', tradeMode: 'broker' });
		hoisted.api.get.mockResolvedValue({
			data: new Blob(['x']),
			headers: {},
		});
		await exportApi.exportTradeHistory({});
		await exportApi.exportSignals({ verdict: 'buy' });
		await exportApi.exportOrders({ status: 'closed' });
		await exportApi.exportPortfolio({ tradeMode: 'paper' });
	});

	it('exportPnlPdf', async () => {
		hoisted.api.get.mockResolvedValue({
			data: new Blob(['%PDF']),
			headers: { 'content-disposition': 'attachment; filename="rep.pdf"' },
		});
		await reports.exportPnlPdf({ period: 'daily', tradeMode: 'paper' });
	});
});
