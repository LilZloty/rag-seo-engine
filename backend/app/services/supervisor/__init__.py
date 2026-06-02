"""
Supervisor Agent — meta-layer over Example Store's SEO/AEO/GEO pipeline.

Phase 0+1: news ingestion. Reads SEO/AEO/GEO news daily, summarizes,
and exposes it to the operator. No reasoning loop yet — that's phase 3+.

The IP is `supervisor_brief.md` (the system prompt) plus the curated
RSS source list in `sources.py`.
"""
