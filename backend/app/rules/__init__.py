"""Deterministic alert rules and score factors. Owned by Rudra.

Rules read normalized `Observation`s from `app.ingestion` and never call a feed, the
model, or Gemini. No AI output can create, shorten, or clear an alert.
"""
