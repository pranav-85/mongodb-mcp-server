"""MongoDB connection management utilities.

This module provides a lazy, process-wide MongoDB client and helper
functions to retrieve the configured database instance.
"""

from __future__ import annotations

from threading import Lock

from pymongo import AsyncMongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from mongodb_mcp_server.config import MONGODB_DATABASE, MONGODB_URI



_client: AsyncMongoClient | AsyncMongoClient | None = None
_client_lock = Lock()



def get_mongo_client(*, uri: str | None = None) -> AsyncMongoClient:
	"""Return a shared MongoClient instance.

	The client is created lazily and reused for subsequent calls.
	"""
	global _client

	if _client is not None:
		return _client

	with _client_lock:
		if _client is not None:
			return _client

		connection_uri = uri or MONGODB_URI
		if not connection_uri:
			raise RuntimeError("MONGODB_URI is not configured.")

		_client = AsyncMongoClient(connection_uri, serverSelectionTimeoutMS=5000)
		return _client


def close_mongo_connection() -> None:
	"""Close the shared MongoClient instance if it exists."""
	global _client

	with _client_lock:
		if _client is not None:
			_client.close()
			_client = None
