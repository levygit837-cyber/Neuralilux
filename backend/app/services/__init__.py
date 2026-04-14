"""Service package for application integrations and business logic.

Avoid eager imports here so lightweight modules can import specific services
without pulling optional dependencies during startup or tests.
"""

# Vertex AI imports (lazy to avoid loading google-genai unless needed)
__all__: list[str] = []
