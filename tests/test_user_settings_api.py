def test_get_and_put_settings(client):
    # Create user via signup
    resp = client.post(
        "/api/v1/auth/signup", json={"email": "s1@example.com", "password": "Secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Get settings
    resp = client.get("/api/v1/user/settings", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["trade_mode"] in ("paper", "broker")

    # Update settings
    resp = client.put(
        "/api/v1/user/settings",
        headers={"Authorization": f"Bearer {token}"},
        json={"trade_mode": "paper"},
    )
    assert resp.status_code == 200
    assert resp.json()["trade_mode"] == "paper"


def test_get_buying_zone_columns_empty(client):
    """Test getting buying zone columns when none are saved."""
    resp = client.post(
        "/api/v1/auth/signup", json={"email": "s2@example.com", "password": "Secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    resp = client.get(
        "/api/v1/user/buying-zone-columns", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["columns"] == []


def test_save_and_get_buying_zone_columns(client):
    """Test saving and retrieving buying zone columns."""
    resp = client.post(
        "/api/v1/auth/signup", json={"email": "s3@example.com", "password": "Secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Save columns
    columns = ["symbol", "rsi10", "ema9", "confidence", "backtest_score"]
    resp = client.put(
        "/api/v1/user/buying-zone-columns",
        headers={"Authorization": f"Bearer {token}"},
        json={"columns": columns},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["columns"] == columns

    # Get columns back
    resp = client.get(
        "/api/v1/user/buying-zone-columns", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["columns"] == columns


def test_update_buying_zone_columns(client):
    """Test updating buying zone columns overwrites previous values."""
    resp = client.post(
        "/api/v1/auth/signup", json={"email": "s4@example.com", "password": "Secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Save initial columns
    initial_columns = ["symbol", "rsi10", "ema9"]
    resp = client.put(
        "/api/v1/user/buying-zone-columns",
        headers={"Authorization": f"Bearer {token}"},
        json={"columns": initial_columns},
    )
    assert resp.status_code == 200

    # Update with new columns
    new_columns = ["symbol", "distance_to_ema9", "ml_confidence", "target", "stop"]
    resp = client.put(
        "/api/v1/user/buying-zone-columns",
        headers={"Authorization": f"Bearer {token}"},
        json={"columns": new_columns},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["columns"] == new_columns

    # Verify they're saved
    resp = client.get(
        "/api/v1/user/buying-zone-columns", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["columns"] == new_columns
    assert data["columns"] != initial_columns


def test_buying_zone_columns_requires_auth(client):
    """Test that buying zone columns endpoints require authentication."""
    # Get without auth
    resp = client.get("/api/v1/user/buying-zone-columns")
    assert resp.status_code == 401

    # Put without auth
    resp = client.put("/api/v1/user/buying-zone-columns", json={"columns": ["symbol", "rsi10"]})
    assert resp.status_code == 401
