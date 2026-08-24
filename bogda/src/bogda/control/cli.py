import argparse
import json
from pathlib import Path
import sys
from typing import Sequence
from uuid import uuid4

from bogda.artifacts import load_run_result
from bogda.contracts import (
    ArtifactSpec,
    JobRequest,
    ResourceClass,
    RunResult,
    ScientificStatus,
)
from bogda.flows import review_run_result, run_shell_job
from bogda.policy import PolicyStore


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="bogda")
    commands = root.add_subparsers(dest="command", required=True)

    demo = commands.add_parser("demo")
    demo.add_argument("--attempts-root", default=".bogda-runs")
    demo.add_argument("--policy-path", default=".bogda-policy.json")
    demo.add_argument("--project-id", default="bogda")

    result = commands.add_parser("result")
    result.add_argument("run_id")

    review = commands.add_parser("review")
    review.add_argument("run_id")
    review.add_argument(
        "status",
        choices=[
            ScientificStatus.ACCEPTED.value,
            ScientificStatus.REJECTED.value,
            ScientificStatus.INCONCLUSIVE.value,
        ],
    )
    review.add_argument("--summary")
    return root


def print_result(result: RunResult) -> None:
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


def demo_request(
    policy_store: PolicyStore | None = None,
    project_id: str = "bogda",
) -> JobRequest:
    store = policy_store or PolicyStore(".bogda-policy.json")
    resolved = store.resolve_mode(project_id)
    return JobRequest(
        job_id=f"demo-{uuid4()}",
        project_id=project_id,
        task_type="shell",
        resource_class=ResourceClass.CPU,
        autonomy_mode=resolved.effective_mode,
        policy_revision=resolved.policy_revision,
        parameters={
            "argv": [
                sys.executable,
                "-c",
                "from pathlib import Path; Path('result.txt').write_text('bogda ok', encoding='utf-8')",
            ]
        },
        expected_artifacts=(ArtifactSpec(path="result.txt"),),
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "demo":
        request = demo_request(
            PolicyStore(args.policy_path),
            project_id=args.project_id,
        )
        result = RunResult.model_validate(
            run_shell_job(
                request.model_dump(mode="json"),
                str(Path(args.attempts_root).resolve()),
            )
        )
        print_result(result)
        return 0
    if args.command == "result":
        result = load_run_result(args.run_id)
        if result is None:
            print(f"run result not found: {args.run_id}", file=sys.stderr)
            return 1
        print_result(result)
        return 0

    reviewed = RunResult.model_validate(
        review_run_result(args.run_id, args.status, args.summary)
    )
    print_result(reviewed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
