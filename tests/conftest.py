"""Pytest fixtures providing isolated temporary SQLite databases for testing."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from crm.database import Base


@pytest.fixture()
def db_session(tmp_path):
    db_file = tmp_path / "test_salespilot.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
