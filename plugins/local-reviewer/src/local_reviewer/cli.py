from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .context import ReviewContext, collect_context
from .errors import LocalReviewerError
from .github import publish_comment
from .providers import available_provider, run_review_provider
from .render import render_markdown
from .schema import normalize_review


PLUGIN_ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = PLUGIN_ROOT / "prompts" / "technical-review.md"
SCHEMA_PATH = PLUGIN_ROOT / "schemas" / "review.schema.json"


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="local-reviewer",
        description="Run an x100-inspired local review with Codex or Claude Code.",
    )
    result.add_argument("--version", action="version", version=__version__)
    result.add_argument("--repo", type=Path, default=Path.cwd(), help="Repository checkout to review.")
    result.add_argument("--provider", choices=("auto", "codex", "claude"), default="auto")
    result.add_argument("--model", help="Optional provider-specific model name.")
    result.add_argument("--base", help="Comparison branch or ref for a local branch review.")
    result.add_argument("--head", default="HEAD", help="Head ref for a local branch review.")
    result.add_argument("--pr", type=int, help="GitHub pull request number. Defaults to the current branch PR.")
    result.add_argument("--no-auto-pr", action="store_true", help="Do not auto-detect the current branch PR.")
    result.add_argument("--uncommitted", action="store_true", help="Review tracked and untracked working-tree changes.")
    result.add_argument("--memory", type=Path, help="Optional operational-memory directory available to the reviewer.")
    result.add_argument("--timeout", type=positive_int, default=900, help="Provider timeout in seconds (default: 900).")
    result.add_argument("--format", choices=("markdown", "json"), default="markdown")
    result.add_argument("--save", type=Path, help="Also save the rendered result to this path.")
    result.add_argument("--show-prompt", action="store_true", help="Print the assembled prompt without invoking a provider.")
    result.add_argument("--publish", action="store_true", help="Create or update an idempotent GitHub PR comment.")
    return result


def build_prompt(context: ReviewContext) -> str:
    return PROMPT_PATH.read_text().replace("{{REVIEW_CONTEXT}}", context.prompt_payload())


def _json_output(
    review: dict[str, object],
    context: ReviewContext,
    *,
    provider: str,
    discarded: list[str],
) -> str:
    return json.dumps(
        {
            "provider": provider,
            "context": json.loads(context.prompt_payload()),
            "review": review,
            "discarded_findings": discarded,
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        context = collect_context(
            args.repo,
            base=args.base,
            head=args.head,
            pull_request=args.pr,
            auto_pull_request=not args.no_auto_pr,
            uncommitted=args.uncommitted,
            memory=args.memory,
        )
        prompt = build_prompt(context)
        if args.show_prompt:
            sys.stdout.write(prompt)
            return 0
        provider = available_provider(args.provider)
        raw = run_review_provider(
            provider,
            root=Path(context.root),
            prompt=prompt,
            schema_path=SCHEMA_PATH,
            model=args.model,
            timeout=args.timeout,
            additional_read_paths=(Path(context.memory_path),) if context.memory_path else (),
        )
        review, discarded = normalize_review(raw, context.changed_files)
        markdown = render_markdown(review, context, provider=provider, discarded=discarded)
        output = _json_output(review, context, provider=provider, discarded=discarded) if args.format == "json" else markdown
        if args.save:
            args.save.expanduser().resolve().write_text(output)
        sys.stdout.write(output)
        if args.publish:
            url = publish_comment(context, markdown, provider=provider)
            print(f"Published: {url}", file=sys.stderr)
        return 0
    except LocalReviewerError as exc:
        print(f"local-reviewer: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
