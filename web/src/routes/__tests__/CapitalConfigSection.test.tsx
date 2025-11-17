import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CapitalConfigSection } from '../dashboard/CapitalConfigSection';
import { DEFAULT_CONFIG, type TradingConfig } from '@/api/trading-config';

const mockConfig: TradingConfig = {
	...DEFAULT_CONFIG,
};

describe('CapitalConfigSection', () => {
	it('renders capital and position management fields', () => {
		const onChange = vi.fn();
		render(<CapitalConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		expect(screen.getByText(/Capital & Position Management/i)).toBeInTheDocument();
		expect(screen.getByLabelText(/Capital per Trade/i)).toBeInTheDocument();
		expect(screen.getByLabelText(/Max Portfolio Size/i)).toBeInTheDocument();
	});

	it('displays current config values', () => {
		const onChange = vi.fn();
		render(<CapitalConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const capitalInput = screen.getByLabelText(/Capital per Trade/i) as HTMLInputElement;
		expect(capitalInput.value).toBe('200000');
	});

	it('calls onChange when capital is changed', () => {
		const onChange = vi.fn();
		render(<CapitalConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const capitalInput = screen.getByLabelText(/Capital per Trade/i);
		fireEvent.change(capitalInput, { target: { value: '250000' } });

		expect(onChange).toHaveBeenCalledWith({ user_capital: 250000 });
	});

	it('calls onChange when max portfolio size is changed', () => {
		const onChange = vi.fn();
		render(<CapitalConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const portfolioSizeInput = screen.getByLabelText(/Max Portfolio Size/i);
		fireEvent.change(portfolioSizeInput, { target: { value: '8' } });

		expect(onChange).toHaveBeenCalledWith({ max_portfolio_size: 8 });
	});

	it('shows impact summary when portfolio size changes', () => {
		const onChange = vi.fn();
		const modifiedConfig = { ...mockConfig, max_portfolio_size: 8 };
		render(<CapitalConfigSection config={modifiedConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		expect(screen.getByText(/Configuration Impact/i)).toBeInTheDocument();
		expect(screen.getByText(/Allows 2 more concurrent position/i)).toBeInTheDocument();
	});

	it('shows capital change indicator', () => {
		const onChange = vi.fn();
		const modifiedConfig = { ...mockConfig, user_capital: 250000 };
		render(<CapitalConfigSection config={modifiedConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		expect(screen.getByText(/\+₹50,000 from default/i)).toBeInTheDocument();
	});
});
