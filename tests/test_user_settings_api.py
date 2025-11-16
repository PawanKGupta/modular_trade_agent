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
