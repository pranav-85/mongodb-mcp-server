
from mcp.server import MCPServer

from mongodb_mcp_server.tools.database_tools import register_database_tools
from mongodb_mcp_server.tools.collection_tools import register_collection_tools
from mongodb_mcp_server.tools.document_tools import register_document_tools


mcp = MCPServer(
    name="MongoDB MCP Server",
    instructions=(
        "A read-only MCP server for exploring and querying "
        "the configured MongoDB database."
    ),
)

register_database_tools(mcp)
register_collection_tools(mcp)
register_document_tools(mcp)


if __name__ == "__main__":
    mcp.run()
