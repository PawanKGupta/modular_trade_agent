import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ContextViewer } from '../dashboard/ContextViewer';
import { vi } from 'vitest';

vi.mock('react-syntax-highlighter', () => ({
	Prism: ({ children }: { children: string }) => <pre>{children}</pre>,
	default: ({ children }: { children: string }) => <pre>{children}</pre>,
}));

vi.mock('react-syntax-highlighter/dist/esm/styles/prism', () => ({
	vscDarkPlus: {},
}));

describe('ContextViewer', () => {
	it('returns null when context is empty', () => {
		const { container } = render(<ContextViewer context={null} />);
		expect(container.firstChild).toBeNull();
	});

	it('expands context with stack trace and highlights search', () => {
		render(
			<ContextViewer
				context={{
					action: 'retry',
					exc_info: true,
					exc_text: 'ValueError: boom',
					detail: 'extra',
				}}
				searchTerm="boom"
			/>
		);

		fireEvent.click(screen.getByRole('button', { name: /Show Context/i }));
		expect(screen.getByText('retry')).toBeInTheDocument();
		expect(screen.getByText(/Exception Info Present/i)).toBeInTheDocument();
		expect(screen.getByText(/Full Context/i)).toBeInTheDocument();
	});
});
