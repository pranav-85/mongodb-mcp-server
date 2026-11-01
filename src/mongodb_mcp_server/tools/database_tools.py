
from pymongo.errors import PyMongoError

from mongodb_mcp_server.database.connection import (
    close_mongo_connection,
    get_mongo_client,
)
from mongodb_mcp_server.exceptions.custom_exception import ToolExecutionError


def register_database_tools(mcp):
    @mcp.tool()
    async def ping_mongodb() -> str:
        """Check whether the configured MongoDB deployment is reachable."""

        try:
            client = get_mongo_client()
            await client.admin.command("ping")

            return "MongoDB connection successful."

        except PyMongoError as exc:
            raise ToolExecutionError(
                f"MongoDB connection failed: {exc}"
            ) from exc
        except Exception as exc:
            raise ToolExecutionError(
                f"Unexpected MongoDB ping failure: {exc}"
            ) from exc
        finally:
            close_mongo_connection()

    @mcp.tool()
    async def list_databases() -> list[str]:
        """List databases visible to the configured MongoDB user."""

        try:
            client = get_mongo_client()
            databases = await client.list_database_names()

            return sorted(databases)

        except PyMongoError as exc:
            raise ToolExecutionError(
                f"Unable to list databases: {exc}"
            ) from exc
        except Exception as exc:
            raise ToolExecutionError(
                f"Unexpected error while listing databases: {exc}"
            ) from exc
        finally:
            close_mongo_connection()
