import { useEffect, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { helpPath } from './helpNav';

interface HelpPageProps {
	title: string;
	children: ReactNode;
}

/** Sets document title and wraps help article content with consistent spacing. */
export function HelpPage({ title, children }: HelpPageProps) {
	useEffect(() => {
		document.title = `${title} — Help — Rebound`;
	}, [title]);

	return (
		<article className="max-w-3xl space-y-4 text-sm sm:text-base leading-relaxed text-[var(--text)]">
			<h1 className="text-xl sm:text-2xl font-semibold mb-2">{title}</h1>
			{children}
		</article>
	);
}

export function HelpSection({ title, children }: { title: string; children: ReactNode }) {
	return (
		<section className="space-y-3">
			<h2 className="text-lg font-semibold pt-4 border-t border-[#1e293b]/60 first:border-0 first:pt-0">
				{title}
			</h2>
			{children}
		</section>
	);
}

export function HelpMuted({ children }: { children: ReactNode }) {
	return <p className="text-[var(--muted)]">{children}</p>;
}

export function HelpList({ items }: { items: ReactNode[] }) {
	return (
		<ol className="list-decimal list-inside space-y-2 pl-1">
			{items.map((item, index) => (
				<li key={index} className="pl-1">
					{item}
				</li>
			))}
		</ol>
	);
}

export function HelpBullets({ items }: { items: ReactNode[] }) {
	return (
		<ul className="list-disc list-inside space-y-1.5 pl-1 text-[var(--muted)]">
			{items.map((item, index) => (
				<li key={index} className="pl-1">
					{item}
				</li>
			))}
		</ul>
	);
}

export function HelpTable({
	headers,
	rows,
}: {
	headers: [string, string];
	rows: [ReactNode, ReactNode][];
}) {
	return (
		<div className="overflow-x-auto rounded border border-[#1e293b]">
			<table className="w-full text-xs sm:text-sm">
				<thead>
					<tr className="bg-[#0f172a]/80 text-left">
						<th className="px-3 py-2 font-medium">{headers[0]}</th>
						<th className="px-3 py-2 font-medium">{headers[1]}</th>
					</tr>
				</thead>
				<tbody>
					{rows.map(([a, b], index) => (
						<tr key={index} className="border-t border-[#1e293b]">
							<td className="px-3 py-2 align-top font-medium">{a}</td>
							<td className="px-3 py-2 align-top text-[var(--muted)]">{b}</td>
						</tr>
					))}
				</tbody>
			</table>
		</div>
	);
}

export function HelpCallout({ children }: { children: ReactNode }) {
	return (
		<div className="rounded border border-[#1e293b] bg-[#0f172a]/50 px-4 py-3 text-[var(--muted)] text-sm">
			{children}
		</div>
	);
}

export function HelpInternalLink({ slug, children }: { slug: string; children: ReactNode }) {
	return (
		<Link to={helpPath(slug)} className="text-[var(--accent)] hover:underline">
			{children}
		</Link>
	);
}

export function HelpAppLink({ to, children }: { to: string; children: ReactNode }) {
	return (
		<Link to={to} className="text-[var(--accent)] hover:underline">
			{children}
		</Link>
	);
}
