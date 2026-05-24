#!/usr/bin/env python3
"""Collect daily ML paper candidates and write a readable recommendation digest."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ARXIV_API = "https://export.arxiv.org/api/query"
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
HN_API = "https://hn.algolia.com/api/v1/search_by_date"

DEFAULT_QUERIES = [
    "recommender systems deep learning",
    "recommendation system LLM",
    "retrieval recommendation ranking",
    "collaborative filtering neural",
    "generative recommender systems",
]

TOPICS = {
    "recommender": "推薦システム",
    "recommendation": "推薦システム",
    "ranking": "ランキング",
    "retrieval": "検索・ retrieval",
    "collaborative": "協調フィルタリング",
    "graph": "グラフ推薦",
    "llm": "LLM x 推薦",
    "language model": "LLM x 推薦",
    "diffusion": "生成モデル",
    "bandit": "バンディット",
    "reinforcement": "強化学習",
}


@dataclass
class Candidate:
    title: str
    url: str
    source: str
    abstract: str = ""
    authors: list[str] = field(default_factory=list)
    published: str = ""
    venue: str = ""
    citation_count: int | None = None
    influential_citation_count: int | None = None
    arxiv_id: str | None = None
    discussion_count: int | None = None
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)

    def key(self) -> str:
        if self.arxiv_id:
            return f"arxiv:{self.arxiv_id.lower()}"
        return normalize_title(self.title)


def normalize_title(title: str) -> str:
    title = re.sub(r"[^a-z0-9]+", " ", title.lower())
    return re.sub(r"\s+", " ", title).strip()


def request_json(url: str, params: dict[str, Any], timeout: int = 30) -> Any:
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{url}?{query}",
        headers={"User-Agent": "paper-read-daily-recommender/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def request_text(url: str, params: dict[str, Any], timeout: int = 30) -> str:
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{url}?{query}",
        headers={"User-Agent": "paper-read-daily-recommender/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read().decode("utf-8")


def fetch_arxiv(query: str, max_results: int) -> list[Candidate]:
    terms = " AND ".join(f'all:"{term}"' for term in query.split())
    search_query = f"(cat:cs.IR OR cat:cs.LG OR cat:cs.AI) AND ({terms})"
    xml_text = request_text(
        ARXIV_API,
        {
            "search_query": search_query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "start": 0,
            "max_results": max_results,
        },
    )
    root = ET.fromstring(xml_text)
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    candidates: list[Candidate] = []
    for entry in root.findall("atom:entry", ns):
        title = compact_text(entry.findtext("atom:title", default="", namespaces=ns))
        abstract = compact_text(entry.findtext("atom:summary", default="", namespaces=ns))
        url = entry.findtext("atom:id", default="", namespaces=ns)
        published = entry.findtext("atom:published", default="", namespaces=ns)[:10]
        authors = [
            compact_text(author.findtext("atom:name", default="", namespaces=ns))
            for author in entry.findall("atom:author", ns)
        ]
        arxiv_id = normalize_arxiv_id(url.rstrip("/").split("/")[-1]) if url else None
        candidates.append(
            Candidate(
                title=title,
                url=url,
                source="arXiv",
                abstract=abstract,
                authors=[a for a in authors if a],
                published=published,
                arxiv_id=arxiv_id,
            )
        )
    return candidates


def fetch_semantic_scholar(query: str, limit: int) -> list[Candidate]:
    data = request_json(
        SEMANTIC_SCHOLAR_API,
        {
            "query": query,
            "limit": limit,
            "fields": ",".join(
                [
                    "title",
                    "abstract",
                    "url",
                    "year",
                    "venue",
                    "citationCount",
                    "influentialCitationCount",
                    "externalIds",
                    "authors",
                    "publicationDate",
                ]
            ),
        },
    )
    candidates: list[Candidate] = []
    for paper in data.get("data", []):
        title = compact_text(paper.get("title") or "")
        if not title:
            continue
        external_ids = paper.get("externalIds") or {}
        arxiv_id = normalize_arxiv_id(external_ids.get("ArXiv") or "")
        url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else paper.get("url", "")
        authors = [a.get("name", "") for a in paper.get("authors", [])[:6]]
        candidates.append(
            Candidate(
                title=title,
                url=url,
                source="Semantic Scholar",
                abstract=compact_text(paper.get("abstract") or ""),
                authors=[a for a in authors if a],
                published=paper.get("publicationDate") or str(paper.get("year") or ""),
                venue=paper.get("venue") or "",
                citation_count=paper.get("citationCount"),
                influential_citation_count=paper.get("influentialCitationCount"),
                arxiv_id=arxiv_id,
            )
        )
    return candidates


def fetch_hacker_news(query: str, days: int, limit: int) -> list[Candidate]:
    since = int((dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).timestamp())
    data = request_json(
        HN_API,
        {
            "query": query,
            "tags": "story",
            "numericFilters": f"created_at_i>{since}",
            "hitsPerPage": limit,
        },
    )
    candidates: list[Candidate] = []
    for hit in data.get("hits", []):
        title = compact_text(hit.get("title") or hit.get("story_title") or "")
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        if not title or not url:
            continue
        candidates.append(
            Candidate(
                title=title,
                url=url,
                source="Hacker News",
                published=hit.get("created_at", "")[:10],
                discussion_count=hit.get("num_comments"),
            )
        )
    return candidates


def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def normalize_arxiv_id(value: str) -> str:
    return re.sub(r"v\d+$", "", value.strip())


def merge_candidates(candidates: list[Candidate]) -> list[Candidate]:
    merged: dict[str, Candidate] = {}
    for item in candidates:
        key = item.key()
        if key not in merged:
            merged[key] = item
            continue
        base = merged[key]
        base.source = " / ".join(sorted(set(base.source.split(" / ") + item.source.split(" / "))))
        base.abstract = base.abstract or item.abstract
        base.url = base.url or item.url
        base.authors = base.authors or item.authors
        base.published = newest_date(base.published, item.published)
        base.venue = base.venue or item.venue
        base.citation_count = max_optional(base.citation_count, item.citation_count)
        base.influential_citation_count = max_optional(
            base.influential_citation_count, item.influential_citation_count
        )
        base.discussion_count = max_optional(base.discussion_count, item.discussion_count)
    return list(merged.values())


def newest_date(left: str, right: str) -> str:
    return max(left or "", right or "")


def max_optional(left: int | None, right: int | None) -> int | None:
    values = [v for v in [left, right] if isinstance(v, int)]
    return max(values) if values else None


def score_candidate(item: Candidate, today: dt.date) -> Candidate:
    score = 0.0
    reasons: list[str] = []
    title_and_abs = f"{item.title} {item.abstract}".lower()

    for token, label in TOPICS.items():
        if token in title_and_abs and label not in reasons:
            score += 8
            reasons.append(label)

    if "arXiv" in item.source:
        score += 16
        reasons.append("新着 arXiv")

    age_days = days_since(item.published, today)
    if age_days is not None:
        if age_days <= 14:
            score += 22
            reasons.append(f"{age_days}日前の新着")
        elif age_days <= 90:
            score += 10
            reasons.append("直近3か月")

    if item.citation_count:
        citation_score = min(item.citation_count, 500) / 20
        score += citation_score
        if item.citation_count >= 100:
            reasons.append(f"引用数 {item.citation_count}")
    if item.influential_citation_count:
        score += min(item.influential_citation_count, 100) / 10
    if item.discussion_count:
        score += min(item.discussion_count, 100) / 5
        reasons.append(f"HN コメント {item.discussion_count}")
    if "Semantic Scholar" in item.source:
        score += 6

    item.score = round(score, 2)
    item.reasons = dedupe(reasons)[:5]
    return item


def days_since(date_text: str, today: dt.date) -> int | None:
    if not date_text:
        return None
    try:
        parsed = dt.date.fromisoformat(date_text[:10])
        return max((today - parsed).days, 0)
    except ValueError:
        return None


def dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def summarize_why(item: Candidate) -> str:
    if item.abstract:
        return textwrap.shorten(item.abstract, width=220, placeholder="...")
    return "タイトルと話題性から、今日の読書候補として拾っています。"


def to_record(item: Candidate) -> dict[str, Any]:
    paper_id = item.arxiv_id or slugify(item.title)
    return {
        "id": paper_id,
        "title": item.title,
        "url": item.url,
        "source": item.source,
        "published": item.published,
        "authors": item.authors,
        "venue": item.venue,
        "citationCount": item.citation_count,
        "influentialCitationCount": item.influential_citation_count,
        "discussionCount": item.discussion_count,
        "score": item.score,
        "reasons": item.reasons,
        "summary": summarize_why(item),
        "requestUrl": build_issue_url(item, paper_id),
    }


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value[:80] or "paper"


def build_issue_url(item: Candidate, paper_id: str) -> str:
    title = f"Generate translation and slides for {paper_id}"
    body = "\n".join(
        [
            "## Paper generation request",
            "",
            f"- Paper ID: {paper_id}",
            f"- Title: {item.title}",
            f"- URL: {item.url}",
            f"- Source: {item.source}",
            "",
            "## Outputs",
            "",
            "- [x] Japanese translation HTML/Markdown",
            "- [x] Ochiai-format summary slides",
            "",
            "## Notes",
            "",
            "Created from the Paper Read recommendation page.",
        ]
    )
    params = urllib.parse.urlencode(
        {
            "title": title,
            "body": body,
            "labels": "paper-generate",
        }
    )
    return f"https://github.com/rabbit-313/paper-read/issues/new?{params}"


def write_outputs(items: list[Candidate], output_dir: Path, date: dt.date) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    records = [to_record(item) for item in items]
    payload = {
        "date": date.isoformat(),
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "focus": "Recommender systems, recommendation, retrieval, ranking, and related ML/DL papers",
        "items": records,
    }
    (output_dir / "latest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    daily_path = output_dir / f"{date.isoformat()}.md"
    daily_path.write_text(render_markdown(payload), encoding="utf-8")


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Daily Paper Recommendations - {payload['date']}",
        "",
        "Focus: recommender systems, recommendation, retrieval, ranking, and related ML/DL papers.",
        "",
    ]
    for index, item in enumerate(payload["items"], start=1):
        meta = " / ".join(
            part
            for part in [
                item.get("source"),
                item.get("published"),
                item.get("venue"),
                f"citations: {item['citationCount']}" if item.get("citationCount") is not None else "",
            ]
            if part
        )
        lines.extend(
            [
                f"## {index}. {item['title']}",
                "",
                f"- URL: {item['url']}",
                f"- Meta: {meta}",
                f"- Score: {item['score']}",
                f"- Reasons: {', '.join(item['reasons']) or 'topic match'}",
                f"- Why read: {item['summary']}",
                "",
            ]
        )
    return "\n".join(lines)


def collect(args: argparse.Namespace) -> list[Candidate]:
    all_candidates: list[Candidate] = []
    fetchers = [
        ("arXiv", lambda q: fetch_arxiv(q, args.per_source_limit)),
        ("Semantic Scholar", lambda q: fetch_semantic_scholar(q, args.per_source_limit)),
        ("Hacker News", lambda q: fetch_hacker_news(q, args.days, args.per_source_limit)),
    ]
    for query in args.query:
        for name, fetcher in fetchers:
            try:
                all_candidates.extend(fetcher(query))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ET.ParseError) as exc:
                print(f"warning: failed to fetch {name} for {query!r}: {exc}", file=sys.stderr)
            time.sleep(args.sleep)
    today = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    merged = merge_candidates(all_candidates)
    scored = [score_candidate(item, today) for item in merged]
    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[: args.limit]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("recommendations"))
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--per-source-limit", type=int, default=10)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--sleep", type=float, default=0.5)
    parser.add_argument("--date", default="", help="Override output date, e.g. 2026-05-24")
    parser.add_argument("--query", action="append", default=DEFAULT_QUERIES)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    today = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    items = collect(args)
    if not items:
        print("No recommendation candidates found.", file=sys.stderr)
        return 1
    write_outputs(items, args.output_dir, today)
    print(f"Wrote {len(items)} recommendations to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
