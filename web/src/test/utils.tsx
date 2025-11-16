import { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

export function withProviders(ui: ReactNode) {
	const client = new QueryClient();
	return (
		<QueryClientProvider client={client}>
			{ui}
		</QueryClientProvider>
	);
}
