"""Agentic layer for the app.

A minimal, provider-clean scaffold around Anthropic's Claude: a client factory
(`client.py`), a tool registry (`tools.py`), and a tool-using agent loop
(`service.py`). Wire new capabilities by adding tools in `tools.py`; the agent
loop and the API route need no changes.
"""
