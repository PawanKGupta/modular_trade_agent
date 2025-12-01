import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import {
	getNotifications,
	getUnreadNotifications,
	markNotificationRead,
	markAllNotificationsRead,
	type Notification,
} from '@/api/notifications';

export function NotificationsPage() {
	const qc = useQueryClient();
	const [filter, setFilter] = useState<'all' | 'unread' | 'service' | 'trading' | 'system' | 'error'>('all');
	const [levelFilter, setLevelFilter] = useState<'all' | 'info' | 'warning' | 'error' | 'critical'>('all');

	const { data: notifications, isLoading } = useQuery<Notification[]>({
		queryKey: ['notifications', filter, levelFilter],
		queryFn: () => {
			if (filter === 'unread') {
				return getUnreadNotifications(100);
			}
			return getNotifications({
				type: filter !== 'all' ? filter : undefined,
				level: levelFilter !== 'all' ? levelFilter : undefined,
				limit: 100,
			});
		},
		refetchInterval: 30000, // Refetch every 30 seconds
	});

	const markReadMutation = useMutation({
		mutationFn: markNotificationRead,
		onSuccess: () => {
			qc.invalidateQueries({ queryKey: ['notifications'] });
		},
	});

	const markAllReadMutation = useMutation({
		mutationFn: markAllNotificationsRead,
		onSuccess: () => {
			qc.invalidateQueries({ queryKey: ['notifications'] });
		},
	});

	useEffect(() => {
		document.title = 'Notifications';
	}, []);

	const handleMarkRead = (notificationId: number) => {
		markReadMutation.mutate(notificationId);
	};

	const handleMarkAllRead = () => {
		markAllReadMutation.mutate();
	};

	const getLevelColor = (level: string) => {
		switch (level) {
			case 'error':
			case 'critical':
				return 'text-red-400';
			case 'warning':
				return 'text-yellow-400';
			case 'info':
				return 'text-blue-400';
			default:
				return 'text-[var(--text)]';
		}
	};

	const getLevelIcon = (level: string) => {
		switch (level) {
			case 'error':
			case 'critical':
				return '❌';
			case 'warning':
				return '⚠️';
			case 'info':
				return 'ℹ️';
			default:
				return '📢';
		}
	};

	if (isLoading) {
		return (
			<div className="p-4">
				<h1 className="text-2xl font-semibold mb-4">Notifications</h1>
				<div className="text-[var(--muted)]">Loading notifications...</div>
			</div>
		);
	}

	const unreadCount = notifications?.filter((n) => !n.read).length || 0;

	return (
		<div className="p-4 space-y-4 max-w-6xl">
			<div className="flex items-center justify-between">
				<h1 className="text-2xl font-semibold">Notifications</h1>
				{unreadCount > 0 && (
					<button
						onClick={handleMarkAllRead}
						disabled={markAllReadMutation.isPending}
						className="px-4 py-2 rounded bg-[var(--accent)] text-black hover:bg-[var(--accent-hover)] disabled:opacity-50"
					>
						{markAllReadMutation.isPending ? 'Marking...' : `Mark All Read (${unreadCount})`}
					</button>
				)}
			</div>

			{/* Filters */}
			<div className="flex gap-4 p-4 border border-[#1e293b] rounded">
				<div className="flex-1">
					<label className="block text-sm mb-1">Type</label>
					<select
						value={filter}
						onChange={(e) => setFilter(e.target.value as any)}
						className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm"
					>
						<option value="all">All</option>
						<option value="unread">Unread</option>
						<option value="service">Service</option>
						<option value="trading">Trading</option>
						<option value="system">System</option>
						<option value="error">Error</option>
					</select>
				</div>
				<div className="flex-1">
					<label className="block text-sm mb-1">Level</label>
					<select
						value={levelFilter}
						onChange={(e) => setLevelFilter(e.target.value as any)}
						className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm"
					>
						<option value="all">All</option>
						<option value="info">Info</option>
						<option value="warning">Warning</option>
						<option value="error">Error</option>
						<option value="critical">Critical</option>
					</select>
				</div>
			</div>

			{/* Notifications List */}
			<div className="space-y-2">
				{notifications && notifications.length > 0 ? (
					notifications.map((notification) => (
						<div
							key={notification.id}
							className={`p-4 border rounded ${
								notification.read
									? 'border-[#1e293b] bg-[#0f1720] opacity-60'
									: 'border-[#1e293b] bg-[#0f1720] border-l-4 border-l-blue-500'
							}`}
						>
							<div className="flex items-start justify-between">
								<div className="flex-1">
									<div className="flex items-center gap-2 mb-1">
										<span className="text-lg">{getLevelIcon(notification.level)}</span>
										<h3 className={`font-semibold ${getLevelColor(notification.level)}`}>
											{notification.title}
										</h3>
										{!notification.read && (
											<span className="px-2 py-0.5 text-xs rounded bg-blue-600 text-white">New</span>
										)}
									</div>
									<p className="text-sm text-[var(--muted)] mb-2 whitespace-pre-wrap">
										{notification.message}
									</p>
									<div className="flex items-center gap-4 text-xs text-[var(--muted)]">
										<span>
											{new Date(notification.created_at).toLocaleString()}
										</span>
										<span className="capitalize">{notification.type}</span>
										<span className="capitalize">{notification.level}</span>
									</div>
								</div>
								{!notification.read && (
									<button
										onClick={() => handleMarkRead(notification.id)}
										disabled={markReadMutation.isPending}
										className="ml-4 px-3 py-1 text-xs rounded bg-gray-600 hover:bg-gray-700 text-white disabled:opacity-50"
									>
										Mark Read
									</button>
								)}
							</div>
						</div>
					))
				) : (
					<div className="p-8 text-center text-[var(--muted)] border border-[#1e293b] rounded">
						No notifications found
					</div>
				)}
			</div>
		</div>
	);
}
