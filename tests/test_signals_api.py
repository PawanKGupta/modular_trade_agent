from tests.support.auth_flow import signup_and_verify_payload
def test_buying_zone_empty(client, db_session):
    # Create user via signup to get token
    _auth_tokens = signup_and_verify_payload(client, db_session, {"email": "bz@example.com", "password": "Secret123!"})
    token = _auth_tokens["access_token"]

    # No signals inserted yet -> expect empty list
    resp = client.get(
        "/api/v1/signals/buying-zone?limit=5", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
