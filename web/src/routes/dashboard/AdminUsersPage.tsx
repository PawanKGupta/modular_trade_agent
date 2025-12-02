import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createUser, deleteUser, listUsers, updateUser, type AdminUser, type CreateUserPayload } from '@/api/admin';
import { useSessionStore } from '@/state/sessionStore';

export function AdminUsersPage() {
	const { isAdmin, refresh } = useSessionStore();

	useEffect(() => {
		// Ensure session is loaded if page is hit directly
		refresh().catch(() => {});
	}, []);

	const qc = useQueryClient();
	const { data, isLoading, isError } = useQuery({
		queryKey: ['admin-users'],
		queryFn: listUsers,
		enabled: isAdmin,
	});

	const [newUser, setNewUser] = useState<CreateUserPayload>({ email: '', password: '', name: '', role: 'user' });

	const createMut = useMutation({
		mutationFn: createUser,
		onSuccess: () => {
			setNewUser({ email: '', password: '', name: '', role: 'user' });
			qc.invalidateQueries({ queryKey: ['admin-users'] });
		},
	});
	const updateMut = useMutation({
		mutationFn: ({ id, payload }: { id: number; payload: Partial<AdminUser> & { password?: string } }) =>
			updateUser(id, payload),
		onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
	});
	const deleteMut = useMutation({
		mutationFn: (id: number) => deleteUser(id),
		onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
	});

	useEffect(() => {
		document.title = 'Admin - Users';
	}, []);

	if (!isAdmin) {
		return <div className="p-2 sm:p-4 text-xs sm:text-sm text-red-600">You do not have permission to view this page.</div>;
	}

	return (
		<div className="p-2 sm:p-4 space-y-4 sm:space-y-6">
			<h1 className="text-lg sm:text-xl font-semibold text-[var(--text)]">Users</h1>

			<div className="bg-[var(--panel)] border border-[#1e293b] rounded p-3 sm:p-4">
				<h2 className="text-sm sm:text-base font-medium mb-2 text-[var(--text)]">Create user</h2>
				<div className="flex flex-col gap-2 max-w-xl">
					<input
						className="bg-[#0f1720] border border-[#1e293b] rounded px-3 py-2 sm:px-2 sm:py-1 text-sm text-[var(--text)] placeholder:text-[var(--muted)] min-h-[44px] sm:min-h-0"
						type="email"
						placeholder="Email"
						value={newUser.email}
						onChange={(e) => setNewUser((s) => ({ ...s, email: e.target.value }))}
					/>
					<input
						className="bg-[#0f1720] border border-[#1e293b] rounded px-3 py-2 sm:px-2 sm:py-1 text-sm text-[var(--text)] placeholder:text-[var(--muted)] min-h-[44px] sm:min-h-0"
						type="password"
						placeholder="Password"
						value={newUser.password}
						onChange={(e) => setNewUser((s) => ({ ...s, password: e.target.value }))}
					/>
					<input
						className="bg-[#0f1720] border border-[#1e293b] rounded px-3 py-2 sm:px-2 sm:py-1 text-sm text-[var(--text)] placeholder:text-[var(--muted)] min-h-[44px] sm:min-h-0"
						type="text"
						placeholder="Name (optional)"
						value={newUser.name}
						onChange={(e) => setNewUser((s) => ({ ...s, name: e.target.value }))}
					/>
					<select
						className="bg-[#0f1720] border border-[#1e293b] rounded px-3 py-2 sm:px-2 sm:py-1 w-full sm:w-40 text-sm text-[var(--text)] min-h-[44px] sm:min-h-0"
						value={newUser.role ?? 'user'}
						onChange={(e) => setNewUser((s) => ({ ...s, role: e.target.value as 'user' | 'admin' }))}
					>
						<option value="user">user</option>
						<option value="admin">admin</option>
					</select>
					<button
						className="bg-blue-600 text-white rounded px-3 py-1 w-32 disabled:opacity-50"
						onClick={() => createMut.mutate(newUser)}
						disabled={!newUser.email || !newUser.password || createMut.isPending}
					>
						{createMut.isPending ? 'Creating...' : 'Create'}
					</button>
					{createMut.isError && <div className="text-red-400 text-sm">Create failed</div>}
				</div>
			</div>

			<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
				<div className="flex items-center justify-between px-4 py-2 border-b border-[#1e293b]">
					<h2 className="font-medium text-[var(--text)]">All users</h2>
					{isLoading && <span className="text-sm text-[var(--muted)]">Loading...</span>}
					{isError && <span className="text-sm text-red-400">Error loading users</span>}
				</div>
				<table className="w-full text-sm">
					<thead className="bg-[#0f172a] text-[var(--muted)]">
						<tr>
							<th className="text-left p-2">Email</th>
							<th className="text-left p-2">Name</th>
							<th className="text-left p-2">Role</th>
							<th className="text-left p-2">Active</th>
							<th className="text-left p-2">Actions</th>
						</tr>
					</thead>
					<tbody>
						{(data ?? []).map((u) => (
							<tr key={u.id} className="border-t border-[#1e293b]">
								<td className="p-2 text-[var(--text)]">{u.email}</td>
								<td className="p-2 text-[var(--text)]">{u.name ?? '-'}</td>
								<td className="p-2">
									<select
										className="bg-[#0f1720] border border-[#1e293b] rounded px-2 py-1 text-[var(--text)]"
										value={u.role}
										onChange={(e) => updateMut.mutate({ id: u.id, payload: { role: e.target.value as any } })}
									>
										<option value="user">user</option>
										<option value="admin">admin</option>
									</select>
								</td>
								<td className="p-2">
									<input
										type="checkbox"
										checked={u.is_active}
										onChange={(e) => updateMut.mutate({ id: u.id, payload: { is_active: e.target.checked } })}
										className="accent-blue-600"
									/>
								</td>
								<td className="p-2">
									<button
										className="text-red-400 hover:text-red-300 hover:underline disabled:opacity-50"
										onClick={() => deleteMut.mutate(u.id)}
										disabled={deleteMut.isPending}
									>
										Delete
									</button>
								</td>
							</tr>
						))}
						{(data ?? []).length === 0 && !isLoading && (
							<tr>
								<td className="p-2 text-[var(--muted)]" colSpan={5}>
									No users found
								</td>
							</tr>
						)}
					</tbody>
				</table>
			</div>
		</div>
	);
}

export default AdminUsersPage;
