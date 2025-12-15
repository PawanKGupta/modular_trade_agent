import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { listUsers, type AdminUser } from '@/api/admin';

type Props = {
	value: string;
	onChange: (userId: string) => void;
	placeholder?: string;
};

export function UserAutocomplete({ value, onChange, placeholder = 'Any' }: Props) {
	const [isOpen, setIsOpen] = useState(false);
	const [searchTerm, setSearchTerm] = useState('');

	// Fetch users list
	const { data: users = [], isLoading } = useQuery<AdminUser[]>({
		queryKey: ['admin-users'],
		queryFn: listUsers,
	});

	// Filter users based on search term
	const filteredUsers = useMemo(() => {
		if (!searchTerm) {
			return users.slice(0, 10); // Show top 10 when empty
		}
		const term = searchTerm.toLowerCase();
		return users
			.filter(
				(user) =>
					user.id.toString().includes(term) ||
					user.email?.toLowerCase().includes(term) ||
					user.name?.toLowerCase().includes(term)
			)
			.slice(0, 10);
	}, [searchTerm, users]);

	// Get selected user info for display
	const selectedUser = useMemo(() => {
		if (!value) return null;
		return users.find((u) => u.id.toString() === value);
	}, [value, users]);

	// Update search term when value changes (for display)
	useEffect(() => {
		if (selectedUser) {
			setSearchTerm(selectedUser.name || selectedUser.email || value);
		} else if (value) {
			setSearchTerm(value);
		} else {
			setSearchTerm('');
		}
	}, [value, selectedUser]);

	const handleSelect = (user: AdminUser) => {
		onChange(user.id.toString());
		setIsOpen(false);
		setSearchTerm(user.name || user.email || user.id.toString());
	};

	const handleClear = () => {
		onChange('');
		setSearchTerm('');
		setIsOpen(false);
	};

	return (
		<div className="relative">
			<div className="flex gap-1">
				<input
					type="text"
					value={searchTerm}
					onChange={(e) => {
						setSearchTerm(e.target.value);
						setIsOpen(true);
						// Clear selection if user types something different
						if (selectedUser && e.target.value !== (selectedUser.name || selectedUser.email || value)) {
							onChange('');
						}
					}}
					onFocus={() => setIsOpen(true)}
					onBlur={() => {
						// Delay to allow click on dropdown item
						setTimeout(() => setIsOpen(false), 200);
					}}
					placeholder={placeholder}
					className="bg-[#0f172a] border border-[#1f2937] rounded px-3 py-2 sm:px-2 sm:py-1 min-h-[44px] sm:min-h-0 w-full sm:w-auto sm:min-w-[120px] flex-1"
					disabled={isLoading}
				/>
				{value && (
					<button
						type="button"
						onClick={handleClear}
						className="px-2 text-red-400 hover:text-red-300 transition-colors"
						title="Clear selection"
					>
						×
					</button>
				)}
			</div>
			{isOpen && !isLoading && filteredUsers.length > 0 && (
				<div className="absolute z-20 w-full mt-1 bg-[#0f172a] border border-[#1f2937] rounded shadow-lg max-h-48 overflow-y-auto">
					{filteredUsers.map((user) => (
						<button
							key={user.id}
							type="button"
							onClick={() => handleSelect(user)}
							className="w-full text-left px-3 py-2 text-xs sm:text-sm hover:bg-[#1a2332] transition-colors"
						>
							<div className="font-semibold">{user.name || user.email}</div>
							<div className="text-[var(--muted)] text-xs">
								{user.email && user.name && user.email}
								{user.email && !user.name && `ID: ${user.id}`}
							</div>
						</button>
					))}
				</div>
			)}
			{isOpen && !isLoading && filteredUsers.length === 0 && searchTerm && (
				<div className="absolute z-20 w-full mt-1 bg-[#0f172a] border border-[#1f2937] rounded shadow-lg px-3 py-2 text-xs text-[var(--muted)]">
					No users found
				</div>
			)}
			{isLoading && (
				<div className="absolute z-20 w-full mt-1 bg-[#0f172a] border border-[#1f2937] rounded shadow-lg px-3 py-2 text-xs text-[var(--muted)]">
					Loading users...
				</div>
			)}
		</div>
	);
}
