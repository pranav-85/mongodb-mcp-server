import os

MONGODB_URI = os.environ.get("MONGODB_URI")
MONGODB_DATABASE = os.environ.get("MONGODB_DATABASE")

if not MONGODB_URI or not MONGODB_DATABASE:
    raise RuntimeError(
        "MONGODB_URI and MONGODB_DATABASE must be provided by the MCP server configuration."
    )