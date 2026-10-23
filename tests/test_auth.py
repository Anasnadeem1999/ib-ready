"""Logins: salted PBKDF2 hashes, wrong-password refusal, lockout, tokens."""

import pytest

from ticktie import config, db


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    db.init()


def test_signup_then_login_and_token():
    prof, tok, created = db.sign_in("Maya", "secret123")
    assert created and db.profile_for_token(tok)["id"] == prof["id"]
    prof2, tok2, created2 = db.sign_in("maya", "secret123")
    assert not created2 and prof2["id"] == prof["id"] and tok2 != tok


def test_password_is_hashed_not_stored():
    prof, _, _ = db.sign_in("Jordan", "hunter22")
    with db.conn() as c:
        row = c.execute("SELECT * FROM credentials WHERE profile_id=?", (prof["id"],)).fetchone()
    assert "hunter22" not in row["pw_hash"] and len(row["salt"]) == 32 and row["iterations"] >= 100_000


def test_wrong_password_and_lockout():
    db.sign_in("Sam", "rightpass")
    for _ in range(db.MAX_FAILURES):
        with pytest.raises(db.AuthError):
            db.sign_in("Sam", "wrongpass")
    with pytest.raises(db.AuthError, match="locked"):
        db.sign_in("Sam", "rightpass")


def test_bad_token_rejected():
    assert db.profile_for_token("nope") is None and db.profile_for_token(None) is None
