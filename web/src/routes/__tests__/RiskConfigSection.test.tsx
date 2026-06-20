import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { RiskConfigSection } from '../dashboard/RiskConfigSection';
import { DEFAULT_CONFIG, type TradingConfig } from '@/api/trading-config';

const mockConfig: TradingConfig = {
	...DEFAULT_CONFIG,
};

describe('RiskConfigSection', () => {
	it('renders all risk management fields', () => {
		const onChange = vi.fn();
		render(<RiskConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		expect(screen.getByText(/Stop Loss Percentages/i)).toBeInTheDocument();
		expect(screen.getByText(/Target Percentages/i)).toBeInTheDocument();
		expect(screen.getByText(/Risk-Reward Ratios/i)).toBeInTheDocument();
	});

	it('displays current stop loss values', () => {
		const onChange = vi.fn();
		render(<RiskConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const minStopLossInput = screen.getByLabelText(/Min Stop Loss/i) as HTMLInputElement;
		expect(minStopLossInput.value).toBe('0.03');
	});

	it('calls onChange when stop loss is changed', () => {
		const onChange = vi.fn();
		render(<RiskConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const minStopLossInput = screen.getByLabelText(/Min Stop Loss/i);
		fireEvent.change(minStopLossInput, { target: { value: '0.04' } });

		expect(onChange).toHaveBeenCalledWith({ min_stop_loss_pct: 0.04 });
	});

	it('handles null stop loss values', () => {
		const onChange = vi.fn();
		render(<RiskConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const minStopLossInput = screen.getByLabelText(/Min Stop Loss/i);

		// Clear the value to send null upstream
		fireEvent.change(minStopLossInput, { target: { value: '' } });
		expect(onChange).toHaveBeenCalledWith({ min_stop_loss_pct: null });
	});

	it('displays current target values', () => {
		const onChange = vi.fn();
		render(<RiskConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const defaultTargetInput = screen.getByLabelText(/Default Target/i) as HTMLInputElement;
		expect(defaultTargetInput.value).toBe('0.1');
	});

	it('calls onChange when target is changed', () => {
		const onChange = vi.fn();
		render(<RiskConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const defaultTargetInput = screen.getByLabelText(/Default Target/i);
		fireEvent.change(defaultTargetInput, { target: { value: '0.12' } });

		expect(onChange).toHaveBeenCalledWith({ default_target_pct: 0.12 });
	});

	it('displays current risk-reward values', () => {
		const onChange = vi.fn();
		render(<RiskConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const buyRiskRewardInput = screen.getByLabelText(/^Buy Risk-Reward$/i) as HTMLInputElement;
		expect(buyRiskRewardInput.value).toBe('2.5');
	});

	it('calls onChange when risk-reward is changed', () => {
		const onChange = vi.fn();
		render(<RiskConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const buyRiskRewardInput = screen.getByLabelText(/^Buy Risk-Reward$/i);
		fireEvent.change(buyRiskRewardInput, { target: { value: '3.0' } });

		expect(onChange).toHaveBeenCalledWith({ buy_risk_reward: 3.0 });
	});

	it('shows validation message for default stop loss', () => {
		const onChange = vi.fn();
		render(<RiskConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		expect(screen.getByText(/Must be > Tight/i)).toBeInTheDocument();
	});

	it('shows asterisk for modified fields', () => {
		const onChange = vi.fn();
		const modifiedConfig = { ...mockConfig, default_stop_loss_pct: 0.1 };
		render(<RiskConfigSection config={modifiedConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const defaultStopLossLabel = screen.getByText(/Default Stop Loss/i);
		expect(defaultStopLossLabel.textContent).toContain('*');
	});

	it('displays default values for all fields', () => {
		const onChange = vi.fn();
		render(<RiskConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		expect(screen.getByText(new RegExp(`Default: ${(DEFAULT_CONFIG.min_stop_loss_pct! * 100).toFixed(0)}%`))).toBeInTheDocument();
		expect(screen.getByText(new RegExp(`Default: ${(DEFAULT_CONFIG.default_target_pct * 100).toFixed(0)}%`))).toBeInTheDocument();
		expect(screen.getByText(new RegExp(`Default: ${DEFAULT_CONFIG.buy_risk_reward}`))).toBeInTheDocument();
	});

	it('updates tight stop loss and sell risk-reward fields', () => {
		const onChange = vi.fn();
		render(<RiskConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		fireEvent.change(screen.getByLabelText(/Tight Stop Loss/i), { target: { value: '0.07' } });
		expect(onChange).toHaveBeenCalledWith({ tight_stop_loss_pct: 0.07 });

		fireEvent.change(screen.getByLabelText(/Default Stop Loss/i), { target: { value: '0.09' } });
		expect(onChange).toHaveBeenCalledWith({ default_stop_loss_pct: 0.09 });

		fireEvent.change(screen.getByLabelText(/Strong Buy Target/i), { target: { value: '0.13' } });
		expect(onChange).toHaveBeenCalledWith({ strong_buy_target_pct: 0.13 });

		fireEvent.change(screen.getByLabelText(/Excellent Risk-Reward/i), { target: { value: '3.6' } });
		expect(onChange).toHaveBeenCalledWith({ excellent_risk_reward: 3.6 });
	});
});
