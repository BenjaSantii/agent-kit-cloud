from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .errors import LocalReviewerError


def available_provider(requested: str) -> str:
    if requested != "auto":
        if shutil.which(requested) is None:
            raise LocalReviewerError(f"Provider executable is not available: {requested}")
        return requested
    for candidate in ("codex", "claude"):
        if shutil.which(candidate):
            return candidate
    raise LocalReviewerError("Neither codex nor claude is available on PATH.")


def _run_provider(
    command: list[str],
    *,
    cwd: Path,
    prompt: str,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            input=prompt,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise LocalReviewerError(f"Provider timed out after {timeout} seconds.") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown provider failure"
        raise LocalReviewerError(f"Provider exited with {result.returncode}: {detail}")
    return result


def _parse_json_text(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        raise LocalReviewerError("Provider result did not contain structured JSON.")
    text = value.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LocalReviewerError(f"Provider returned invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise LocalReviewerError("Provider JSON result must be an object.")
    return parsed


def run_codex(
    *,
    root: Path,
    prompt: str,
    schema_path: Path,
    model: str | None,
    timeout: int,
    additional_read_paths: tuple[Path, ...] = (),
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="local-reviewer-codex-") as raw:
        output_path = Path(raw) / "review.json"
        command = [
            "codex",
            "exec",
            "--sandbox",
            "read-only",
            "--ephemeral",
            "--ignore-user-config",
            "--color",
            "never",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "--cd",
            str(root),
        ]
        if model:
            command.extend(["--model", model])
        for path in additional_read_paths:
            command.extend(["--add-dir", str(path)])
        command.append("-")
        _run_provider(command, cwd=root, prompt=prompt, timeout=timeout)
        if not output_path.exists():
            raise LocalReviewerError("Codex completed without writing its final structured response.")
        return _parse_json_text(output_path.read_text())


def run_claude(
    *,
    root: Path,
    prompt: str,
    schema_path: Path,
    model: str | None,
    timeout: int,
    additional_read_paths: tuple[Path, ...] = (),
) -> dict[str, Any]:
    schema = json.dumps(json.loads(schema_path.read_text()), separators=(",", ":"))
    command = [
        "claude",
        "--print",
        "--output-format",
        "json",
        "--json-schema",
        schema,
        "--permission-mode",
        "plan",
        "--no-session-persistence",
        "--safe-mode",
        "--tools",
        "Read,Glob,Grep,Bash",
        "--disallowedTools",
        "Edit,Write,NotebookEdit,WebFetch,WebSearch",
    ]
    if model:
        command.extend(["--model", model])
    for path in additional_read_paths:
        command.extend(["--add-dir", str(path)])
    result = _run_provider(command, cwd=root, prompt=prompt, timeout=timeout)
    try:
        envelope = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise LocalReviewerError(f"Claude returned an invalid JSON envelope: {exc}") from exc
    if isinstance(envelope, dict) and envelope.get("structured_output") is not None:
        return _parse_json_text(envelope["structured_output"])
    if isinstance(envelope, dict) and envelope.get("result") is not None:
        return _parse_json_text(envelope["result"])
    return _parse_json_text(envelope)


def run_review_provider(
    provider: str,
    *,
    root: Path,
    prompt: str,
    schema_path: Path,
    model: str | None,
    timeout: int,
    additional_read_paths: tuple[Path, ...] = (),
) -> dict[str, Any]:
    if provider == "codex":
        return run_codex(
            root=root,
            prompt=prompt,
            schema_path=schema_path,
            model=model,
            timeout=timeout,
            additional_read_paths=additional_read_paths,
        )
    if provider == "claude":
        return run_claude(
            root=root,
            prompt=prompt,
            schema_path=schema_path,
            model=model,
            timeout=timeout,
            additional_read_paths=additional_read_paths,
        )
    raise LocalReviewerError(f"Unsupported provider: {provider}")
