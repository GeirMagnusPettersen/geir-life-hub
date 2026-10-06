"""Shared pytest fixtures: an isolated in-memory SQLite DB per test and a
TestClient wired to the FastAPI app via dependency override.

SQLite stands in for Postgres in tests to keep them fast and
dependency-free; the application code only uses portable SQLAlchemy
constructs so this is a safe trade-off for a skeleton test suite.
"""
from __future__ import annotations

import os

# Must be set before any `app.*` module is imported, since app.database
# builds its module-level engine from these settings at import time. This
# keeps the FastAPI startup event (which calls Base.metadata.create_all on
# that engine) from trying to reach a real Postgres server during tests.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SESSION_SECRET_KEY", "test-only-secret")

from collections.abc import Generator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.security import hash_password  # noqa: E402


@pytest.fixture()
def db_session() -> Generator:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session) -> Generator[TestClient, None, None]:
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def seed_user(db_session):
    from app.models import User

    user = User(
        username="geir",
        display_name="Geir",
        password_hash=hash_password("correct-horse-battery"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def auth_client(client, seed_user) -> TestClient:
    response = client.post(
        "/auth/login",
        json={"username": "geir", "password": "correct-horse-battery"},
    )
    assert response.status_code == 200
    return client
