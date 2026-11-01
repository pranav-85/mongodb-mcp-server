
import json
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
from mongodb_mcp_server.utils.serializers import serialize_bson


DEFAULT_FIND_LIMIT = 20
MAX_FIND_LIMIT = 500
MAX_SKIP = 10_000

DEFAULT_AGGREGATION_LIMIT = 100
MAX_AGGREGATION_LIMIT = 500
MAX_PIPELINE_STAGES = 20

MAX_FILTER_SIZE = 16_384
MAX_PIPELINE_SIZE = 32_768
MAX_EXECUTION_TIME_MS = 10_000

ALLOWED_AGGREGATION_STAGES = {
    "$match",
    "$project",
    "$sort",
    "$skip",
    "$limit",
    "$unwind",
    "$group",
    "$count",
    "$addFields",
    "$set",
    "$unset",
    "$replaceRoot",
    "$replaceWith",
    "$sortByCount",
}

FORBIDDEN_OPERATORS = {
    "$where",
    "$function",
    "$accumulator",
    "$out",
    "$merge",
    "$currentOp",
    "$listSessions",
    "$changeStream",
}


def validate_payload_size(
    payload: Any,
    max_size: int,
    payload_name: str,
) -> None:
    """Ensure a query payload is within the configured size limit."""

    try:
        encoded = json.dumps(payload, default=str).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ToolValidationError(
            f"{payload_name} must contain valid JSON data."
        ) from exc

    if len(encoded) > max_size:
        raise ToolValidationError(
            f"{payload_name} exceeds the maximum size of "
            f"{max_size} bytes."
        )


def validate_forbidden_operators(value: Any) -> None:
    """Recursively reject prohibited MongoDB operators."""

    if isinstance(value, dict):
        for key, nested_value in value.items():

            if key in FORBIDDEN_OPERATORS:
                raise ToolValidationError(
                    f"MongoDB operator '{key}' is not permitted."
                )

            validate_forbidden_operators(nested_value)

    elif isinstance(value, list):
        for item in value:
            validate_forbidden_operators(item)


def validate_projection(
    projection: dict[str, int] | None,
) -> None:
    """Validate MongoDB inclusion/exclusion projections."""

    if projection is None:
        return

    if not isinstance(projection, dict):
        raise ToolValidationError(
            "projection must be a JSON object."
        )

    for value in projection.values():
        if type(value) is not int or value not in (0, 1):
            raise ToolValidationError(
                "Projection values must be integer 0 or 1."
            )

    non_id_fields = {
        key: value
        for key, value in projection.items()
        if key != "_id"
    }

    has_inclusion = any(value == 1 for value in non_id_fields.values())
    has_exclusion = any(value == 0 for value in non_id_fields.values())

    if has_inclusion and has_exclusion:
        raise ToolValidationError(
            "Cannot mix inclusion and exclusion in a projection, "
            "except for excluding _id."
        )


def validate_sort(sort: dict[str, int] | None) -> None:
    """Validate sort field directions."""

    if sort is None:
        return

    if not isinstance(sort, dict):
        raise ToolValidationError(
            "sort must be a JSON object."
        )

    for direction in sort.values():
        if type(direction) is not int or direction not in (-1, 1):
            raise ToolValidationError(
                "Sort directions must be integer 1 or -1."
            )


def validate_pipeline(pipeline: list[dict[str, Any]]) -> None:
    """Validate an aggregation pipeline against the stage allowlist."""

    if not isinstance(pipeline, list) or not pipeline:
        raise ToolValidationError(
            "pipeline must be a non-empty list."
        )

    if len(pipeline) > MAX_PIPELINE_STAGES:
        raise ToolValidationError(
            f"Pipeline cannot exceed {MAX_PIPELINE_STAGES} stages."
        )

    validate_payload_size(
        pipeline,
        MAX_PIPELINE_SIZE,
        "Aggregation pipeline",
    )

    for position, stage in enumerate(pipeline):

        if not isinstance(stage, dict) or len(stage) != 1:
            raise ToolValidationError(
                f"Stage {position} must contain exactly one operator."
            )

        operator = next(iter(stage))

        if operator not in ALLOWED_AGGREGATION_STAGES:
            raise ToolValidationError(
                f"Aggregation stage '{operator}' is not permitted."
            )

        validate_forbidden_operators(stage)


