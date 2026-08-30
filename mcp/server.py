"""Lambeth Cyclists MCP Server — CycleBot over MCP.

A facade, not an implementation. The tools, the Notion reading and the
formatting all live in `core.cyclebot`; this file exposes them over MCP for
clients that can only speak MCP (Claude Desktop and the like).

It used to be the only way to reach the tools, which meant the portal's own
chat page went out to the public internet and back to use them. The portal now
calls `core.cyclebot.answer()` directly, so nothing internal depends on this
server any more. It is kept because MCP is the one way a third-party client
could ever reach CycleBot, and at this size that option is close to free.

If you stop deploying it, the tools keep working everywhere else — that is the
point of it being a facade.

Run:
    python server.py            # streamable-http, requires MCP_API_KEY
    python server.py stdio      # local pipe, no key needed
"""

import os
import sys
import hmac
import json
import logging

from mcp.server.fastmcp import FastMCP

from core.cyclebot import DATABASES, TOOLS, describe

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP(
    "lambeth-cyclists",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8000)),
)

# FastMCP takes the name and the argument schema off each function, the same
# material core.cyclebot.anthropic_tools() uses. The description is passed
# explicitly so both go through core.cyclebot.describe(): FastMCP would
# otherwise use the raw __doc__, leaving MCP clients with the same text
# indented differently. One definition, described one way.
for _fn in TOOLS.values():
    mcp.tool(description=describe(_fn))(_fn)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
# Comma-separated so each caller can hold its own key: a single shared secret
# would mean rotating it for one caller breaks the others.
MCP_API_KEYS = [k.strip() for k in os.environ.get("MCP_API_KEY", "").split(",") if k.strip()]


class BearerAuthMiddleware:
    """ASGI middleware requiring `Authorization: Bearer <MCP_API_KEY>`.

    Without this check the server hands every database in DATABASES —
    committee action items and councillor research included — to anyone who
    knows the Railway URL.
    """

    def __init__(self, app, api_keys):
        self.app = app
        self.api_keys = list(api_keys)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        supplied = headers.get(b"authorization", b"").decode("latin-1")
        prefix = "Bearer "
        token = supplied[len(prefix):] if supplied.startswith(prefix) else ""

        # compare_digest against each key rather than `in`, so the check does
        # not leak how much of a key matched via timing.
        if not any(hmac.compare_digest(token, k) for k in self.api_keys):
            logger.warning("Rejected unauthenticated request to %s", scope.get("path"))
            body = json.dumps({"error": "unauthorized"}).encode()
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"www-authenticate", b'Bearer realm="lambeth-cyclists-mcp"'),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return

        await self.app(scope, receive, send)


# ---------------------------------------------------------------------------
# Server startup
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    transport = sys.argv[1] if len(sys.argv) > 1 else "streamable-http"

    if transport == "stdio":
        # Local process pipe — the transport is its own trust boundary.
        logger.info(
            "Starting Lambeth Cyclists MCP server — transport=stdio, %d tools",
            len(TOOLS),
        )
        mcp.run(transport="stdio")
    else:
        if not MCP_API_KEYS:
            sys.exit(
                "MCP_API_KEY is not set. This server exposes read access to every "
                "Notion database in core.cyclebot.DATABASES, so it refuses to start "
                "unauthenticated over HTTP. Set MCP_API_KEY to every key its callers "
                "send, comma-separated."
            )

        import uvicorn

        port = int(os.environ.get("PORT", 8000))
        logger.info(
            "Starting Lambeth Cyclists MCP server — port=%s transport=%s, "
            "%d tools over %d databases (bearer auth on, %d key(s) accepted)",
            port, transport, len(TOOLS), len(DATABASES), len(MCP_API_KEYS),
        )
        uvicorn.run(
            BearerAuthMiddleware(mcp.streamable_http_app(), MCP_API_KEYS),
            host="0.0.0.0",
            port=port,
        )
