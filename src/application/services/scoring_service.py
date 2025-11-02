"""
Scoring Service (Re-export)

This module re-exports ScoringService from services package for backward compatibility
with src/ application layer code.

Phase 4: Consolidated to services/scoring_service.py to eliminate duplication.

For new code, prefer importing directly from services:
    from services import ScoringService

This module maintains backward compatibility for existing src/ code.
"""

# Phase 4: Re-export from services package (single source of truth)
from services.scoring_service import ScoringService

__all__ = ['ScoringService']
