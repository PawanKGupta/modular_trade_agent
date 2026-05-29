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
		expect(capitalInput.value).toBe('100000');
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

	it('uses fallback values when numeric inputs are cleared', () => {
		const onChange = vi.fn();
		render(<CapitalConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		fireEvent.change(screen.getByLabelText(/Capital per Trade/i), { target: { value: '' } });
		expect(onChange).toHaveBeenCalledWith({ user_capital: 200000 });

		fireEvent.change(screen.getByLabelText(/Paper Trading Initial Capital/i), { target: { value: '' } });
		expect(onChange).toHaveBeenCalledWith({ paper_trading_initial_capital: 300000 });

		fireEvent.change(screen.getByLabelText(/Max Portfolio Size/i), { target: { value: '' } });
		expect(onChange).toHaveBeenCalledWith({ max_portfolio_size: 6 });
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
		const { container } = render(<CapitalConfigSection config={modifiedConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		// Capital change: 250000 - 100000 = 150000
		// The number is formatted as "1,50,000" (Indian locale) in the component
		// Check that the change indicator text exists in the rendered component
		expect(container.textContent).toMatch(/Rs.*1,50,000.*from default/i);
	});

	it('updates paper trading initial capital', () => {
		const onChange = vi.fn();
		render(<CapitalConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		fireEvent.change(screen.getByLabelText(/Paper Trading Initial Capital/i), {
			target: { value: '500000' },
		});

		expect(onChange).toHaveBeenCalledWith({ paper_trading_initial_capital: 500000 });
	});

	it('shows negative paper capital and portfolio reduction impact', () => {
		const onChange = vi.fn();
		const modifiedConfig = {
			...mockConfig,
			paper_trading_initial_capital: 200000,
			max_portfolio_size: 4,
		};
		render(<CapitalConfigSection config={modifiedConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		expect(screen.getByText(/Starting balance for paper trading simulation/i)).toBeInTheDocument();
		expect(screen.getByText(/-2 positions from default/i)).toBeInTheDocument();
	});

	it('shows positive paper capital change indicator', () => {
		const onChange = vi.fn();
		const modifiedConfig = { ...mockConfig, paper_trading_initial_capital: 1200000 };
		const { container } = render(
			<CapitalConfigSection config={modifiedConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />
		);

		expect(screen.getByText(/Starting balance for paper trading simulation/i)).toBeInTheDocument();
		expect(container.textContent).toMatch(/Rs.*2,00,000.*from default/i);
	});

	it('shows negative user capital change indicator', () => {
		const onChange = vi.fn();
		const modifiedConfig = { ...mockConfig, user_capital: 50000 };
		const { container } = render(
			<CapitalConfigSection config={modifiedConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />
		);
		expect(container.textContent).toMatch(/Rs.*50,000.*from default/i);
	});
});
