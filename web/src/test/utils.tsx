import { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

export function withProviders(ui: ReactNode) {
	const client = new QueryClient({
		defaultOptions: {
			queries: {
				retry: false,
				refetchOnWindowFocus: false,
			},
		},
	});
	return (
		<QueryClientProvider client={client}>
			{ui}
		</QueryClientProvider>
	);
}
