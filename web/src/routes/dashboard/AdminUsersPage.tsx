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
		document.title = 'Admin • Users';
	}, []);

	if (!isAdmin) {
		return <div className="p-4 text-sm text-red-600">You do not have permission to view this page.</div>;
	}

	return (
		<div className="p-4 space-y-6">
			<h1 className="text-xl font-semibold">Users</h1>

			<div className="rounded border p-4">
				<h2 className="font-medium mb-2">Create user</h2>
				<div className="flex flex-col gap-2 max-w-xl">
					<input
						className="border rounded px-2 py-1"
						type="email"
						placeholder="Email"
						value={newUser.email}
						onChange={(e) => setNewUser((s) => ({ ...s, email: e.target.value }))}
					/>
					<input
						className="border rounded px-2 py-1"
						type="password"
						placeholder="Password"
						value={newUser.password}
						onChange={(e) => setNewUser((s) => ({ ...s, password: e.target.value }))}
					/>
					<input
						className="border rounded px-2 py-1"
						type="text"
						placeholder="Name (optional)"
						value={newUser.name}
						onChange={(e) => setNewUser((s) => ({ ...s, name: e.target.value }))}
					/>
					<select
						className="border rounded px-2 py-1 w-40"
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
					{createMut.isError && <div className="text-red-600 text-sm">Create failed</div>}
				</div>
			</div>

			<div className="rounded border">
				<div className="flex items-center justify-between px-4 py-2 border-b">
					<h2 className="font-medium">All users</h2>
					{isLoading && <span className="text-sm text-gray-500">Loading...</span>}
					{isError && <span className="text-sm text-red-600">Error loading users</span>}
				</div>
				<table className="w-full text-sm">
					<thead className="bg-gray-50">
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
							<tr key={u.id} className="border-t">
								<td className="p-2">{u.email}</td>
								<td className="p-2">{u.name ?? '-'}</td>
								<td className="p-2">
									<select
										className="border rounded px-2 py-1"
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
									/>
								</td>
								<td className="p-2">
									<button
										className="text-red-600 hover:underline disabled:opacity-50"
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
								<td className="p-2 text-gray-500" colSpan={5}>
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
