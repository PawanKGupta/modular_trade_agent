"""``monitoring._get_services_health_impl`` error propagation."""

from __future__ import annotations

import pytest


def test_get_services_health_impl_propagates_execute_errors():
    from server.app.routers import monitoring

    class BoomDb:
        def execute(self, *_a, **_k):
            raise RuntimeError("db execute failed")

    with pytest.raises(RuntimeError, match="db execute failed"):
        monitoring._get_services_health_impl(BoomDb())
