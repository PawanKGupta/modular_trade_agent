import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { OrderConfigSection } from '../dashboard/OrderConfigSection';
import { DEFAULT_CONFIG, type TradingConfig } from '@/api/trading-config';

const mockConfig: TradingConfig = {
	...DEFAULT_CONFIG,
};

describe('OrderConfigSection', () => {
	it('renders all order default fields', () => {
		const onChange = vi.fn();
		render(<OrderConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		expect(screen.getByText(/Order Defaults/i)).toBeInTheDocument();
		expect(screen.getByLabelText(/Default Exchange/i)).toBeInTheDocument();
		expect(screen.getByLabelText(/Default Product/i)).toBeInTheDocument();
		expect(screen.getByLabelText(/Default Order Type/i)).toBeInTheDocument();
		expect(screen.getByLabelText(/Default Variety/i)).toBeInTheDocument();
		expect(screen.getByLabelText(/Default Validity/i)).toBeInTheDocument();
	});

	it('displays current config values', () => {
		const onChange = vi.fn();
		render(<OrderConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const exchangeSelect = screen.getByLabelText(/Default Exchange/i) as HTMLSelectElement;
		expect(exchangeSelect.value).toBe('NSE');
	});

	it('calls onChange when exchange is changed', () => {
		const onChange = vi.fn();
		render(<OrderConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const exchangeSelect = screen.getByLabelText(/Default Exchange/i);
		fireEvent.change(exchangeSelect, { target: { value: 'BSE' } });

		expect(onChange).toHaveBeenCalledWith({ default_exchange: 'BSE' });
	});

	it('calls onChange when product is changed', () => {
		const onChange = vi.fn();
		render(<OrderConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const productSelect = screen.getByLabelText(/Default Product/i);
		fireEvent.change(productSelect, { target: { value: 'MIS' } });

		expect(onChange).toHaveBeenCalledWith({ default_product: 'MIS' });
	});

	it('calls onChange when order type is changed', () => {
		const onChange = vi.fn();
		render(<OrderConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const orderTypeSelect = screen.getByLabelText(/Default Order Type/i);
		fireEvent.change(orderTypeSelect, { target: { value: 'LIMIT' } });

		expect(onChange).toHaveBeenCalledWith({ default_order_type: 'LIMIT' });
	});

	it('calls onChange when variety is changed', () => {
		const onChange = vi.fn();
		render(<OrderConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const varietySelect = screen.getByLabelText(/Default Variety/i);
		fireEvent.change(varietySelect, { target: { value: 'REGULAR' } });

		expect(onChange).toHaveBeenCalledWith({ default_variety: 'REGULAR' });
	});

	it('calls onChange when validity is changed', () => {
		const onChange = vi.fn();
		render(<OrderConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const validitySelect = screen.getByLabelText(/Default Validity/i);
		fireEvent.change(validitySelect, { target: { value: 'IOC' } });

		expect(onChange).toHaveBeenCalledWith({ default_validity: 'IOC' });
	});

	it('displays all available options for each select', () => {
		const onChange = vi.fn();
		render(<OrderConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		// Check exchange options
		const exchangeSelect = screen.getByLabelText(/Default Exchange/i);
		expect(exchangeSelect.querySelector('option[value="NSE"]')).toBeInTheDocument();
		expect(exchangeSelect.querySelector('option[value="BSE"]')).toBeInTheDocument();

		// Check product options
		const productSelect = screen.getByLabelText(/Default Product/i);
		expect(productSelect.querySelector('option[value="CNC"]')).toBeInTheDocument();
		expect(productSelect.querySelector('option[value="MIS"]')).toBeInTheDocument();
		expect(productSelect.querySelector('option[value="NRML"]')).toBeInTheDocument();
	});
});
