import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ServiceControls } from '../dashboard/ServiceControls';

describe('ServiceControls', () => {
	it('renders start and stop buttons', () => {
		const onStart = vi.fn();
		const onStop = vi.fn();

		render(
			<ServiceControls
				isRunning={false}
				onStart={onStart}
				onStop={onStop}
				isStarting={false}
				isStopping={false}
			/>
		);

		expect(screen.getByRole('button', { name: /Start Service/i })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: /Stop Service/i })).toBeInTheDocument();
	});

	it('disables start button when service is running', () => {
		const onStart = vi.fn();
		const onStop = vi.fn();

		render(
			<ServiceControls
				isRunning={true}
				onStart={onStart}
				onStop={onStop}
				isStarting={false}
				isStopping={false}
			/>
		);

		const startButton = screen.getByRole('button', { name: /Start Service/i });
		expect(startButton).toBeDisabled();
	});

	it('disables stop button when service is not running', () => {
		const onStart = vi.fn();
		const onStop = vi.fn();

		render(
			<ServiceControls
				isRunning={false}
				onStart={onStart}
				onStop={onStop}
				isStarting={false}
				isStopping={false}
			/>
		);

		const stopButton = screen.getByRole('button', { name: /Stop Service/i });
		expect(stopButton).toBeDisabled();
	});

	it('calls onStart when start button is clicked', () => {
		const onStart = vi.fn();
		const onStop = vi.fn();

		render(
			<ServiceControls
				isRunning={false}
				onStart={onStart}
				onStop={onStop}
				isStarting={false}
				isStopping={false}
			/>
		);

		const startButton = screen.getByRole('button', { name: /Start Service/i });
		fireEvent.click(startButton);

		expect(onStart).toHaveBeenCalledTimes(1);
		expect(onStop).not.toHaveBeenCalled();
	});

	it('calls onStop when stop button is clicked', () => {
		const onStart = vi.fn();
		const onStop = vi.fn();

		render(
			<ServiceControls
				isRunning={true}
				onStart={onStart}
				onStop={onStop}
				isStarting={false}
				isStopping={false}
			/>
		);

		const stopButton = screen.getByRole('button', { name: /Stop Service/i });
		fireEvent.click(stopButton);

		expect(onStop).toHaveBeenCalledTimes(1);
		expect(onStart).not.toHaveBeenCalled();
	});

	it('shows loading state when starting', () => {
		const onStart = vi.fn();
		const onStop = vi.fn();

		render(
			<ServiceControls
				isRunning={false}
				onStart={onStart}
				onStop={onStop}
				isStarting={true}
				isStopping={false}
			/>
		);

		expect(screen.getByText(/Starting.../i)).toBeInTheDocument();
		const startButton = screen.getByRole('button', { name: /Starting.../i });
		expect(startButton).toBeDisabled();
	});

	it('shows loading state when stopping', () => {
		const onStart = vi.fn();
		const onStop = vi.fn();

		render(
			<ServiceControls
				isRunning={true}
				onStart={onStart}
				onStop={onStop}
				isStarting={false}
				isStopping={true}
			/>
		);

		expect(screen.getByText(/Stopping.../i)).toBeInTheDocument();
		const stopButton = screen.getByRole('button', { name: /Stopping.../i });
		expect(stopButton).toBeDisabled();
	});
});
