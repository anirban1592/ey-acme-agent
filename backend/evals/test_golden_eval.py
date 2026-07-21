"""
Golden-question eval suite: for each case in .dataset.json, runs the real
agent (as the seeded user named in the golden's additional_metadata) and
asserts on two things per DeepEval metric:
  - TOOL SELECTION: did the agent call the tool(s) we expected? (ToolCorrectnessMetric)
  - RESPONSE CORRECTNESS: does the reply match what we expected? (GEval)

Run with:
    deepeval test run backend/evals/test_golden_eval.py

Requires the live stack (Postgres, the mcp/ server, Redis) reachable via the
usual MCP_SERVER_URL/POSTGRES_*/REDIS_* env vars, plus a real OPENAI_API_KEY
(both for the agent itself and as DeepEval's default judge model) — see
backend/evals/README.md.

All 19 goldens are run through the agent up front, inside one asyncio.run()
call, before any pytest assertion happens. This is deliberate, not just a
style choice: the agent singleton's Redis checkpointer and MCP HTTP client
(backend/agent/checkpointer.py, backend/agent/mcp_client.py) bind to
whichever asyncio event loop first builds them. pytest-asyncio's default of
handing each test its own fresh loop would break every case after the first
against those loop-bound clients. Building every LLMTestCase in a single
loop first, then asserting synchronously per case, avoids that — and is
DeepEval's own documented pattern for pre-built test cases (see
EvaluationDataset.add_test_case + parametrizing over dataset.test_cases).
"""

import asyncio
from pathlib import Path

import pytest
from deepeval import assert_test
from deepeval.dataset import EvaluationDataset
from deepeval.test_case import LLMTestCase

from agent_runner import build_test_cases
from metrics import GOLDEN_EVAL_METRICS

DATASET_PATH = Path(__file__).parent / ".dataset.json"

dataset = EvaluationDataset()
dataset.add_goldens_from_json_file(file_path=str(DATASET_PATH))

asyncio.run(build_test_cases(dataset))


@pytest.mark.parametrize(
    "test_case",
    dataset.test_cases,
    ids=[tc.name for tc in dataset.test_cases],
)
def test_golden_eval(test_case: LLMTestCase):
    assert_test(test_case=test_case, metrics=GOLDEN_EVAL_METRICS)
