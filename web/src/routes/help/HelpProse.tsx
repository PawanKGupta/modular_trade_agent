import { useEffect, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { helpPath } from './helpNav';

const HELP_LINK_CLASS =
	'text-[var(--accent)] hover:underline focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 focus:ring-offset-2 focus:ring-offset-[var(--bg)] rounded-sm';

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
			<h1 className="text-lg sm:text-xl font-semibold mb-2">{title}</h1>
			{children}
		</article>
	);
}

export function HelpSection({ title, children }: { title: string; children: ReactNode }) {
	return (
		<section className="space-y-3">
			<h2 className="text-base sm:text-lg font-semibold text-[var(--text)] pt-4 border-t border-[#1e293b]/60 first:border-0 first:pt-0">
				{title}
			</h2>
			{children}
		</section>
	);
}

/** Intro or secondary line under the page title. */
export function HelpMuted({ children }: { children: ReactNode }) {
	return <p className="text-sm sm:text-base text-[var(--muted)]">{children}</p>;
}

/** Body copy inside a section (muted, matches list tone). */
export function HelpParagraph({ children }: { children: ReactNode }) {
	return <p className="text-[var(--muted)]">{children}</p>;
}

/** Emphasis inside muted lists or FAQ answers. */
export function HelpEmphasis({ children }: { children: ReactNode }) {
	return <strong className="text-[var(--text)] font-semibold">{children}</strong>;
}

/** Inline path or field value (monospace). */
export function HelpCode({ children }: { children: ReactNode }) {
	return (
		<code className="text-xs sm:text-sm font-mono bg-[#0f172a] border border-[#1e293b] px-1.5 py-0.5 rounded">
			{children}
		</code>
	);
}

export function HelpList({ items }: { items: ReactNode[] }) {
	return (
		<ol className="list-decimal list-outside ml-5 space-y-2 text-[var(--muted)]">
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
		<ul className="list-disc list-outside ml-5 space-y-1.5 text-[var(--muted)]">
			{items.map((item, index) => (
				<li key={index} className="pl-1">
					{item}
				</li>
			))}
		</ul>
	);
}

/** Nested bullet list inside a numbered step. */
export function HelpSubBullets({ items }: { items: ReactNode[] }) {
	return (
		<ul className="list-disc list-outside ml-5 mt-2 space-y-1 text-[var(--muted)]">
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
		<div className="rounded border border-[#1e293b] bg-[#0f172a]/50 px-4 py-3 text-sm sm:text-base text-[var(--muted)]">
			{children}
		</div>
	);
}

/** FAQ question + answer (lighter than guide section headings). */
export function HelpFaqItem({ question, children }: { question: string; children: ReactNode }) {
	return (
		<div className="space-y-2">
			<h2 className="text-base sm:text-lg font-medium text-[var(--text)]">{question}</h2>
			<div className="text-sm sm:text-base text-[var(--muted)] leading-relaxed">{children}</div>
		</div>
	);
}

export function HelpFaqList({ items }: { items: { q: string; a: ReactNode }[] }) {
	return (
		<div className="space-y-6 pt-2">
			{items.map((item, index) => (
				<div
					key={item.q}
					className={index > 0 ? 'pt-6 border-t border-[#1e293b]/40' : undefined}
				>
					<HelpFaqItem question={item.q}>{item.a}</HelpFaqItem>
				</div>
			))}
		</div>
	);
}

export function HelpInternalLink({ slug, children }: { slug: string; children: ReactNode }) {
	return (
		<Link to={helpPath(slug)} className={HELP_LINK_CLASS}>
			{children}
		</Link>
	);
}

/** In-app route only — help must not link to repo/GitHub developer documentation. */
export function HelpAppLink({ to, children }: { to: string; children: ReactNode }) {
	return (
		<Link to={to} className={HELP_LINK_CLASS}>
			{children}
		</Link>
	);
}
