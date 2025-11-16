def test_buying_zone_empty(client):
    # Create user via signup to get token
    resp = client.post(
        "/api/v1/auth/signup", json={"email": "bz@example.com", "password": "Secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # No signals inserted yet -> expect empty list
    resp = client.get(
        "/api/v1/signals/buying-zone?limit=5", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
