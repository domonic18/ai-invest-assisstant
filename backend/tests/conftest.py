import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_db
from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client():
    """返回已清除依赖覆盖的 TestClient。"""
    app.dependency_overrides.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()


class _MockSession:
    """极简 mock session，用于覆盖 get_db。"""

    async def commit(self) -> None:
        pass

    async def refresh(self, obj: object) -> None:
        pass

    async def close(self) -> None:
        pass


@pytest.fixture
def mock_session(client):
    """覆盖 get_db 返回一个 mock session。"""
    session = _MockSession()

    async def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    return session
