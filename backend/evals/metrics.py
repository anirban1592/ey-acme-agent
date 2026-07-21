"""
DeepEval metric instances for the golden-question eval suite.

Kept in a separate module (per DeepEval convention) so test_golden_eval.py
stays focused on running the app and asserting, not constructing metrics.

Both metrics judge against a real OpenAI model — DEEPEVAL_MODEL lets that be
overridden without touching code, defaulting to DeepEval's own default model
when unset, matching this project's existing MAIN_AGENT_MODEL/GUARDRAIL_MODEL
env-var convention.
"""

import os

from deepeval.metrics import GEval, ToolCorrectnessMetric
from deepeval.test_case import LLMTestCaseParams

_JUDGE_MODEL = os.getenv("DEEPEVAL_MODEL") or None

# "Did the agent call the tool(s) we expected it to?" — matches tools_called
# (captured live via agent_runner.ToolCallRecorder) against each golden's
# expected_tools by name only (default evaluation_params=[] ignores
# input_parameters/output), non-exact/order-independent, so extra internal
# tool calls (e.g. the structured-output finalization step) don't tank the
# score — only whether every expected tool was actually reached.
TOOL_SELECTION_METRICS = [
    ToolCorrectnessMetric(threshold=1.0),
]

# "Is the actual response what we expected?" — a custom GEval criterion,
# since correctness here is domain-specific (RBAC-scoped issue/customer
# data, exact rejection text for guardrail blocks, etc.) with no predefined
# DeepEval metric for it. Judges actual_output against each golden's
# expected_output description.
RESPONSE_CORRECTNESS_METRICS = [
    GEval(
        name="Response Correctness",
        criteria=(
            "Determine whether 'actual output' satisfies what 'expected output' "
            "describes as correct for this customer-issue-tracking assistant. "
            "'expected output' is sometimes an exact required string (e.g. a "
            "fixed rejection message) and sometimes a description of the facts "
            "and shape the reply must contain (e.g. which issues, which "
            "customer, which fields) — judge against whichever form it takes. "
            "The reply must not contradict, omit, or fabricate facts relative "
            "to 'expected output', and must not leak data it explicitly should "
            "not have access to (e.g. another role's issues, CRM profile "
            "fields for a non-admin caller)."
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        model=_JUDGE_MODEL,
        threshold=0.5,
    ),
]

GOLDEN_EVAL_METRICS = TOOL_SELECTION_METRICS + RESPONSE_CORRECTNESS_METRICS
