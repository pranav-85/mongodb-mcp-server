
from mcp.server.mcpserver.exceptions import ToolError


class ToolValidationError(ToolError):
    """Raised when a tool receives invalid input."""


class ToolExecutionError(ToolError):
    """Raised when a database tool operation fails."""
