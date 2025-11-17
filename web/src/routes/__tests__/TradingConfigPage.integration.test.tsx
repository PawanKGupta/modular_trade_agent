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

describe('TradingConfigPage Integration', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(tradingConfigApi.getTradingConfig).mockResolvedValue(mockConfig);
		vi.mocked(tradingConfigApi.updateTradingConfig).mockResolvedValue(mockConfig);
		vi.mocked(tradingConfigApi.resetTradingConfig).mockResolvedValue(mockConfig);
	});

	it('completes full workflow: modify config -> save -> verify update', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<TradingConfigPage />
				</MemoryRouter>
			)
		);

		// Wait for config to load
		await waitFor(() => {
			expect(screen.getByText(/Trading Configuration/i)).toBeInTheDocument();
		});

		const rsiPeriodInput = await screen.findByLabelText(/RSI Period/i);
		fireEvent.change(rsiPeriodInput, { target: { value: '15' } });

		// Verify unsaved changes indicator appears
		await waitFor(() => {
			expect(screen.getByText(/You have unsaved changes/i)).toBeInTheDocument();
		});

		// Click save
		const [saveButton] = screen.getAllByRole('button', { name: /Save Changes/i });
		fireEvent.click(saveButton);

		// Verify API was called with correct update
		await waitFor(() => {
			expect(tradingConfigApi.updateTradingConfig).toHaveBeenCalledWith(
				expect.objectContaining({ rsi_period: 15 }),
				expect.any(Object)
			);
		});
	});

	it('completes workflow: modify multiple fields -> save -> verify all updates', async () => {
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

		// Modify multiple fields
		const rsiPeriodInput = await screen.findByLabelText(/RSI Period/i);
		fireEvent.change(rsiPeriodInput, { target: { value: '15' } });

		const capitalInput = await screen.findByLabelText(/Capital per Trade/i);
		fireEvent.change(capitalInput, { target: { value: '250000' } });

		const portfolioSizeInput = await screen.findByLabelText(/Max Portfolio Size/i);
		fireEvent.change(portfolioSizeInput, { target: { value: '8' } });

		// Save
		const [saveButton] = screen.getAllByRole('button', { name: /Save Changes/i });
		fireEvent.click(saveButton);

		// Verify all updates were sent
		await waitFor(() => {
			expect(tradingConfigApi.updateTradingConfig).toHaveBeenCalledWith(
				expect.objectContaining({
					rsi_period: 15,
					user_capital: 250000,
					max_portfolio_size: 8,
				}),
				expect.any(Object)
			);
		});
	});

	it('completes workflow: apply preset -> verify changes -> save', async () => {
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

		// Find and click preset button
		const presetButtons = await screen.findAllByRole('button', { name: /Apply Preset/i });
		if (presetButtons.length > 0) {
			fireEvent.click(presetButtons[0]);

			// Verify unsaved changes appear
			await waitFor(() => {
				expect(screen.getByText(/You have unsaved changes/i)).toBeInTheDocument();
			});

			// Save
			const [saveButton] = screen.getAllByRole('button', { name: /Save Changes/i });
			fireEvent.click(saveButton);

			// Verify update was called
			await waitFor(() => {
				expect(tradingConfigApi.updateTradingConfig).toHaveBeenCalled();
			});
		}
	});

	it('completes workflow: modify -> cancel -> verify no save', async () => {
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

		// Modify a field
		const rsiPeriodInput = await screen.findByLabelText(/RSI Period/i);
		fireEvent.change(rsiPeriodInput, { target: { value: '15' } });

		// Wait for sticky bar
		await waitFor(() => {
			expect(screen.getByText(/You have unsaved changes/i)).toBeInTheDocument();
		});

		// Click cancel
		const cancelButton = screen.getByRole('button', { name: /Cancel/i });
		fireEvent.click(cancelButton);

		// Verify no save was called
		expect(tradingConfigApi.updateTradingConfig).not.toHaveBeenCalled();

		// Verify unsaved changes indicator is gone
		await waitFor(() => {
			expect(screen.queryByText(/You have unsaved changes/i)).not.toBeInTheDocument();
		});
	});

	it('completes workflow: reset config -> verify reset API call', async () => {
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

		// Click reset
		const [resetButton] = await screen.findAllByRole('button', { name: /Reset to Defaults/i });
		fireEvent.click(resetButton);

		// Verify reset API was called
		await waitFor(() => {
			expect(tradingConfigApi.resetTradingConfig).toHaveBeenCalled();
		});

		confirmSpy.mockRestore();
	});
});
