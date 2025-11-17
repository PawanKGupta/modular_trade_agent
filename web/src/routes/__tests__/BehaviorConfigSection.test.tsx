import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { BehaviorConfigSection } from '../dashboard/BehaviorConfigSection';
import { DEFAULT_CONFIG, type TradingConfig } from '@/api/trading-config';

const mockConfig: TradingConfig = {
	...DEFAULT_CONFIG,
};

describe('BehaviorConfigSection', () => {
	it('renders all behavior settings', () => {
		const onChange = vi.fn();
		render(<BehaviorConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		expect(screen.getByText(/Behavior Settings/i)).toBeInTheDocument();
		expect(screen.getByText(/Allow Duplicate Recommendations Same Day/i)).toBeInTheDocument();
		expect(screen.getByText(/Exit on EMA9 or RSI50/i)).toBeInTheDocument();
		expect(screen.getByText(/Min Combined Score/i)).toBeInTheDocument();
	});

	it('displays current checkbox states', () => {
		const onChange = vi.fn();
		render(<BehaviorConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const duplicateCheckbox = screen.getByLabelText(/Allow Duplicate Recommendations Same Day/i) as HTMLInputElement;
		expect(duplicateCheckbox.checked).toBe(false);

		const exitCheckbox = screen.getByLabelText(/Exit on EMA9 or RSI50/i) as HTMLInputElement;
		expect(exitCheckbox.checked).toBe(true);
	});

	it('calls onChange when checkbox is toggled', () => {
		const onChange = vi.fn();
		render(<BehaviorConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const duplicateCheckbox = screen.getByLabelText(/Allow Duplicate Recommendations Same Day/i);
		fireEvent.click(duplicateCheckbox);

		expect(onChange).toHaveBeenCalledWith({ allow_duplicate_recommendations_same_day: true });
	});

	it('calls onChange when min combined score is changed', () => {
		const onChange = vi.fn();
		render(<BehaviorConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const scoreInput = screen.getByLabelText(/Min Combined Score/i);
		fireEvent.change(scoreInput, { target: { value: '60' } });

		expect(onChange).toHaveBeenCalledWith({ min_combined_score: 60 });
	});

	it('shows news sentiment section', () => {
		const onChange = vi.fn();
		render(<BehaviorConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		expect(screen.getByRole('heading', { name: /^News Sentiment$/i })).toBeInTheDocument();
		expect(screen.getByLabelText(/Enable News Sentiment Analysis/i)).toBeInTheDocument();
	});

	it('hides news sentiment fields when disabled', () => {
		const onChange = vi.fn();
		render(<BehaviorConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const newsCheckbox = screen.getByLabelText(/Enable News Sentiment Analysis/i) as HTMLInputElement;
		expect(newsCheckbox.checked).toBe(false);

		// News sentiment fields should not be visible when disabled
		expect(screen.queryByLabelText(/Lookback Days/i)).not.toBeInTheDocument();
	});

	it('shows news sentiment fields when enabled', () => {
		const onChange = vi.fn();
		const configWithNews = { ...mockConfig, news_sentiment_enabled: true };
		render(<BehaviorConfigSection config={configWithNews} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		expect(screen.getByLabelText(/Lookback Days/i)).toBeInTheDocument();
		expect(screen.getByLabelText(/Min Articles/i)).toBeInTheDocument();
		expect(screen.getByLabelText(/Positive Threshold/i)).toBeInTheDocument();
		expect(screen.getByLabelText(/Negative Threshold/i)).toBeInTheDocument();
	});

	it('calls onChange when news sentiment is toggled', () => {
		const onChange = vi.fn();
		render(<BehaviorConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const newsCheckbox = screen.getByLabelText(/Enable News Sentiment Analysis/i);
		fireEvent.click(newsCheckbox);

		expect(onChange).toHaveBeenCalledWith({ news_sentiment_enabled: true });
	});

	it('calls onChange when news sentiment fields are changed', () => {
		const onChange = vi.fn();
		const configWithNews = { ...mockConfig, news_sentiment_enabled: true };
		render(<BehaviorConfigSection config={configWithNews} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const lookbackInput = screen.getByLabelText(/Lookback Days/i);
		fireEvent.change(lookbackInput, { target: { value: '14' } });

		expect(onChange).toHaveBeenCalledWith({ news_sentiment_lookback_days: 14 });
	});

	it('shows ML configuration section', () => {
		const onChange = vi.fn();
		render(<BehaviorConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		expect(screen.getByText(/ML Configuration/i)).toBeInTheDocument();
		expect(screen.getByText(/Enable ML Predictions/i)).toBeInTheDocument();
	});

	it('hides ML fields when disabled', () => {
		const onChange = vi.fn();
		render(<BehaviorConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const mlCheckbox = screen.getByLabelText(/Enable ML Predictions/i) as HTMLInputElement;
		expect(mlCheckbox.checked).toBe(false);

		// ML fields should not be visible when disabled
		expect(screen.queryByLabelText(/ML Model Version/i)).not.toBeInTheDocument();
	});

	it('shows ML fields when enabled', () => {
		const onChange = vi.fn();
		const configWithML = { ...mockConfig, ml_enabled: true };
		render(<BehaviorConfigSection config={configWithML} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		expect(screen.getByLabelText(/ML Model Version/i)).toBeInTheDocument();
		expect(screen.getByLabelText(/Confidence Threshold/i)).toBeInTheDocument();
		expect(screen.getByText(/Combine ML with Rule-Based Logic/i)).toBeInTheDocument();
	});

	it('calls onChange when ML is toggled', () => {
		const onChange = vi.fn();
		render(<BehaviorConfigSection config={mockConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const mlCheckbox = screen.getByLabelText(/Enable ML Predictions/i);
		fireEvent.click(mlCheckbox);

		expect(onChange).toHaveBeenCalledWith({ ml_enabled: true });
	});

	it('calls onChange when ML fields are changed', () => {
		const onChange = vi.fn();
		const configWithML = { ...mockConfig, ml_enabled: true };
		render(<BehaviorConfigSection config={configWithML} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const modelVersionInput = screen.getByLabelText(/ML Model Version/i);
		fireEvent.change(modelVersionInput, { target: { value: 'v2.0' } });

		expect(onChange).toHaveBeenCalledWith({ ml_model_version: 'v2.0' });
	});

	it('handles null ML model version', () => {
		const onChange = vi.fn();
		const configWithML = { ...mockConfig, ml_enabled: true, ml_model_version: 'v1.0' };
		render(<BehaviorConfigSection config={configWithML} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const modelVersionInput = screen.getByLabelText(/ML Model Version/i) as HTMLInputElement;
		expect(modelVersionInput.value).toBe('v1.0');

		// Clear the value
		fireEvent.change(modelVersionInput, { target: { value: '' } });
		expect(onChange).toHaveBeenCalledWith({ ml_model_version: null });
	});

	it('calls onChange when ML combine checkbox is toggled', () => {
		const onChange = vi.fn();
		const configWithML = { ...mockConfig, ml_enabled: true };
		render(<BehaviorConfigSection config={configWithML} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const combineCheckbox = screen.getByLabelText(/Combine ML with Rule-Based Logic/i);
		fireEvent.click(combineCheckbox);

		expect(onChange).toHaveBeenCalledWith({ ml_combine_with_rules: false });
	});

	it('shows asterisk for modified fields', () => {
		const onChange = vi.fn();
		const modifiedConfig = { ...mockConfig, min_combined_score: 60 };
		render(<BehaviorConfigSection config={modifiedConfig} defaultConfig={DEFAULT_CONFIG} onChange={onChange} />);

		const scoreLabel = screen.getByText(/Min Combined Score/i);
		expect(scoreLabel.textContent).toContain('*');
	});
});
