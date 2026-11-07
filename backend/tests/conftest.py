import os

os.environ.setdefault("JWT_SECRET_KEY", "local-test-key-that-is-at-least-32-characters-long")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.main import app
from app.models import Base


@pytest.fixture
def test_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with test_session() as session:
        from app.models.identity import Role

        session.add_all(
            [
                Role(name="customer", description="Customer loyalty account"),
                Role(name="staff", description="Shop staff"),
                Role(name="admin", description="Shop administrator"),
            ]
        )
        session.commit()
    yield test_session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(test_session_factory):
    with test_session_factory() as session:
        yield session


@pytest.fixture
def client(test_session_factory):
    limiter.reset()

    def override_get_db():
        with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
