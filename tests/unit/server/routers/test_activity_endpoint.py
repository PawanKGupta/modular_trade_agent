"""
Tests for activity endpoint to verify no 307 redirects
"""

from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from server.app.main import app
from server.app.core.deps import get_current_user, get_db


def test_activity_endpoint_without_trailing_slash():
    """Test that /api/v1/user/activity (no trailing slash) returns 200, not 307"""
    
    # Override dependencies
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id=1, email="test@example.com")
    app.dependency_overrides[get_db] = lambda: MagicMock()
    
    try:
        with patch("server.app.routers.activity.ActivityRepository") as mock_repo:
            mock_repo_instance = MagicMock()
            mock_repo_instance.recent.return_value = []
            mock_repo.return_value = mock_repo_instance
            
            client = TestClient(app)
            response = client.get("/api/v1/user/activity")
            
            # Should return 200, not 307
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    finally:
        app.dependency_overrides.clear()


def test_activity_endpoint_with_query_params():
    """Test that /api/v1/user/activity?level=warn returns 200, not 307"""
    
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id=1, email="test@example.com")
    app.dependency_overrides[get_db] = lambda: MagicMock()
    
    try:
        with patch("server.app.routers.activity.ActivityRepository") as mock_repo:
            mock_repo_instance = MagicMock()
            mock_repo_instance.recent.return_value = []
            mock_repo.return_value = mock_repo_instance
            
            client = TestClient(app)
            response = client.get("/api/v1/user/activity?level=warn")
            
            # Should return 200, not 307 (this was the reported issue)
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    finally:
        app.dependency_overrides.clear()


def test_activity_endpoint_no_307_redirect():
    """Verify the endpoint doesn't cause 307 redirects"""
    
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id=1, email="test@example.com")
    app.dependency_overrides[get_db] = lambda: MagicMock()
    
    try:
        with patch("server.app.routers.activity.ActivityRepository") as mock_repo:
            mock_repo_instance = MagicMock()
            mock_repo_instance.recent.return_value = []
            mock_repo.return_value = mock_repo_instance
            
            client = TestClient(app)
            
            # Test various combinations that were causing 307
            test_urls = [
                "/api/v1/user/activity",
                "/api/v1/user/activity?level=info",
                "/api/v1/user/activity?level=warn",
                "/api/v1/user/activity?level=error",
                "/api/v1/user/activity?level=all",
            ]
            
            for url in test_urls:
                response = client.get(url, follow_redirects=False)
                assert response.status_code == 200, f"URL {url} returned {response.status_code}, expected 200"
    finally:
        app.dependency_overrides.clear()
