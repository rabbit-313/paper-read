#!/usr/bin/env python3
"""Watch GitHub Issues and run local Codex paper-generation skills."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


REPO = "rabbit-313/paper-read"
LABEL = "paper-generate"


@dataclass
class Issue:
    number: int
    title: str
    body: str
    url: str
    labels: list[str]


@dataclass
class PaperRequest:
    issue: Issue
    paper_id: str
    paper_url: str
    title: str
    wants_translation: bool
    wants_slides: bool


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=check)


def ensure_clean_worktree(repo_dir: Path) -> None:
    result = run(["git", "status", "--short"], repo_dir)
    if result.stdout.strip():
        raise RuntimeError(
            "Working tree is not clean. Commit or stash local changes before running the watcher.\n"
            + result.stdout
        )


def list_issues(repo_dir: Path) -> list[Issue]:
    result = run(
        [
            "gh",
            "issue",
            "list",
            "--repo",
            REPO,
            "--state",
            "open",
            "--limit",
            "50",
            "--json",
            "number,title,body,url,labels",
        ],
        repo_dir,
    )
    data = json.loads(result.stdout or "[]")
    issues = [
        Issue(
            item["number"],
            item["title"],
            item.get("body") or "",
            item["url"],
            [label.get("name", "") for label in item.get("labels", [])],
        )
        for item in data
    ]
    return [issue for issue in issues if is_generation_issue(issue)]


def is_generation_issue(issue: Issue) -> bool:
    if LABEL in issue.labels:
        return True
    if issue.title.lower().startswith("generate translation and slides for"):
        return True
    return "Paper generation request" in issue.body


def parse_issue(issue: Issue) -> PaperRequest | None:
    body = issue.body
    paper_id = find_field(body, "Paper ID") or find_arxiv_id(body) or find_arxiv_id(issue.title)
    paper_url = find_field(body, "URL") or (f"https://arxiv.org/abs/{paper_id}" if paper_id else "")
    title = find_field(body, "Title") or issue.title
    if not paper_id and paper_url:
        paper_id = slugify(title)
    if not paper_id or not paper_url:
        return None
    body_lower = body.lower()
    wants_translation = "japanese translation" in body_lower or "translation" in body_lower
    wants_slides = "ochiai" in body_lower or "slides" in body_lower
    if not wants_translation and not wants_slides:
        wants_translation = True
        wants_slides = True
    return PaperRequest(issue, paper_id, paper_url, title, wants_translation, wants_slides)


def find_field(body: str, name: str) -> str:
    match = re.search(rf"^-\s*{re.escape(name)}:\s*(.+)$", body, re.MULTILINE)
    if match:
        return match.group(1).strip()
    heading = re.search(
        rf"^###\s*{re.escape(name)}\s*\n+\s*(.+?)(?:\n\s*\n###|\Z)",
        body,
        re.MULTILINE | re.DOTALL,
    )
    if not heading:
        return ""
    return heading.group(1).strip().splitlines()[0].strip()


def find_arxiv_id(text: str) -> str:
    match = re.search(r"(?:arxiv:|arxiv.org/(?:abs|pdf)/)?(\d{4}\.\d{4,5})(?:v\d+)?", text, re.I)
    return match.group(1) if match else ""


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value[:80] or "paper"


def build_prompt(request: PaperRequest, repo_dir: Path) -> str:
    outputs = []
    if request.wants_translation:
        outputs.append(f"- Use the translate-paper-pdf skill to create `papers/{request.paper_id}/translation/`.")
    if request.wants_slides:
        outputs.append(f"- Use the paper-ochiai-slides skill to create `papers/{request.paper_id}/slides/`.")
    output_text = "\n".join(outputs)
    return f"""You are working in {repo_dir}.

Generate local paper reading assets for this paper:
- Paper ID: {request.paper_id}
- Title: {request.title}
- URL: {request.paper_url}

Required outputs:
{output_text}

