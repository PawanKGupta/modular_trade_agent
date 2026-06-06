import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { listUsers, type AdminUser } from '@/api/admin';

const SEARCH_DEBOUNCE_MS = 280;
const SEARCH_LIMIT = 40;

type Props = {
	value: string;
	onChange: (userId: string) => void;
	placeholder?: string;
};

export function UserAutocomplete({ value, onChange, placeholder = 'Search name, email, or id…' }: Props) {
	const [isOpen, setIsOpen] = useState(false);
	const [searchTerm, setSearchTerm] = useState('');
	const [debouncedSearch, setDebouncedSearch] = useState('');

	useEffect(() => {
		const t = window.setTimeout(() => setDebouncedSearch(searchTerm.trim()), SEARCH_DEBOUNCE_MS);
		return () => window.clearTimeout(t);
	}, [searchTerm]);

	const searchEnabled = debouncedSearch.length >= 1;

	const { data: searchResults = [], isFetching: searchLoading } = useQuery<AdminUser[]>({
		queryKey: ['admin-users-search', debouncedSearch, SEARCH_LIMIT],
		queryFn: () => listUsers({ q: debouncedSearch, limit: SEARCH_LIMIT }),
		enabled: searchEnabled,
	});

	const idLookupEnabled = Boolean(value && /^\d+$/.test(value.trim()));

	const { data: idLookupResults = [] } = useQuery<AdminUser[]>({
		queryKey: ['admin-users-search', `resolve:${value}`, SEARCH_LIMIT],
		queryFn: () => listUsers({ q: value.trim(), limit: SEARCH_LIMIT }),
		enabled: idLookupEnabled,
	});

	const selectedUser = useMemo(() => {
		if (!value || !/^\d+$/.test(value.trim())) return null;
		const id = Number(value);
		if (!Number.isInteger(id)) return null;
		return (
			idLookupResults.find((u) => u.id === id) ??
			searchResults.find((u) => u.id === id) ??
			null
		);
	}, [value, idLookupResults, searchResults]);

	// When a user id is selected, show their label. Do not clear `searchTerm` when `value`
	// becomes empty from typing (parent clears id) — keep the typed query for search.
	useEffect(() => {
		if (!value) return;
		if (selectedUser) {
			setSearchTerm(selectedUser.name || selectedUser.email || String(selectedUser.id));
		}
	}, [value, selectedUser]);

	const showDropdown = isOpen && searchEnabled;
	const listLoading = searchLoading;
	const showHint = isOpen && !searchEnabled && !value;
	const noHits = showDropdown && !listLoading && searchResults.length === 0;

	return (
		<div className="relative min-w-[14rem] flex-1 sm:max-w-md">
			<div className="flex gap-1">
				<input
					type="text"
					value={searchTerm}
					onChange={(e) => {
						setSearchTerm(e.target.value);
						setIsOpen(true);
						if (selectedUser && e.target.value !== (selectedUser.name || selectedUser.email || value)) {
							onChange('');
						}
					}}
					onFocus={() => setIsOpen(true)}
					onBlur={() => {
						window.setTimeout(() => setIsOpen(false), 200);
					}}
					placeholder={placeholder}
					className="bg-[#0f172a] border border-[#1f2937] rounded px-3 py-2 sm:px-2 sm:py-1 min-h-[44px] sm:min-h-0 w-full flex-1"
					autoComplete="off"
				/>
				{value && (
					<button
						type="button"
						onClick={() => {
							onChange('');
							setSearchTerm('');
							setIsOpen(false);
						}}
						className="px-2 text-red-400 hover:text-red-300 transition-colors shrink-0"
						title="Clear selection"
					>
						×
					</button>
				)}
			</div>
			{showHint && (
				<div className="absolute z-20 w-full mt-1 bg-[#0f172a] border border-[#1f2937] rounded shadow-lg px-3 py-2 text-xs text-[var(--muted)]">
					Type at least one character to search users.
				</div>
			)}
			{showDropdown && listLoading && (
				<div className="absolute z-20 w-full mt-1 bg-[#0f172a] border border-[#1f2937] rounded shadow-lg px-3 py-2 text-xs text-[var(--muted)]">
					Searching…
				</div>
			)}
			{showDropdown && !listLoading && searchResults.length > 0 && (
				<div className="absolute z-20 w-full mt-1 bg-[#0f172a] border border-[#1f2937] rounded shadow-lg max-h-48 overflow-y-auto">
					{searchResults.map((user) => (
						<button
							key={user.id}
							type="button"
							onClick={() => {
								onChange(user.id.toString());
								setIsOpen(false);
								setSearchTerm(user.name || user.email || String(user.id));
							}}
							className="w-full text-left px-3 py-2 text-xs sm:text-sm hover:bg-[#1a2332] transition-colors"
						>
							<div className="font-semibold">{user.name || user.email}</div>
							<div className="text-[var(--muted)] text-xs">
								{user.email && user.name ? user.email : null}
								{user.email && !user.name ? `ID: ${user.id}` : null}
							</div>
						</button>
					))}
				</div>
			)}
			{noHits && (
				<div className="absolute z-20 w-full mt-1 bg-[#0f172a] border border-[#1f2937] rounded shadow-lg px-3 py-2 text-xs text-[var(--muted)]">
					No users found
				</div>
			)}
		</div>
	);
}
