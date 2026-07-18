import logging
import os

from fastmcp import Context, FastMCP
from fastmcp.server.lifespan import lifespan

from db import create_pool, fetch_customer_issues
from models import Issue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@lifespan
async def app_lifespan(server):
    pool = await create_pool()
    try:
        yield {"pool": pool}
    finally:
        await pool.close()
        logger.info("Database connection pool closed")


mcp = FastMCP("issues-mcp", lifespan=app_lifespan)


@mcp.tool(annotations={"readOnlyHint": True})
async def retrieve_customer_profile(
    customer_name: str, role: str, ctx: Context
) -> list[Issue]:
    """Return the issues for a customer, scoped to the caller's role.

    Issues are filtered to those where issues.domain matches role, except
    when role is 'admin', in which case all of the customer's issues are
    returned regardless of domain.
    """
    pool = ctx.lifespan_context["pool"]
    return await fetch_customer_issues(pool, customer_name, role)


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host=os.getenv("MCP_HOST", "0.0.0.0"),
        port=int(os.getenv("MCP_PORT", "9000")),
    )
