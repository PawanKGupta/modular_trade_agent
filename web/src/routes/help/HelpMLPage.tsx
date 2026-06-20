import {
	HelpAppLink,
	HelpCallout,
	HelpEmphasis,
	HelpMuted,
	HelpPage,
	HelpParagraph,
	HelpSection,
	HelpBullets,
	HelpList,
} from './HelpProse';

export function HelpMLPage() {
	return (
		<HelpPage title="ML-powered signals">
			<HelpMuted>
				Rebound layers a machine-learning verdict on top of every rule-based analysis so you can see
				not just <HelpEmphasis>what the rules say</HelpEmphasis> but{' '}
				<HelpEmphasis>how confident the system is</HelpEmphasis> in that verdict.
			</HelpMuted>

			<HelpSection title="What the ML engine does">
				<HelpParagraph>
					After the rule-based scanner scores a stock (RSI, EMA, volume, backtest), an independent
					Random Forest or XGBoost classifier re-evaluates the same features and outputs a
					probability. The two verdicts are then combined so the final signal is only promoted to
					your buying zone when <HelpEmphasis>both the rules and the model agree</HelpEmphasis>.
				</HelpParagraph>
				<HelpBullets
					items={[
						<>
							<HelpEmphasis>Fewer false signals</HelpEmphasis> — the model filters out stocks
							that look good on rules alone but have historically underperformed.
						</>,
						<>
							<HelpEmphasis>Confidence score</HelpEmphasis> — every signal shows a percentage
							(e.g. 74%) so you can prioritise the highest-conviction ideas.
						</>,
						<>
							<HelpEmphasis>Transparent</HelpEmphasis> — you can see both the rule verdict and
							the ML verdict side-by-side in Buying Zone.
						</>,
						<>
							<HelpEmphasis>Graceful fallback</HelpEmphasis> — if the ML model is unavailable,
							Rebound continues scanning using rules only. Nothing breaks.
						</>,
					]}
				/>
			</HelpSection>

			<HelpSection title="Where to see ML verdicts">
				<HelpList
					items={[
						<>
							Open <HelpAppLink to="/dashboard/buying-zone">Buying Zone</HelpAppLink>. Each
							signal card shows <HelpEmphasis>ML Verdict</HelpEmphasis> and{' '}
							<HelpEmphasis>ML Confidence</HelpEmphasis> columns (enable them via the column
							selector if hidden).
						</>,
						<>
							A confidence of <HelpEmphasis>60 % or above</HelpEmphasis> means the model has
							cleared its threshold and the verdict has been included in the final decision.
						</>,
						<>
							Telegram notifications include the ML verdict and confidence alongside the
							rule-based score — so you get the full picture on your phone.
						</>,
					]}
				/>
			</HelpSection>

			<HelpSection title="ML confidence threshold">
				<HelpParagraph>
					You can tune the minimum confidence the model must reach before its verdict counts
					toward the final signal. This is set in{' '}
					<HelpAppLink to="/dashboard/trading-config">Trading Config</HelpAppLink> under{' '}
					<HelpEmphasis>ML Configuration → ML Confidence Threshold</HelpEmphasis>.
				</HelpParagraph>
				<HelpBullets
					items={[
						<>Default: <HelpEmphasis>0.6</HelpEmphasis> (60 %)</>,
						<>
							Higher (e.g. 0.75) — fewer but higher-conviction signals. Good for low-risk
							approaches.
						</>,
						<>
							Lower (e.g. 0.5) — more signals but with marginally lower ML certainty. Better
							for catching early breakouts.
						</>,
					]}
				/>
			</HelpSection>

			<HelpSection title="Enable or disable ML predictions">
				<HelpParagraph>
					In <HelpAppLink to="/dashboard/trading-config">Trading Config</HelpAppLink> under{' '}
					<HelpEmphasis>ML Configuration</HelpEmphasis>:
				</HelpParagraph>
				<HelpBullets
					items={[
						<>
							<HelpEmphasis>Enable ML Predictions</HelpEmphasis> — turns the verdict
							classifier on or off. When off, only rule-based verdicts drive signals.
						</>,
						<>
							<HelpEmphasis>Combine ML with Rule-Based Logic</HelpEmphasis> — when on (default),
							both must agree for a buy signal. When off, ML verdict alone decides.
						</>,
						<>
							<HelpEmphasis>Use ML for target / stop</HelpEmphasis> — an optional second model
							that refines price targets and stop-loss levels. Requires a trained price model on
							the server; leave off if your operator has not set one up.
						</>,
					]}
				/>
			</HelpSection>

			<HelpSection title="How signals stay fresh">
				<HelpParagraph>
					Each time the analysis service runs, it re-evaluates every stock in the watchlist. If a
					stock&apos;s ML verdict drops from <HelpEmphasis>buy</HelpEmphasis> to{' '}
					<HelpEmphasis>watch</HelpEmphasis> or <HelpEmphasis>avoid</HelpEmphasis>, its existing
					signal in Buying Zone is automatically expired — it disappears without you having to
					manually reject it. This means your buying zone always reflects the{' '}
					<HelpEmphasis>current opinion</HelpEmphasis> of both the rules and the model.
				</HelpParagraph>
			</HelpSection>

			<HelpSection title="Walk-forward validated">
				<HelpParagraph>
					The default model shipped with Rebound was trained and validated using a{' '}
					<HelpEmphasis>walk-forward methodology</HelpEmphasis>: the model only ever sees data
					from the past when predicting the future — the same way it would behave in real trading.
					This prevents the common machine-learning trap of overfitting to data the model
					&quot;should not have seen&quot;.
				</HelpParagraph>
			</HelpSection>

			<HelpCallout>
				ML signals improve with more trade history. The longer the system runs and the more
				outcomes are recorded, the better the model can be retrained. Operators can retrain
				from the ML Training admin page at any time.
			</HelpCallout>

			<HelpCallout>
				Trading involves risk of loss. ML confidence scores are probability estimates, not
				guarantees. Always apply your own judgment before placing or approving a trade.
			</HelpCallout>
		</HelpPage>
	);
}
