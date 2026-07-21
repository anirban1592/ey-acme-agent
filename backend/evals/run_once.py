"""
One-off runner: executes the golden dataset against the live agent exactly
once and writes a JSON report (backend/evals/eval_report.json) with the
per-case pass/fail for both metrics plus overall pass percentages.

This is the "just tell me the pass percentage" entry point — for the
committed, CI-integrated suite (`deepeval test run`), use
test_golden_eval.py instead. Requires the same live infra as that file (see
README.md): Postgres, the mcp/ server, Redis, and a real OPENAI_API_KEY.

Usage:
    cd backend && python -m evals.run_once [--limit N]

--limit N runs only the first N goldens — a quick smoke test before
committing to a full run, useful when working around OpenAI rate limits.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from deepeval import evaluate
from deepeval.dataset import EvaluationDataset
from deepeval.evaluate.configs import ErrorConfig

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from evals.agent_runner import build_test_cases  # noqa: E402
from evals.metrics import GOLDEN_EVAL_METRICS  # noqa: E402

DATASET_PATH = Path(__file__).parent / ".dataset.json"
REPORT_PATH = Path(__file__).parent / "eval_report.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N goldens.")
    args = parser.parse_args()

    dataset = EvaluationDataset()
    dataset.add_goldens_from_json_file(file_path=str(DATASET_PATH))

    n = args.limit or len(dataset.goldens)
    print(f"Running {n} golden case(s) through the live agent...")
    asyncio.run(build_test_cases(dataset, limit=args.limit))

    result = evaluate(
        test_cases=dataset.test_cases,
        metrics=GOLDEN_EVAL_METRICS,
        error_config=ErrorConfig(ignore_errors=True),
    )

    cases = []
    tool_selection_passes = 0
    response_correctness_passes = 0
    for test_result in result.test_results:
        metrics_out = []
        for metric_data in test_result.metrics_data or []:
            metrics_out.append(
                {
                    "name": metric_data.name,
                    "success": metric_data.success,
                    "score": metric_data.score,
                    "threshold": metric_data.threshold,
                    "reason": metric_data.reason,
                }
            )
            if metric_data.name.startswith("Tool Correctness") and metric_data.success:
                tool_selection_passes += 1
            if metric_data.name.startswith("Response Correctness") and metric_data.success:
                response_correctness_passes += 1

        cases.append(
            {
                "name": test_result.name,
                "input": test_result.input,
                "actual_output": test_result.actual_output,
                "expected_output": test_result.expected_output,
                "overall_success": test_result.success,
                "metrics": metrics_out,
            }
        )

    total = len(result.test_results)
    overall_passes = sum(1 for tr in result.test_results if tr.success)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_cases": total,
        "overall_pass_count": overall_passes,
        "overall_pass_rate": round(overall_passes / total, 4) if total else None,
        "tool_selection_pass_count": tool_selection_passes,
        "tool_selection_pass_rate": round(tool_selection_passes / total, 4) if total else None,
        "response_correctness_pass_count": response_correctness_passes,
        "response_correctness_pass_rate": round(response_correctness_passes / total, 4) if total else None,
        "cases": cases,
    }

    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        f"\nTool selection:        {tool_selection_passes}/{total} passed "
        f"({report['tool_selection_pass_rate']:.0%})"
    )
    print(
        f"Response correctness:  {response_correctness_passes}/{total} passed "
        f"({report['response_correctness_pass_rate']:.0%})"
    )
    print(
        f"Overall (both metrics): {overall_passes}/{total} passed "
        f"({report['overall_pass_rate']:.0%})"
    )
    print(f"\nFull report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
