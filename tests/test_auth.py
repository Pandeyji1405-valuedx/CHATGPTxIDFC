import pytest

import uuid

def test_user_registration_and_login(client):
    uid = uuid.uuid4().hex[:6]
    email = f"test_user_{uid}@bank.com"
    pwd = "SecurePassword@123"

    # 1. Register
    reg_res = client.post("/api/auth/register", json={
        "name": "Test Auth User",
        "email": email,
        "password": pwd
    })
    assert reg_res.status_code == 201
    data = reg_res.json()
    assert "access_token" in data
    assert data["user"]["email"] == email
    assert data["user"]["name"] == "Test Auth User"

    # 2. Login
    login_res = client.post("/api/auth/login", json={
        "email": email,
        "password": pwd
    })
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "access_token" in login_data

    # 3. Invalid credentials
    bad_login = client.post("/api/auth/login", json={
        "email": email,
        "password": "WrongPassword"
    })
    assert bad_login.status_code == 401

def test_google_oauth_flow(client):
    uid = uuid.uuid4().hex[:6]
    google_res = client.post("/api/auth/google", json={
        "credential": f"google_token_mock_{uid}",
        "email": f"siddharth.oauth.{uid}@gmail.com",
        "name": "Siddharth OAuth"
    })
    assert google_res.status_code == 200
    data = google_res.json()
    assert "access_token" in data
    assert data["user"]["email"] == f"siddharth.oauth.{uid}@gmail.com"
    assert data["user"]["auth_provider"] == "google"

def test_get_current_user_profile(client, auth_headers_user1):
    res = client.get("/api/auth/me", headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert "id" in data
    assert "email" in data
    assert data["name"] == "User Alpha"

def test_switch_account_session(client):
    # Switch using registered email prefix
    switch_res = client.post("/api/auth/switch-account", json={
        "email": "customer@idfcbank.com"
    })
    assert switch_res.status_code == 200
    data = switch_res.json()
    assert "access_token" in data
    assert "customer" in data["user"]["email"]

