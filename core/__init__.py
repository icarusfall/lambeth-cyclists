"""Shared across the processor, the portal and the MCP server.

These three ran as separate repos and drifted: the same model name in two
files, one of which went stale for six weeks; the same Notion helpers copied
between services; the same secret under two names. Anything used by more than
one service belongs here so there is one copy to keep right.
"""
