"""
Supervisor read tools.

Phase 2 — wrappers around existing FastAPI services that expose structured
JSON the supervisor agent (Phase 3) can reason over via tool calls.

All tools follow the same shape:
- Input: a SQLAlchemy Session + simple primitive args
- Output: a small dict with the metric, the comparison window, and a
  short prose summary for the agent's prompt context.
"""
