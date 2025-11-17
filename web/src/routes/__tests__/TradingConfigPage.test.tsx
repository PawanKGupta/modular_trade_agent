import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { TradingConfigPage } from '../dashboard/TradingConfigPage';
import { withProviders } from '@/test/utils';
import * as tradingConfigApi from '@/api/trading-config';

// Mock the API module
vi.mock('@/api/trading-config', async (importOriginal) => {
	const actual = await importOriginal<typeof import('@/api/trading-config')>();
	return {
		...actual,
		getTradingConfig: vi.fn(),
		updateTradingConfig: vi.fn(),
		resetTradingConfig: vi.fn(),
	};
});

const mockConfig: tradingConfigApi.TradingConfig = {
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
};

describe('TradingConfigPage', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(tradingConfigApi.getTradingConfig).mockResolvedValue(mockConfig);
		vi.mocked(tradingConfigApi.updateTradingConfig).mockResolvedValue(mockConfig);
		vi.mocked(tradingConfigApi.resetTradingConfig).mockResolvedValue(mockConfig);
	});

	it('renders trading configuration page', async () => {
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/trading-config']}>
					<TradingConfigPage />
				</MemoryRouter>
			)
		);

		expect(await screen.findByText(/Trading Configuration/i)).toBeInTheDocument();
		expect(await screen.findByText(/Strategy Parameters/i)).toBeInTheDocument();
		expect(screen.getByText(/Capital & Position Management/i)).toBeInTheDocument();
		expect(screen.getByText(/Risk Management/i)).toBeInTheDocument();
		expect(screen.getByText(/Order Defaults/i)).toBeInTheDocument();
		expect(screen.getByText(/Behavior Settings/i)).toBeInTheDocument();
	});

	it('displays save and reset buttons', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<TradingConfigPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByRole('button', { name: /Save Changes/i })).toBeInTheDocument();
			expect(screen.getByRole('button', { name: /Reset to Defaults/i })).toBeInTheDocument();
		});
	});

	it('shows unsaved changes indicator when config is modified', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<TradingConfigPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Trading Configuration/i)).toBeInTheDocument();
		});

		// Wait for form fields to load
		const rsiPeriodInput = await screen.findByLabelText(/RSI Period/i);
		fireEvent.change(rsiPeriodInput, { target: { value: '15' } });

		// Should show unsaved changes (there may be multiple, so use getAllByText)
		await waitFor(() => {
			const unsavedIndicators = screen.getAllByText(/Unsaved changes/i);
			expect(unsavedIndicators.length).toBeGreaterThan(0);
		});
	});

	it('saves configuration changes', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<TradingConfigPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Trading Configuration/i)).toBeInTheDocument();
		});

		// Wait for form fields to load
		const rsiPeriodInput = await screen.findByLabelText(/RSI Period/i);
		fireEvent.change(rsiPeriodInput, { target: { value: '15' } });

		// Click save (there may be multiple buttons, so get the first enabled one)
		const saveButtons = await screen.findAllByRole('button', { name: /Save Changes/i });
		const enabledSaveButton = saveButtons.find((btn) => !(btn as HTMLButtonElement).disabled);
		if (enabledSaveButton) {
			fireEvent.click(enabledSaveButton);
		} else {
			fireEvent.click(saveButtons[0]);
		}

		await waitFor(() => {
			expect(tradingConfigApi.updateTradingConfig).toHaveBeenCalled();
		});
	});

	it('resets configuration to defaults', async () => {
		// Mock window.confirm
		const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);

		render(
			withProviders(
				<MemoryRouter>
					<TradingConfigPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Trading Configuration/i)).toBeInTheDocument();
		});

		const resetButton = await screen.findByRole('button', { name: /Reset to Defaults/i });
		fireEvent.click(resetButton);

		await waitFor(() => {
			expect(confirmSpy).toHaveBeenCalled();
			expect(tradingConfigApi.resetTradingConfig).toHaveBeenCalled();
		});

		confirmSpy.mockRestore();
	});

	it('does not reset when user cancels confirmation', async () => {
		const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);

		render(
			withProviders(
				<MemoryRouter>
					<TradingConfigPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Trading Configuration/i)).toBeInTheDocument();
		});

		const resetButton = await screen.findByRole('button', { name: /Reset to Defaults/i });
		fireEvent.click(resetButton);

		await waitFor(() => {
			expect(confirmSpy).toHaveBeenCalled();
		});

		expect(tradingConfigApi.resetTradingConfig).not.toHaveBeenCalled();
		confirmSpy.mockRestore();
	});

	it('disables save button when there are no changes', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<TradingConfigPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			const saveButton = screen.getByRole('button', { name: /Save Changes/i });
			expect(saveButton).toBeDisabled();
		});
	});

	it('shows sticky save bar when there are unsaved changes', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<TradingConfigPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Trading Configuration/i)).toBeInTheDocument();
		});

		// Wait for form fields to load
		const rsiPeriodInput = await screen.findByLabelText(/RSI Period/i);
		fireEvent.change(rsiPeriodInput, { target: { value: '15' } });

		// Should show sticky save bar
		await waitFor(() => {
			expect(screen.getByText(/You have unsaved changes/i)).toBeInTheDocument();
		});
	});

	it('cancels changes when cancel button is clicked', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<TradingConfigPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Trading Configuration/i)).toBeInTheDocument();
		});

		// Wait for form fields to load
		const rsiPeriodInput = await screen.findByLabelText(/RSI Period/i);
		fireEvent.change(rsiPeriodInput, { target: { value: '15' } });

		// Wait for sticky bar to appear
		await waitFor(() => {
			expect(screen.getByText(/You have unsaved changes/i)).toBeInTheDocument();
		});

		// Click cancel
		const cancelButton = await screen.findByRole('button', { name: /Cancel/i });
		fireEvent.click(cancelButton);

		// Should no longer show unsaved changes
		await waitFor(() => {
			expect(screen.queryByText(/You have unsaved changes/i)).not.toBeInTheDocument();
		});
	});

	it('displays loading state', () => {
		vi.mocked(tradingConfigApi.getTradingConfig).mockImplementation(() => new Promise(() => {})); // Never resolves

		render(
			withProviders(
				<MemoryRouter>
					<TradingConfigPage />
				</MemoryRouter>
			)
		);

		expect(screen.getByText(/Loading trading configuration/i)).toBeInTheDocument();
	});
});