Keep the existing repository layout and top-level archive style.
Do not run destructive commands.
Do not commit or push; the watcher will handle git after you finish.
When finished, make sure each requested output has an index.html entry point.
"""


def run_codex(request: PaperRequest, repo_dir: Path, dry_run: bool) -> None:
    prompt = build_prompt(request, repo_dir)
    prompt_path = repo_dir / "recommendations" / "last-codex-request.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt, encoding="utf-8")
    if dry_run:
        print(prompt)
        return
    cmd = [
        "codex",
        "exec",
        "--cd",
        str(repo_dir),
        "--sandbox",
        "workspace-write",
        "--ask-for-approval",
        "never",
        prompt,
    ]
    print("Running:", " ".join(shlex.quote(part) for part in cmd[:8]), "<prompt>")
    subprocess.run(cmd, cwd=repo_dir, check=True)


def verify_outputs(request: PaperRequest, repo_dir: Path) -> list[str]:
    missing: list[str] = []
    if request.wants_translation:
        path = repo_dir / "papers" / request.paper_id / "translation" / "index.html"
        if not path.exists():
            missing.append(str(path.relative_to(repo_dir)))
    if request.wants_slides:
        path = repo_dir / "papers" / request.paper_id / "slides" / "index.html"
        if not path.exists():
            missing.append(str(path.relative_to(repo_dir)))
    return missing


def commit_and_push(request: PaperRequest, repo_dir: Path, push: bool) -> None:
    status = run(["git", "status", "--short"], repo_dir).stdout.strip()
    if not status:
        raise RuntimeError("Codex finished without producing git changes.")
    run(["git", "add", "papers", "index.html", "script.js", "styles.css", "recommendations"], repo_dir)
    message = f"Add generated assets for {request.paper_id}"
    run(["git", "commit", "-m", message], repo_dir)
    if push:
        run(["git", "push"], repo_dir)


def comment_and_close(request: PaperRequest, repo_dir: Path, push: bool) -> None:
    page_base = "https://rabbit-313.github.io/paper-read"
    lines = [
        "Generated locally with Codex skills.",
        "",
        f"- Translation: {page_base}/papers/{request.paper_id}/translation/",
        f"- Slides: {page_base}/papers/{request.paper_id}/slides/",
    ]
    if not push:
        lines.append("")
        lines.append("Note: watcher ran with --no-push, so Pages will update after pushing manually.")
    run(
        [
            "gh",
            "issue",
            "comment",
            str(request.issue.number),
            "--repo",
            REPO,
            "--body",
            "\n".join(lines),
        ],
        repo_dir,
    )
    run(["gh", "issue", "close", str(request.issue.number), "--repo", REPO], repo_dir)


def fail_issue(issue: Issue, repo_dir: Path, message: str) -> None:
    run(
        [
            "gh",
            "issue",
            "comment",
            str(issue.number),
            "--repo",
            REPO,
            "--body",
            f"Local generation failed:\n\n```text\n{message[:3500]}\n```",
        ],
        repo_dir,
        check=False,
    )


def process_once(repo_dir: Path, args: argparse.Namespace) -> int:
    ensure_clean_worktree(repo_dir)
    issues = list_issues(repo_dir)
    if not issues:
        print("No queued paper-generation issues.")
        return 0
    for issue in issues[: args.max_issues]:
        request = parse_issue(issue)
        if not request:
            fail_issue(issue, repo_dir, "Could not parse Paper ID or URL from the issue body.")
            continue
        print(f"Processing #{issue.number}: {request.paper_id}")
        try:
            run_codex(request, repo_dir, args.dry_run)
            if args.dry_run:
                continue
            missing = verify_outputs(request, repo_dir)
            if missing:
                raise RuntimeError("Missing expected outputs: " + ", ".join(missing))
            commit_and_push(request, repo_dir, push=not args.no_push)
            comment_and_close(request, repo_dir, push=not args.no_push)
        except Exception as exc:  # noqa: BLE001
            fail_issue(issue, repo_dir, str(exc))
            raise
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-dir", type=Path, default=Path.cwd())
    parser.add_argument("--poll", action="store_true", help="Keep polling instead of running once.")
    parser.add_argument("--interval", type=int, default=300, help="Polling interval in seconds.")
    parser.add_argument("--max-issues", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true", help="Print the Codex prompt without running Codex.")
    parser.add_argument("--no-push", action="store_true", help="Commit locally but do not push.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_dir = args.repo_dir.resolve()
    while True:
        try:
            process_once(repo_dir, args)
        except subprocess.CalledProcessError as exc:
            print(exc.stderr or exc.stdout or str(exc), file=sys.stderr)
            return exc.returncode
        except Exception as exc:  # noqa: BLE001
            print(str(exc), file=sys.stderr)
            return 1
        if not args.poll:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
