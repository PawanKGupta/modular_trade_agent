import { useEffect, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { helpPath } from './helpNav';

const HELP_LINK_CLASS =
	'text-[var(--accent)] hover:text-white font-medium hover:underline focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 focus:ring-offset-2 focus:ring-offset-[var(--bg)] rounded-sm transition-colors duration-150';

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
		<article className="max-w-3xl space-y-5 text-xs sm:text-sm leading-relaxed text-[var(--text)]">
			<h1 className="text-xl sm:text-2xl font-extrabold tracking-tight text-white mb-4 bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
				{title}
			</h1>
			{children}
		</article>
	);
}

export function HelpSection({ title, children }: { title: string; children: ReactNode }) {
	return (
		<section className="space-y-3">
			<h2 className="text-sm sm:text-base font-bold tracking-tight text-white pt-5 border-t border-slate-800/80 first:border-0 first:pt-0">
				{title}
			</h2>
			{children}
		</section>
	);
}

/** Intro or secondary line under the page title. */
export function HelpMuted({ children }: { children: ReactNode }) {
	return <p className="text-xs sm:text-sm text-[var(--muted)] font-medium leading-relaxed">{children}</p>;
}

/** Body copy inside a section (muted, matches list tone). */
export function HelpParagraph({ children }: { children: ReactNode }) {
	return <p className="text-[var(--muted)] leading-relaxed">{children}</p>;
}

/** Emphasis inside muted lists or FAQ answers. */
export function HelpEmphasis({ children }: { children: ReactNode }) {
	return <strong className="text-white font-semibold">{children}</strong>;
}

/** Inline path or field value (monospace). */
export function HelpCode({ children }: { children: ReactNode }) {
	return (
		<code className="text-[11px] sm:text-xs font-mono bg-slate-950/80 border border-slate-800/85 px-1.5 py-0.5 rounded text-[var(--accent)] select-all">
			{children}
		</code>
	);
}

export function HelpList({ items }: { items: ReactNode[] }) {
	return (
		<ol className="list-decimal list-outside ml-5 space-y-2 text-[var(--muted)]">
			{items.map((item, index) => (
				<li key={index} className="pl-1 hover:text-slate-300 transition-colors duration-150">
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
				<li key={index} className="pl-1 hover:text-slate-300 transition-colors duration-150">
					{item}
				</li>
			))}
		</ul>
	);
}

/** Nested bullet list inside a numbered step. */
export function HelpSubBullets({ items }: { items: ReactNode[] }) {
	return (
		<ul className="list-disc list-outside ml-5 mt-1.5 space-y-1 text-[var(--muted)]/85 border-l border-slate-800/50 pl-3">
			{items.map((item, index) => (
				<li key={index} className="pl-1 hover:text-slate-300 transition-colors duration-150">
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
		<div className="overflow-x-auto rounded-lg border border-slate-800 bg-[#0f172a]/20 shadow-md backdrop-blur-sm">
			<table className="w-full text-[11px] sm:text-xs border-collapse">
				<thead>
					<tr className="bg-[#0f172a]/90 text-left border-b border-slate-800">
						<th className="px-3 py-2 font-semibold text-slate-200">{headers[0]}</th>
						<th className="px-3 py-2 font-semibold text-slate-200">{headers[1]}</th>
					</tr>
				</thead>
				<tbody>
					{rows.map(([a, b], index) => (
						<tr key={index} className="border-t border-slate-800/60 hover:bg-slate-800/10 transition-colors duration-150">
							<td className="px-3 py-2 align-top font-medium text-slate-300">{a}</td>
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
		<div className="rounded-r-md border-l-4 border-l-[var(--accent)] border-y border-r border-slate-800 bg-slate-900/30 backdrop-blur-sm px-4 py-3 text-xs sm:text-sm text-[var(--muted)] shadow-md transition-all duration-300 hover:bg-slate-900/40">
			{children}
		</div>
	);
}

/** FAQ question + answer (lighter than guide section headings). */
export function HelpFaqItem({ question, children }: { question: string; children: ReactNode }) {
	return (
		<div className="space-y-2">
			<h2 className="text-xs sm:text-sm font-bold text-white group-hover:text-[var(--accent)] transition-colors duration-200 flex items-center gap-2">
				<span className="text-[var(--accent)] text-xs font-semibold opacity-70 group-hover:opacity-100 transition-opacity">Q.</span>
				{question}
			</h2>
			<div className="text-xs sm:text-sm text-[var(--muted)] leading-relaxed pl-5">{children}</div>
		</div>
	);
}

export function HelpFaqList({ items }: { items: { q: string; a: ReactNode }[] }) {
	return (
		<div className="space-y-3 pt-2">
			{items.map((item) => (
				<div
					key={item.q}
					className="group p-3.5 sm:p-4 rounded-lg border border-slate-800/40 bg-[#0f172a]/10 hover:border-slate-800/80 hover:bg-[#0f172a]/30 transition-all duration-300 shadow-sm hover:shadow-md"
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
