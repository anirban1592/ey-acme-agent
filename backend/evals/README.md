# Agent evals (DeepEval)

Golden-question eval suite for the main chat agent (`backend/agent/core.py`).
For each golden question we know, up front, which top-level tool(s) the
agent should call and what the reply should say — this suite runs the real
agent and scores both dimensions.

## What's here

| File | Purpose |
|---|---|
| `.dataset.json` | The golden set: question, expected tool(s), expected response, and which seeded user asks it. |
| `agent_runner.py` | Runs the real agent singleton (`backend/agent/core.py`'s `get_agent()`) for one question, capturing the final reply text and every top-level tool call via a callback. |
| `metrics.py` | The two DeepEval metrics: `ToolCorrectnessMetric` (tool selection) and a custom `GEval` criterion (response correctness). |
| `test_golden_eval.py` | The pytest suite `deepeval test run` executes. |

## Why this is two metrics, not one

- **Tool selection** (`ToolCorrectnessMetric`) — did the agent call the tool(s) the golden says it should, e.g. `retrieve_customer_issues` vs. `consult_summarizer_agent` vs. `get_customer_profile`? Matched by tool name only (order-independent), so an extra internal tool call doesn't tank the score — only whether every expected tool was actually reached.
- **Response correctness** (`GEval`) — does the reply actually say the right thing (right customer, right issues, right RBAC outcome, exact rejection text for guardrail cases, etc.)? There's no predefined DeepEval metric for this since correctness here is entirely domain-specific, so it's a custom criterion judged by an LLM against each golden's `expected_output`.

A case can pass tool selection and fail response correctness (called the right tool, said the wrong thing) or vice versa (answered correctly some other way) — the two are reported separately.

## Dataset shape

Each entry in `.dataset.json` is a DeepEval `Golden`:

```json
{
  "name": "crm-profile-rbac-denied-google-bob",
  "input": "What's Google's account tier and risk level?",
  "expected_tools": [{"name": "get_customer_profile"}],
  "expected_output": "get_customer_profile is restricted to the admin role. bob (sales) must be denied ...",
  "additional_metadata": {"username": "bob"},
  "comments": "RBAC negative case: CRM profile tool is admin-only, unlike the issues/summarizer tools."
}
```

`additional_metadata.username` must be one of the seeded users in
`agent_runner.SEED_USERS` (`alice`=admin, `bob`=sales, `charlie`=operations,
`tony`=support, `eve`=no role) — these mirror `postgres/initv2.sql`'s seed
data exactly. `expected_output` can be an exact required string (the fixed
guardrail rejection message) or a description of the facts/shape the reply
must contain — the GEval judge is told to handle both forms.

The starter set (19 cases) was hand-drafted from the real seeded
customers/issues/roles to cover: all 5 tools (`retrieve_customer_issues`,
`retrieve_issue_updates` via `consult_summarizer_agent`,
`get_customer_profile`, `consult_escalation_agent`), RBAC positive/negative
cases per persona and per role (including the admin-only CRM gate and the
no-role `eve` edge case), a composite (two-shape) answer, plain chat, and
both guardrail-block paths (prompt injection, off-topic). Edit or extend
`.dataset.json` directly — it's a plain JSON array, no generator involved.

Not covered yet: multi-turn follow-ups (e.g. the "narrow follow-up answered
from conversation history" behavior from `CLAUDE.md`'s 2026-07-20 decision)
— this suite is single-turn QA pairs by design; each case runs in its own
fresh thread. Add a multi-turn suite separately if that behavior needs
covering.

## Running it

Requires the live stack — this suite calls the real agent, not a mock:

```bash
docker compose up -d postgres mcp redis
```

Then, with `OPENAI_API_KEY` set (used both by the agent and, by default, as
DeepEval's judge model) and the rest of `backend/`'s usual env vars
available (`MCP_SERVER_URL`, `POSTGRES_*`, `REDIS_*` — see `.env.example`;
override `*_HOST` to `localhost` if running from the host rather than
inside the `backend` container):

```bash
cd backend
pip install -r requirements.txt
deepeval test run evals/test_golden_eval.py --identifier "golden-eval-round-1"
```

For a larger dataset later, add `--num-processes 5 --ignore-errors
--skip-on-missing-params` (see the DeepEval skill's `pytest-e2e-evals.md`
reference). Note that `test_golden_eval.py` runs every golden through the
live agent once at collection time (before any test executes) — even
`--collect-only` will make real LLM/DB/MCP calls.

`deepeval test run` prints a per-case pass/fail table and an overall
summary — that's the "what percentage is passing" answer. Set
`DEEPEVAL_MODEL` to override the judge model (defaults to DeepEval's own
default OpenAI model).

## Iterating on failures

When a case fails, read which metric failed (tool selection vs. response
correctness) and the printed reason before changing anything:
- Tool selection failures usually mean the system prompt
  (`BASE_SYSTEM_PROMPT` in `backend/agent/core.py`) doesn't clearly steer
  the model to the right tool for that phrasing.
- Response correctness failures usually mean either a real RBAC/logic bug,
  or the golden's `expected_output` is stricter than what's actually
  required — check both before assuming the app is wrong.

This suite intentionally has no DeepEval tracing/`@observe` instrumentation
(the project already has LangSmith tracing for observability); add it later
if failures need step-by-step inspection beyond the printed reason.