async def get_collection(collection_name: str):
    """Return a collection after verifying that it exists."""

    if not isinstance(collection_name, str) or not collection_name.strip():
        raise ToolValidationError(
            "collection_name must be a non-empty string."
        )

    collection_name = collection_name.strip()

    try:
        client = get_mongo_client()
        database = client[MONGODB_DATABASE]

        collection_names = await database.list_collection_names()

        if collection_name not in collection_names:
            raise ToolValidationError(
                f"Collection '{collection_name}' does not exist "
                f"in database '{MONGODB_DATABASE}'."
            )

        return database[collection_name]

    except ToolValidationError:
        raise

    except PyMongoError as exc:
        raise ToolExecutionError(
            f"Unable to access collection: {exc}"
        ) from exc


def register_document_tools(mcp):

    @mcp.tool()
    async def find_documents(
        collection_name: str,
        filter: dict[str, Any] | None = None,
        projection: dict[str, int] | None = None,
        sort: dict[str, int] | None = None,
        skip: int = 0,
        limit: int = DEFAULT_FIND_LIMIT,
    ) -> dict[str, Any]:
        """
        Find documents using MongoDB filters.

        Supports filtering, projection, sorting and pagination.

        Example filter:
        {"address.city": "Hyderabad", "is_active": true}
        """

        if filter is None:
            filter = {}

        if not isinstance(filter, dict):
            raise ToolValidationError(
                "filter must be a JSON object."
            )

        validate_payload_size(
            filter,
            MAX_FILTER_SIZE,
            "Filter",
        )
        validate_forbidden_operators(filter)
        validate_projection(projection)
        validate_sort(sort)

        if type(skip) is not int or not 0 <= skip <= MAX_SKIP:
            raise ToolValidationError(
                f"skip must be between 0 and {MAX_SKIP}."
            )

        if (
            type(limit) is not int
            or not 1 <= limit <= MAX_FIND_LIMIT
        ):
            raise ToolValidationError(
                f"limit must be between 1 and {MAX_FIND_LIMIT}."
            )

        collection = await get_collection(collection_name)
        normalized_collection_name = collection.name

        try:
            cursor = collection.find(
                filter,
                projection=projection,
                max_time_ms=MAX_EXECUTION_TIME_MS,
            )

            if sort:
                cursor = cursor.sort(list(sort.items()))

            cursor = cursor.skip(skip).limit(limit)

            documents = await cursor.to_list(length=limit)

            return {
                "database": MONGODB_DATABASE,
                "collection": normalized_collection_name,
                "returned_count": len(documents),
                "skip": skip,
                "limit": limit,
                "documents": serialize_bson(documents),
            }

        except PyMongoError as exc:
            raise ToolExecutionError(
                f"MongoDB find operation failed: {exc}"
            ) from exc
        except Exception as exc:
            raise ToolExecutionError(
                f"Unexpected error while finding documents: {exc}"
            ) from exc
        finally:
            close_mongo_connection()

    @mcp.tool()
    async def aggregate_documents(
        collection_name: str,
        pipeline: list[dict[str, Any]],
        limit: int = DEFAULT_AGGREGATION_LIMIT,
    ) -> dict[str, Any]:
        """
        Execute a validated, read-only MongoDB aggregation pipeline.

        Supported stages include $match, $group, $sort, $project,
        $unwind, $count, $addFields and $sortByCount.

        The server applies a final result limit.

        Example:
        [
            {"$group": {
                "_id": "$status",
                "order_count": {"$sum": 1}
            }},
            {"$sort": {"order_count": -1}}
        ]
        """

        validate_pipeline(pipeline)

        if (
            type(limit) is not int
            or not 1 <= limit <= MAX_AGGREGATION_LIMIT
        ):
            raise ToolValidationError(
                f"limit must be between 1 and "
                f"{MAX_AGGREGATION_LIMIT}."
            )

        collection = await get_collection(collection_name)
        normalized_collection_name = collection.name

        # Copy the pipeline to avoid modifying the caller's input.
        safe_pipeline = [dict(stage) for stage in pipeline]

        # Enforce a maximum number of returned result documents.
        safe_pipeline.append({"$limit": limit})

        try:
            cursor = await collection.aggregate(
                safe_pipeline,
                allowDiskUse=False,
                maxTimeMS=MAX_EXECUTION_TIME_MS,
            )

            documents = await cursor.to_list(length=limit)

            return {
                "database": MONGODB_DATABASE,
                "collection": normalized_collection_name,
                "returned_count": len(documents),
                "limit": limit,
                "documents": serialize_bson(documents),
            }

        except PyMongoError as exc:
            raise ToolExecutionError(
                f"MongoDB aggregation failed: {exc}"
            ) from exc
        except Exception as exc:
            raise ToolExecutionError(
                f"Unexpected error while aggregating documents: {exc}"
            ) from exc
        finally:
            close_mongo_connection()
