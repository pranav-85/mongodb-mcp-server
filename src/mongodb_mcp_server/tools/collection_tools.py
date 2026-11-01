from typing import Any

from pymongo.errors import PyMongoError

from mongodb_mcp_server.config import MONGODB_DATABASE
from mongodb_mcp_server.database.connection import (
    close_mongo_connection,
    get_mongo_client,
)
from mongodb_mcp_server.exceptions.custom_exception import (
    ToolExecutionError,
    ToolValidationError,
)


def _normalize_collection_name(collection_name: str) -> str:
    """Validate and normalize a MongoDB collection name input."""

    if not collection_name or not collection_name.strip():
        raise ToolValidationError("collection_name cannot be empty.")

    return collection_name.strip()


def _format_indexes(index_information: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert PyMongo index metadata into a stable tool response shape."""

    indexes: list[dict[str, Any]] = []

    for index_name, details in index_information.items():
        indexes.append(
            {
                "name": index_name,
                "keys": [
                    {
                        "field": field,
                        "direction": direction,
                    }
                    for field, direction in details.get("key", [])
                ],
                "unique": details.get("unique", False),
                "sparse": details.get("sparse", False),
            }
        )

    return indexes


def register_collection_tools(mcp):

    @mcp.tool()
    async def list_collections() -> list[str]:
        """List collections in the configured MongoDB database."""

        try:
            client = get_mongo_client()
            database = client[MONGODB_DATABASE]

            collections = await database.list_collection_names()

            return sorted(collections)

        except PyMongoError as exc:
            raise ToolExecutionError(
                f"Unable to list collections: {exc}"
            ) from exc
        except Exception as exc:
            raise ToolExecutionError(
                f"Unexpected error while listing collections: {exc}"
            ) from exc
        finally:
            close_mongo_connection()

    @mcp.tool()
    async def get_collection_info(
        collection_name: str,
    ) -> dict[str, Any]:
        """
        Retrieve collection metadata, estimated document count,
        and index information.
        """

        normalized_name = _normalize_collection_name(collection_name)

        try:
            client = get_mongo_client()
            database = client[MONGODB_DATABASE]

            collection_names = await database.list_collection_names()

            if normalized_name not in collection_names:
                raise ToolValidationError(
                    f"Collection '{normalized_name}' does not exist "
                    f"in database '{MONGODB_DATABASE}'."
                )

            collection = database[normalized_name]

            document_count = (
                await collection.estimated_document_count()
            )

            index_information = await collection.index_information()
            indexes = _format_indexes(index_information)

            return {
                "database": MONGODB_DATABASE,
                "collection": normalized_name,
                "estimated_document_count": document_count,
                "index_count": len(indexes),
                "indexes": indexes,
            }

        except ToolValidationError:
            raise

        except PyMongoError as exc:
            raise ToolExecutionError(
                f"Unable to retrieve collection information: {exc}"
            ) from exc
        except Exception as exc:
            raise ToolExecutionError(
                "Unexpected error while retrieving collection "
                f"information: {exc}"
            ) from exc
        finally:
            close_mongo_connection()
