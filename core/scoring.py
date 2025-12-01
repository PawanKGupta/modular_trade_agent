"""
Scoring Module (Deprecated)

Phase 4.6: This module is deprecated. All functionality has been moved to services.ScoringService.

For new code, use:
    from services import ScoringService
    service = ScoringService()
    score = service.compute_strength_score(entry)

This module now only provides backward-compatible wrappers that delegate to the service layer.
"""

from utils.deprecation import deprecation_notice


def compute_strength_score(entry):
    """
    [WARN]? DEPRECATED in Phase 4: This function is deprecated and will be removed in a future version.

    Phase 4.6: This function now delegates to ScoringService instead of duplicating logic.

    For new code, prefer using ScoringService:
        from services import ScoringService
        service = ScoringService()
        score = service.compute_strength_score(entry)

    Migration guide: See utils.deprecation.get_migration_guide("compute_strength_score")
    """
    # Phase 4: Issue deprecation warning
    deprecation_notice(
        module="core.scoring",
        function="compute_strength_score",
        replacement="services.ScoringService.compute_strength_score()",
        version="Phase 4",
    )

    # Phase 4.6: Delegate to service layer (no duplicate implementation)
    try:
        from services import ScoringService

        service = ScoringService()
        return service.compute_strength_score(entry)
    except ImportError as e:
        from utils.logger import logger

        logger.error(f"ScoringService not available: {e}")
        # Fallback: return -1 for non-buy verdicts, 0 for others
        verdict = entry.get("verdict")
        if verdict in ["buy", "strong_buy"]:
            return 0  # Minimal fallback score
        return -1
