from unittest.mock import AsyncMock, MagicMock

import pytest
from pymongo.errors import PyMongoError

from mongodb_mcp_server.exceptions.custom_exception import (
    ToolExecutionError,
    ToolValidationError,
)
from mongodb_mcp_server.tools import document_tools
from mongodb_mcp_server.tools.document_tools import register_document_tools
from tests.conftest import FakeMCP


def _build_registered_tools():
    mcp = FakeMCP()
    register_document_tools(mcp)
    return mcp.tools


def test_validate_projection_rejects_mixed_modes():
    with pytest.raises(ToolValidationError, match="Cannot mix inclusion and exclusion"):
        document_tools.validate_projection({"name": 1, "age": 0})


def test_validate_pipeline_rejects_disallowed_stage():
    with pytest.raises(ToolValidationError, match="not permitted"):
        document_tools.validate_pipeline([{"$lookup": {"from": "x"}}])


@pytest.mark.asyncio
async def test_find_documents_success(monkeypatch):
    tools = _build_registered_tools()

    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.to_list = AsyncMock(return_value=[{"_id": 1, "name": "A"}])

    collection = MagicMock()
    collection.name = "users"
    collection.find.return_value = cursor

    close_mock = MagicMock()
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.document_tools.get_collection",
        AsyncMock(return_value=collection),
    )
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.document_tools.close_mongo_connection",
        close_mock,
    )

    result = await tools["find_documents"](
        collection_name="users",
        filter={"status": "active"},
        sort={"name": 1},
        skip=0,
        limit=2,
    )

    assert result["collection"] == "users"
    assert result["returned_count"] == 1
    assert result["documents"][0]["name"] == "A"
    close_mock.assert_called_once()


@pytest.mark.asyncio
async def test_find_documents_validation_error_invalid_limit():
    tools = _build_registered_tools()

    with pytest.raises(ToolValidationError, match="limit must be between"):
        await tools["find_documents"](
            collection_name="users",
            filter={},
            limit=0,
        )


@pytest.mark.asyncio
async def test_find_documents_wraps_pymongo_error(monkeypatch):
    tools = _build_registered_tools()

    collection = MagicMock()
    collection.name = "users"
    collection.find.side_effect = PyMongoError("query failed")

    close_mock = MagicMock()
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.document_tools.get_collection",
        AsyncMock(return_value=collection),
    )
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.document_tools.close_mongo_connection",
        close_mock,
    )

    with pytest.raises(ToolExecutionError, match="MongoDB find operation failed"):
        await tools["find_documents"](
            collection_name="users",
            filter={},
        )

    close_mock.assert_called_once()


@pytest.mark.asyncio
async def test_aggregate_documents_success(monkeypatch):
    tools = _build_registered_tools()

    aggregate_cursor = MagicMock()
    aggregate_cursor.to_list = AsyncMock(return_value=[{"_id": "A", "count": 3}])

    collection = MagicMock()
    collection.name = "orders"
    collection.aggregate = AsyncMock(return_value=aggregate_cursor)

    close_mock = MagicMock()
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.document_tools.get_collection",
        AsyncMock(return_value=collection),
    )
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.document_tools.close_mongo_connection",
        close_mock,
    )

    pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    result = await tools["aggregate_documents"]("orders", pipeline, limit=5)

    assert result["collection"] == "orders"
    assert result["returned_count"] == 1

    called_pipeline = collection.aggregate.await_args.args[0]
    assert called_pipeline[-1] == {"$limit": 5}
    assert pipeline == [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    close_mock.assert_called_once()


@pytest.mark.asyncio
async def test_aggregate_documents_rejects_invalid_pipeline_before_db_call(monkeypatch):
    tools = _build_registered_tools()

    get_collection_mock = AsyncMock()
    monkeypatch.setattr(
        "mongodb_mcp_server.tools.document_tools.get_collection",
        get_collection_mock,
    )

    with pytest.raises(ToolValidationError, match="pipeline must be a non-empty list"):
        await tools["aggregate_documents"]("orders", [])

    get_collection_mock.assert_not_awaited()
