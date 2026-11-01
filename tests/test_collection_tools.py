from unittest.mock import AsyncMock, MagicMock

import pytest
from pymongo.errors import PyMongoError

from mongodb_mcp_server.exceptions.custom_exception import (
    ToolExecutionError,
    ToolValidationError,
)
from mongodb_mcp_server.tools.collection_tools import (
    _format_indexes,
    _normalize_collection_name,
    register_collection_tools,
)
from tests.conftest import FakeMCP


def test_normalize_collection_name_success():
    assert _normalize_collection_name("  users  ") == "users"


def test_normalize_collection_name_rejects_empty():
    with pytest.raises(ToolValidationError, match="cannot be empty"):
        _normalize_collection_name("   ")


def test_format_indexes_handles_missing_key_metadata():
    formatted = _format_indexes({"_id_": {"unique": True}})
    assert formatted == [
        {
            "name": "_id_",
            "keys": [],
            "unique": True,
            "sparse": False,
        }
    ]


@pytest.mark.asyncio
async def test_list_collections_success(monkeypatch):
    mcp = FakeMCP()
    register_collection_tools(mcp)

    database = MagicMock()
    database.list_collection_names = AsyncMock(return_value=["b", "a"])

    client = MagicMock()
    client.__getitem__.return_value = database

    close_mock = MagicMock()
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.collection_tools.get_mongo_client",
        lambda: client,
    )
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.collection_tools.close_mongo_connection",
        close_mock,
    )

    result = await mcp.tools["list_collections"]()

    assert result == ["a", "b"]
    close_mock.assert_called_once()


@pytest.mark.asyncio
async def test_get_collection_info_success(monkeypatch):
    mcp = FakeMCP()
    register_collection_tools(mcp)

    collection = MagicMock()
    collection.estimated_document_count = AsyncMock(return_value=42)
    collection.index_information = AsyncMock(
        return_value={
            "_id_": {"key": [("_id", 1)], "unique": True},
            "name_1": {
                "key": [("name", 1)],
                "unique": False,
                "sparse": True,
            },
        }
    )

    database = MagicMock()
    database.list_collection_names = AsyncMock(return_value=["users"])
    database.__getitem__.return_value = collection

    client = MagicMock()
    client.__getitem__.return_value = database

    close_mock = MagicMock()
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.collection_tools.get_mongo_client",
        lambda: client,
    )
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.collection_tools.close_mongo_connection",
        close_mock,
    )

    result = await mcp.tools["get_collection_info"](" users ")

    assert result["collection"] == "users"
    assert result["estimated_document_count"] == 42
    assert result["index_count"] == 2
    close_mock.assert_called_once()


@pytest.mark.asyncio
async def test_get_collection_info_rejects_missing_collection(monkeypatch):
    mcp = FakeMCP()
    register_collection_tools(mcp)

    database = MagicMock()
    database.list_collection_names = AsyncMock(return_value=["orders"])

    client = MagicMock()
    client.__getitem__.return_value = database

    close_mock = MagicMock()
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.collection_tools.get_mongo_client",
        lambda: client,
    )
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.collection_tools.close_mongo_connection",
        close_mock,
    )

    with pytest.raises(ToolValidationError, match="does not exist"):
        await mcp.tools["get_collection_info"]("users")

    close_mock.assert_called_once()


@pytest.mark.asyncio
async def test_get_collection_info_wraps_pymongo_errors(monkeypatch):
    mcp = FakeMCP()
    register_collection_tools(mcp)

    database = MagicMock()
    database.list_collection_names = AsyncMock(side_effect=PyMongoError("db down"))

    client = MagicMock()
    client.__getitem__.return_value = database

    close_mock = MagicMock()
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.collection_tools.get_mongo_client",
        lambda: client,
    )
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.collection_tools.close_mongo_connection",
        close_mock,
    )

    with pytest.raises(ToolExecutionError, match="Unable to retrieve collection information"):
        await mcp.tools["get_collection_info"]("users")

    close_mock.assert_called_once()
