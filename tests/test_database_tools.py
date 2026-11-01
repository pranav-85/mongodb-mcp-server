from unittest.mock import AsyncMock, MagicMock

import pytest
from pymongo.errors import PyMongoError

from mongodb_mcp_server.exceptions.custom_exception import ToolExecutionError
from mongodb_mcp_server.tools.database_tools import register_database_tools
from tests.conftest import FakeMCP


@pytest.mark.asyncio
async def test_ping_mongodb_success(monkeypatch):
    mcp = FakeMCP()
    register_database_tools(mcp)

    client = MagicMock()
    client.admin = MagicMock()
    client.admin.command = AsyncMock(return_value={"ok": 1})

    close_mock = MagicMock()
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.database_tools.get_mongo_client",
        lambda: client,
    )
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.database_tools.close_mongo_connection",
        close_mock,
    )

    result = await mcp.tools["ping_mongodb"]()

    assert result == "MongoDB connection successful."
    close_mock.assert_called_once()


@pytest.mark.asyncio
async def test_ping_mongodb_wraps_pymongo_errors(monkeypatch):
    mcp = FakeMCP()
    register_database_tools(mcp)

    client = MagicMock()
    client.admin = MagicMock()
    client.admin.command = AsyncMock(side_effect=PyMongoError("down"))

    close_mock = MagicMock()
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.database_tools.get_mongo_client",
        lambda: client,
    )
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.database_tools.close_mongo_connection",
        close_mock,
    )

    with pytest.raises(ToolExecutionError, match="MongoDB connection failed"):
        await mcp.tools["ping_mongodb"]()

    close_mock.assert_called_once()


@pytest.mark.asyncio
async def test_list_databases_returns_sorted(monkeypatch):
    mcp = FakeMCP()
    register_database_tools(mcp)

    client = MagicMock()
    client.list_database_names = AsyncMock(return_value=["zeta", "alpha"])

    close_mock = MagicMock()
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.database_tools.get_mongo_client",
        lambda: client,
    )
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.database_tools.close_mongo_connection",
        close_mock,
    )

    result = await mcp.tools["list_databases"]()

    assert result == ["alpha", "zeta"]
    close_mock.assert_called_once()


@pytest.mark.asyncio
async def test_list_databases_wraps_unexpected_errors(monkeypatch):
    mcp = FakeMCP()
    register_database_tools(mcp)

    client = MagicMock()
    client.list_database_names = AsyncMock(side_effect=RuntimeError("boom"))

    close_mock = MagicMock()
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.database_tools.get_mongo_client",
        lambda: client,
    )
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.database_tools.close_mongo_connection",
        close_mock,
    )

    with pytest.raises(ToolExecutionError, match="Unexpected error while listing databases"):
        await mcp.tools["list_databases"]()

    close_mock.assert_called_once()
