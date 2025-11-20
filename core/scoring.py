def compute_strength_score(entry):
    """
    [WARN]? DEPRECATED in Phase 4: This function is deprecated and will be removed in a future version.

    For new code, prefer using ScoringService:
        from services import ScoringService
        service = ScoringService()
        score = service.compute_strength_score(entry)

    Migration guide: See utils.deprecation.get_migration_guide("compute_strength_score")
    """
    # Phase 4: Issue deprecation warning
    import warnings
    from utils.deprecation import deprecation_notice

    deprecation_notice(
        module="core.scoring",
        function="compute_strength_score",
        replacement="services.ScoringService.compute_strength_score()",
        version="Phase 4",
    )
    score = 0
    verdict = entry.get("verdict")

    # Base score based on verdict type
    if verdict == "strong_buy":
        score = 10  # Strong baseline for strong buys
    elif verdict == "buy":
        score = 5  # Standard baseline for buys
    else:
        return -1  # No scoring for non-buy verdicts

    justifications = entry.get("justification", [])
    timeframe_analysis = entry.get("timeframe_analysis")

    # Pattern-based scoring
    for j in justifications:
        if j.startswith("pattern:"):
            patterns = j.replace("pattern:", "").split(",")
            score += len(patterns) * 2
        elif j == "volume_strong":
            score += 1
        elif j.startswith("rsi:"):
            try:
                rsi_val = float(j.split(":")[1])
                if rsi_val < 30:
                    score += 1
                if rsi_val < 20:
                    score += 1
            except Exception:
                pass
        elif j == "excellent_uptrend_dip_confirmation":
            score += 8  # Highest bonus for excellent uptrend dip (RSI<30 + strong uptrend)
        elif j == "good_uptrend_dip_confirmation":
            score += 5  # Strong bonus for good uptrend dip
        elif j == "fair_uptrend_dip_confirmation":
            score += 3  # Moderate bonus for fair uptrend dip

    # Additional dip-buying timeframe analysis scoring
    if timeframe_analysis:
        alignment_score = timeframe_analysis.get("alignment_score", 0)
        confirmation = timeframe_analysis.get("confirmation", "poor_dip")

        # Bonus points for dip-buying alignment score
        if alignment_score >= 8:
            score += 4  # Excellent dip bonus
        elif alignment_score >= 6:
            score += 3  # Good dip bonus
        elif alignment_score >= 4:
            score += 2  # Fair dip bonus
        elif alignment_score >= 2:
            score += 1  # Weak dip bonus

        # Analyze dip-buying specific components
        daily_analysis = timeframe_analysis.get("daily_analysis", {})
        weekly_analysis = timeframe_analysis.get("weekly_analysis", {})

        if daily_analysis and weekly_analysis:
            # Daily oversold condition (primary signal)
            daily_oversold = daily_analysis.get("oversold_analysis", {})
            if daily_oversold.get("severity") == "extreme":
                score += 3  # RSI < 20
            elif daily_oversold.get("severity") == "high":
                score += 2  # RSI < 30

            # Support level confluence
            daily_support = daily_analysis.get("support_analysis", {})
            if daily_support.get("quality") == "strong":
                score += 2
            elif daily_support.get("quality") == "moderate":
                score += 1

            # Volume exhaustion signals
            daily_volume = daily_analysis.get("volume_exhaustion", {})
            volume_exhaustion_score = daily_volume.get("exhaustion_score", 0)
            if volume_exhaustion_score >= 2:
                score += 2
            elif volume_exhaustion_score >= 1:
                score += 1

    return min(score, 25)  # Cap maximum score at 25
