import os

# Importing `agent.*` (even just agent.response_types) runs agent/__init__.py,
# which eagerly imports customer_profile.py — and unlike core.py's lazy
# get_agent(), customer_profile.py constructs a real ChatOpenAI client at
# module import time. Without a key that construction raises OpenAIError,
# so any test that merely imports something under agent/ would fail in CI
# (the fast unit-tests job has no OPENAI_API_KEY secret). Same placeholder
# convention as docker-compose's "mock-key" fallback — client construction
# doesn't hit the network, only real .ainvoke() calls would, and these tests
# never make one.
os.environ.setdefault("OPENAI_API_KEY", "test-key")
