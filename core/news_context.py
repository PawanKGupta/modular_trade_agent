"""Request-scoped news source profile (cheap vs full composite)."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Literal

NewsProfile = Literal["cheap", "full"]

# Default profile when not set by analyze_ticker / enrich helpers
news_profile_ctx: ContextVar[NewsProfile | None] = ContextVar("news_profile", default=None)


def set_news_profile(profile: NewsProfile) -> Token:
    return news_profile_ctx.set(profile)


def reset_news_profile(token: Token) -> None:
    news_profile_ctx.reset(token)


def current_news_profile() -> NewsProfile | None:
    return news_profile_ctx.get()
