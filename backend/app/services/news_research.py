from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
import hashlib
from html import unescape
import itertools
import json
import logging
import os
import re
from typing import Iterable
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import requests

from app.schemas.graph import GraphEdge, GraphNode, GraphResponse, GraphSummary


GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
logger = logging.getLogger("company_news_graph")


@dataclass
class NewsArticle:
    title: str
    url: str
    source_name: str
    published_at: datetime
    snippet: str


@dataclass
class ExtractedEvent:
    event_type: str
    event_label: str
    summary: str
    article_snippet: str
    published_at: datetime
    published_date: str
    source_name: str
    source_url: str
    source_title: str
    company_name: str


@dataclass
class EventCluster:
    event_type: str
    event_label: str
    items: list[ExtractedEvent]


@dataclass
class ClusterSummary:
    title: str
    summary: str
    key_points: list[str]
    confidence: str
    generated_by: str
    ai_reason: str
    raw_llm_output: str


def run_news_research(company_name: str, start_date: date, end_date: date) -> GraphResponse:
    try:
        articles = fetch_google_news_articles(company_name, start_date, end_date)
        events = [extract_event(company_name, article) for article in articles]
        return build_news_graph(company_name, events)
    except Exception as exc:
        return build_error_graph(company_name, str(exc))


def fetch_google_news_articles(
    company_name: str,
    start_date: date,
    end_date: date,
    limit: int = 8,
) -> list[NewsArticle]:
    query = build_google_news_query(company_name, start_date, end_date)
    url = f"{GOOGLE_NEWS_RSS_URL}?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; CompanyNewsGraph/0.1; +https://github.com/Nanki-nn/company-news-graph)"
        },
    )

    with urlopen(request, timeout=20) as response:
        payload = response.read()

    return parse_google_news_rss(payload, start_date, end_date)[:limit]


def build_google_news_query(company_name: str, start_date: date, end_date: date) -> str:
    return f'"{company_name}" after:{start_date.isoformat()} before:{end_date.isoformat()}'


def parse_google_news_rss(payload: bytes, start_date: date, end_date: date) -> list[NewsArticle]:
    root = ET.fromstring(payload)
    channel = root.find("channel")
    if channel is None:
        return []

    articles: list[NewsArticle] = []
    for item in channel.findall("item"):
        title = item.findtext("title", default="Untitled").strip()
        link = item.findtext("link", default="").strip()
        pub_date = item.findtext("pubDate", default="").strip()
        description = item.findtext("description", default="").strip()

        published_at = parse_rss_datetime(pub_date)
        if published_at is None:
          continue

        published_date = published_at.date()
        if published_date < start_date or published_date > end_date:
            continue

        clean_title, source_name = split_title_and_source(title)
        snippet = strip_html(description)
        articles.append(
            NewsArticle(
                title=clean_title,
                url=link,
                source_name=source_name,
                published_at=published_at,
                snippet=snippet,
            )
        )
    return deduplicate_articles(articles)


def parse_rss_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def split_title_and_source(title: str) -> tuple[str, str]:
    if " - " not in title:
        return title, "Google News"
    parts = title.rsplit(" - ", maxsplit=1)
    if len(parts) != 2:
        return title, "Google News"
    headline, source_name = parts
    return headline.strip(), source_name.strip()


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", unescape(value))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def deduplicate_articles(articles: Iterable[NewsArticle]) -> list[NewsArticle]:
    deduped: list[NewsArticle] = []
    seen: set[str] = set()
    for article in articles:
        digest = hashlib.sha1(f"{article.title}|{article.url}".encode("utf-8")).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        deduped.append(article)
    return deduped


EVENT_RULES: list[tuple[str, tuple[str, ...], str]] = [
    ("partnership", ("partner", "partnership", "collaboration", "deal with", "agreement"), "Partnership"),
    ("product_launch", ("launch", "introduce", "release", "unveil", "announce"), "Product Launch"),
    ("earnings", ("earnings", "revenue", "quarter", "results", "guidance"), "Earnings"),
    ("acquisition", ("acquire", "acquisition", "buy", "merge", "merger"), "Acquisition"),
    ("leadership_change", ("ceo", "cfo", "chairman", "appoint", "steps down", "resign"), "Leadership Change"),
    ("regulation", ("lawsuit", "probe", "investigation", "regulator", "fine", "ban"), "Regulation"),
]


def extract_event(company_name: str, article: NewsArticle) -> ExtractedEvent:
    haystack = f"{article.title} {article.snippet}".lower()
    event_type = "news"
    label = "General Update"
    for candidate_type, keywords, candidate_label in EVENT_RULES:
        if any(keyword in haystack for keyword in keywords):
            event_type = candidate_type
            label = candidate_label
            break

    summary = article.snippet or article.title
    if company_name.lower() not in summary.lower():
        summary = f"{company_name}: {summary}"

    return ExtractedEvent(
        event_type=event_type,
        event_label=label,
        summary=summary[:280],
        article_snippet=article.snippet[:400],
        published_at=article.published_at,
        published_date=article.published_at.date().isoformat(),
        source_name=article.source_name,
        source_url=article.url,
        source_title=article.title if article.title else label,
        company_name=company_name,
    )


def build_news_graph(company_name: str, events: list[ExtractedEvent]) -> GraphResponse:
    company_id = "company:target"
    nodes: list[GraphNode] = [
        GraphNode(
            id=company_id,
            label=company_name,
            type="Company",
            data={"canonical_name": company_name},
        )
    ]
    edges: list[GraphEdge] = []
    clusters = cluster_events(events)
    top_event_types: list[str] = []
    source_index = 0

    for event_index, cluster in enumerate(clusters, start=1):
        event_type = cluster.event_type
        group = cluster.items
        representative = group[0]
        event_id = f"event:{event_index}"
        article_titles = [item.source_title for item in group]
        cluster_summary = summarize_cluster(company_name, cluster)
        articles = [
            {
                "title": item.source_title,
                "summary": item.summary,
                "snippet": item.article_snippet,
                "source_name": item.source_name,
                "source_url": item.source_url,
                "published_at": item.published_at.isoformat(),
                "published_date": item.published_date,
            }
            for item in group
        ]
        nodes.append(
            GraphNode(
                id=event_id,
                label=cluster_summary.title,
                type="Event",
                data={
                    "event_type": representative.event_type,
                    "event_label": cluster.event_label,
                    "date": representative.published_date,
                    "published_at": representative.published_at.isoformat(),
                    "summary": cluster_summary.summary,
                    "title": cluster_summary.title,
                    "article_title": representative.source_title,
                    "article_snippet": representative.article_snippet,
                    "source_name": representative.source_name,
                    "source_url": representative.source_url,
                    "company_name": representative.company_name,
                    "article_count": len(group),
                    "article_titles": article_titles,
                    "articles": articles,
                    "key_points": cluster_summary.key_points,
                    "confidence": cluster_summary.confidence,
                    "generated_by": cluster_summary.generated_by,
                    "ai_reason": cluster_summary.ai_reason,
                    "raw_llm_output": cluster_summary.raw_llm_output,
                },
            )
        )
        edges.append(
            GraphEdge(
                id=f"edge:{event_index}:company",
                source=company_id,
                target=event_id,
                label="INVOLVED_IN",
                type="INVOLVED_IN",
            )
        )
        top_event_types.append(event_type)

        for item in group:
            source_index += 1
            source_id = f"source:{source_index}"
            nodes.append(
                GraphNode(
                    id=source_id,
                    label=item.source_name or "Google News",
                    type="Source",
                    data={
                        "url": item.source_url,
                        "published_at": item.published_at.isoformat(),
                        "published_date": item.published_date,
                        "title": item.source_title,
                        "article_title": item.source_title,
                        "article_snippet": item.article_snippet,
                        "summary": item.summary,
                        "source_name": item.source_name,
                        "company_name": item.company_name,
                    },
                )
            )
            edges.append(
                GraphEdge(
                    id=f"edge:{event_index}:source:{source_index}",
                    source=event_id,
                    target=source_id,
                    label="REPORTED_BY",
                    type="REPORTED_BY",
                )
            )

    if not events:
        empty_event_id = "event:none"
        nodes.append(
            GraphNode(
                id=empty_event_id,
                label="General Update",
                type="Event",
                data={
                    "event_type": "news",
                    "event_label": "General Update",
                    "date": "",
                    "summary": f"No recent Google News RSS results found for {company_name} in the selected time range.",
                    "company_name": company_name,
                },
            )
        )
        edges.append(
            GraphEdge(
                id="edge:none",
                source=company_id,
                target=empty_event_id,
                label="INVOLVED_IN",
                type="INVOLVED_IN",
            )
        )
        top_event_types = ["news"]

    return GraphResponse(
        nodes=nodes,
        edges=edges,
        summary=GraphSummary(
            event_count=len(top_event_types),
            source_count=len(events),
            top_event_types=sorted(set(top_event_types)),
        ),
    )


def cluster_events(events: list[ExtractedEvent]) -> list[EventCluster]:
    if not events:
        return []

    clusters: list[EventCluster] = []
    events_by_type = itertools.groupby(
        sorted(events, key=lambda item: (item.event_type, item.published_at), reverse=True),
        key=lambda item: item.event_type,
    )

    for event_type, items_iter in events_by_type:
        items = list(items_iter)
        type_clusters: list[EventCluster] = []
        for item in items:
            matched_cluster = next(
                (cluster for cluster in type_clusters if belongs_to_cluster(item, cluster)),
                None,
            )
            if matched_cluster is None:
                type_clusters.append(
                    EventCluster(
                        event_type=event_type,
                        event_label=item.event_label,
                        items=[item],
                    )
                )
            else:
                matched_cluster.items.append(item)
        clusters.extend(type_clusters)

    return sorted(
        clusters,
        key=lambda cluster: cluster.items[0].published_at,
        reverse=True,
    )


def belongs_to_cluster(item: ExtractedEvent, cluster: EventCluster) -> bool:
    item_tokens = significant_tokens(item.source_title)
    for existing in cluster.items:
        existing_tokens = significant_tokens(existing.source_title)
        if token_overlap_score(item_tokens, existing_tokens) >= 0.35:
            return True
        if len(item_tokens & existing_tokens) >= 2:
            return True
    return False


def significant_tokens(text: str) -> set[str]:
    stop_words = {
        "the", "and", "for", "with", "from", "into", "that", "this", "will", "says",
        "after", "before", "over", "under", "amid", "about", "company", "shares",
        "stock", "news", "report", "reports", "update", "latest"
    }
    tokens = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return {token for token in tokens if token not in stop_words}


def token_overlap_score(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    overlap = left & right
    union = left | right
    return len(overlap) / len(union)


def build_cluster_title(company_name: str, cluster: EventCluster) -> str:
    representative = cluster.items[0]
    title = re.sub(re.escape(company_name), "", representative.source_title, flags=re.IGNORECASE).strip(" -:")
    if title:
        return title[:120]
    return f"{event_type_to_label(cluster.event_type)} update"


def build_cluster_summary(company_name: str, cluster: EventCluster) -> str:
    representative = cluster.items[0]
    source_names = sorted({item.source_name for item in cluster.items if item.source_name})
    article_count = len(cluster.items)
    if article_count == 1:
        return representative.summary

    title_samples = [item.source_title for item in cluster.items[:3]]
    summary = (
        f"{company_name} had {article_count} related reports around "
        f"{event_type_to_label(cluster.event_type).lower()}. "
        f"Representative headlines: {'; '.join(title_samples)}."
    )
    if source_names:
        summary += f" Sources include {', '.join(source_names[:3])}."
    return summary[:420]


def summarize_cluster(company_name: str, cluster: EventCluster) -> ClusterSummary:
    ai_summary, ai_reason = summarize_cluster_with_ai(company_name, cluster)
    if ai_summary is not None:
        return ai_summary

    return ClusterSummary(
        title=build_cluster_title(company_name, cluster),
        summary=build_cluster_summary(company_name, cluster),
        key_points=build_cluster_key_points(cluster),
        confidence="heuristic",
        generated_by="rules",
        ai_reason=ai_reason,
        raw_llm_output="",
    )


def build_cluster_key_points(cluster: EventCluster) -> list[str]:
    points: list[str] = []
    unique_sources = sorted({item.source_name for item in cluster.items if item.source_name})
    if cluster.items:
        points.append(f"{len(cluster.items)} related articles in this cluster.")
        points.append(f"Most recent article date: {cluster.items[0].published_date}.")
    if unique_sources:
        points.append(f"Covered by {', '.join(unique_sources[:3])}.")
    headline = cluster.items[0].source_title if cluster.items else ""
    if headline:
        points.append(f"Representative headline: {headline}.")
    return points[:4]


def summarize_cluster_with_ai(
    company_name: str,
    cluster: EventCluster,
) -> tuple[ClusterSummary | None, str]:
    if os.getenv("COMPANY_NEWS_USE_AI", "0") not in {"1", "true", "TRUE", "yes", "YES"}:
        return None, "COMPANY_NEWS_USE_AI is disabled"

    provider = os.getenv("LLM_PROVIDER", "openai-compatible").strip().lower()
    if provider in {"openai-compatible", "openai"}:
        return summarize_cluster_with_openai_compatible(company_name, cluster)
    if provider in {"anthropic", "claude"}:
        return summarize_cluster_with_anthropic(company_name, cluster)
    return None, f"Unsupported LLM_PROVIDER: {provider}"


def summarize_cluster_with_openai_compatible(
    company_name: str,
    cluster: EventCluster,
) -> tuple[ClusterSummary | None, str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None, "OPENAI_API_KEY is missing"
    base_url = os.getenv("OPENAI_BASE_URL")
    if not base_url:
        return None, "OPENAI_BASE_URL is missing"
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    messages_payload = build_llm_messages(company_name, cluster)
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "temperature": 0.1,
        "messages": messages_payload,
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=60)
    except requests.RequestException as exc:
        return None, f"LLM request failed: {exc}"

    if not response.ok:
        try:
            error_body = response.json()
        except ValueError:
            error_body = response.text
        return None, f"LLM invoke failed: Error code: {response.status_code} - {error_body}"

    try:
        body = response.json()
    except ValueError:
        return None, "LLM response was not valid JSON"

    content = extract_openai_compatible_content(body)
    if not content:
        return None, "LLM response missing choices[0].message.content"

    return parse_cluster_summary_response(content, os.getenv("LLM_PROVIDER", "openai-compatible"), cluster)


def summarize_cluster_with_anthropic(
    company_name: str,
    cluster: EventCluster,
) -> tuple[ClusterSummary | None, str]:
    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN") or os.getenv("ANTHROPIC_API_KEY")
    if not auth_token:
        return None, "ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY is missing"

    base_url = os.getenv("ANTHROPIC_BASE_URL")
    if not base_url:
        return None, "ANTHROPIC_BASE_URL is missing"

    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    session_id = os.getenv("ANTHROPIC_SESSION_ID", "company-news-graph")
    endpoint = f"{base_url.rstrip('/')}/messages"
    article_lines = build_article_lines(cluster)

    payload = {
        "model": model,
        "max_tokens": 600,
        "temperature": 0.1,
        "system": (
            "You summarize clustered company news into one concise business event. "
            "Return strict JSON with keys: title, summary, key_points, confidence. "
            "title: <= 12 words. summary: <= 90 words. key_points: array of 2 to 4 short bullets. "
            "confidence: one of high, medium, low. Do not include markdown."
        ),
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Company: {company_name}\n"
                    f"Event type: {cluster.event_type}\n"
                    f"Cluster size: {len(cluster.items)}\n"
                    f"Articles:\n{'\n'.join(article_lines)}"
                ),
            }
        ],
        "metadata": {
            "session_id": session_id,
        },
    }
    headers = {
        "Content-Type": "application/json",
        "anthropic-version": os.getenv("ANTHROPIC_VERSION", "2023-06-01"),
        "x-api-key": auth_token,
        "Authorization": f"Bearer {auth_token}",
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=60)
    except requests.RequestException as exc:
        return None, f"LLM request failed: {exc}"

    if not response.ok:
        try:
            error_body = response.json()
        except ValueError:
            error_body = response.text
        return None, f"LLM invoke failed: Error code: {response.status_code} - {error_body}"

    try:
        body = response.json()
    except ValueError:
        logger.warning("[llm-raw-preview] %s", response.text[:1000])
        return None, "Anthropic response was not valid JSON"

    content = extract_anthropic_content(body)
    if not content:
        logger.warning("[llm-raw-preview] %s", response.text[:1000])
        return None, "Anthropic response missing content text"

    return parse_cluster_summary_response(content, os.getenv("LLM_PROVIDER", "anthropic"), cluster)


def build_article_lines(cluster: EventCluster) -> list[str]:
    article_lines = []
    for index, item in enumerate(cluster.items[:6], start=1):
        article_lines.append(
            f"{index}. {item.published_date} | {item.source_name} | {item.source_title} | {item.summary}"
        )
    return article_lines


def build_llm_messages(company_name: str, cluster: EventCluster) -> list[dict[str, str]]:
    article_lines = build_article_lines(cluster)
    return [
        {
            "role": "system",
            "content": (
                "You summarize clustered company news into one concise business event. "
                "Return strict JSON with keys: title, summary, key_points, confidence. "
                "title: <= 12 words. summary: <= 90 words. key_points: array of 2 to 4 short bullets. "
                "confidence: one of high, medium, low. Do not include markdown."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Company: {company_name}\n"
                f"Event type: {cluster.event_type}\n"
                f"Cluster size: {len(cluster.items)}\n"
                f"Articles:\n{'\n'.join(article_lines)}"
            ),
        },
    ]


def extract_openai_compatible_content(body: dict[str, object]) -> str | None:
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return None
    message = first_choice.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                text_parts.append(item["text"])
        return "\n".join(text_parts).strip() or None
    return None


def extract_anthropic_content(body: dict[str, object]) -> str | None:
    content = body.get("content")
    if not isinstance(content, list):
        return None
    text_parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
            text_parts.append(item["text"])
    return "\n".join(text_parts).strip() or None


def parse_cluster_summary_response(
    content: str,
    provider_name: str,
    cluster: EventCluster,
) -> tuple[ClusterSummary | None, str]:
    parsed = parse_llm_json(content)
    if parsed is None:
        logger.warning("[llm-raw-preview] %s", content[:1000])
        fallback = parse_llm_fallback_text(content, cluster)
        if fallback is None:
            return None, "LLM response was not valid JSON"
        fallback.generated_by = provider_name
        fallback.ai_reason = "AI summary generated via fallback parser"
        fallback.raw_llm_output = content[:8000]
        return fallback, "AI summary generated via fallback parser"

    normalized = normalize_parsed_cluster_summary(parsed, cluster)
    if normalized is None:
        logger.warning("[llm-raw-preview] %s", content[:1000])
        fallback = parse_llm_fallback_text(content, cluster)
        if fallback is None:
            return None, "LLM response missing title or summary"
        fallback.generated_by = provider_name
        fallback.ai_reason = "AI summary generated via fallback parser"
        fallback.raw_llm_output = content[:8000]
        return fallback, "AI summary generated via fallback parser"

    normalized.generated_by = provider_name
    normalized.raw_llm_output = content[:8000]
    return (
        normalized,
        "AI summary generated successfully",
    )


def normalize_parsed_cluster_summary(
    parsed: dict[str, object],
    cluster: EventCluster,
) -> ClusterSummary | None:
    title = str(parsed.get("title") or "").strip()
    summary = str(parsed.get("summary") or "").strip()
    key_points_raw = parsed.get("key_points") or []
    confidence = str(parsed.get("confidence") or "medium").strip().lower()
    if not title or not summary:
        return None

    key_points = [str(item).strip() for item in key_points_raw if str(item).strip()]
    if not key_points:
        key_points = build_cluster_key_points(cluster)

    return ClusterSummary(
        title=title[:120],
        summary=summary[:600],
        key_points=key_points[:4],
        confidence=confidence if confidence in {"high", "medium", "low"} else "medium",
        generated_by="ai",
        ai_reason="AI summary generated successfully",
        raw_llm_output="",
    )


def parse_llm_fallback_text(
    content: str,
    cluster: EventCluster,
) -> ClusterSummary | None:
    cleaned = clean_llm_text(content)
    if not cleaned:
        return None

    lines = [line.strip("-* \t") for line in cleaned.splitlines() if line.strip()]
    title = ""
    summary = ""
    key_points: list[str] = []
    confidence = "medium"

    for line in lines:
        lower = line.lower()
        if not title and any(lower.startswith(prefix) for prefix in ("title:", "headline:", "event:")):
            title = line.split(":", 1)[1].strip() if ":" in line else line
            continue
        if not summary and any(lower.startswith(prefix) for prefix in ("summary:", "overview:", "description:")):
            summary = line.split(":", 1)[1].strip() if ":" in line else line
            continue
        if lower.startswith("confidence:"):
            confidence = line.split(":", 1)[1].strip().lower()
            continue
        if line.startswith(("-", "*")) or re.match(r"^\d+\.", line):
            key_points.append(re.sub(r"^(\d+\.|[-*])\s*", "", line).strip())

    if not title and lines:
        title = lines[0][:120]

    if not summary:
        prose_lines = [
            line for line in lines[1:] if not any(
                line.lower().startswith(prefix)
                for prefix in ("title:", "headline:", "event:", "confidence:")
            )
        ]
        summary = " ".join(prose_lines[:3]).strip()

    if not summary:
        summary = build_cluster_summary(cluster.items[0].company_name, cluster)

    if not key_points:
        key_points = extract_key_points_from_text(lines)
    if not key_points:
        key_points = build_cluster_key_points(cluster)

    if not title:
        title = build_cluster_title(cluster.items[0].company_name, cluster)

    return ClusterSummary(
        title=title[:120],
        summary=summary[:600],
        key_points=key_points[:4],
        confidence=confidence if confidence in {"high", "medium", "low"} else "medium",
        generated_by="ai",
        ai_reason="AI summary generated via fallback parser",
        raw_llm_output=content[:8000],
    )


def clean_llm_text(text: str) -> str:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json|text)?\s*", "", candidate)
        candidate = re.sub(r"\s*```$", "", candidate)
    return candidate.strip()


def extract_key_points_from_text(lines: list[str]) -> list[str]:
    candidates = []
    for line in lines:
        normalized = line.strip()
        if not normalized:
            continue
        lower = normalized.lower()
        if any(lower.startswith(prefix) for prefix in ("summary:", "overview:", "description:", "confidence:")):
            continue
        if normalized.startswith(("-", "*")) or re.match(r"^\d+\.", normalized):
            candidates.append(re.sub(r"^(\d+\.|[-*])\s*", "", normalized).strip())
    return [item for item in candidates if item][:4]


def parse_llm_json(text: str) -> dict[str, object] | None:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
        candidate = re.sub(r"\s*```$", "", candidate)
    try:
        loaded = json.loads(candidate)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", candidate, re.DOTALL)
        if not match:
            return None
        try:
            loaded = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return loaded if isinstance(loaded, dict) else None


def build_error_graph(company_name: str, error_message: str) -> GraphResponse:
    company_id = "company:target"
    event_id = "event:error"
    source_id = "source:error"
    return GraphResponse(
        nodes=[
            GraphNode(
                id=company_id,
                label=company_name,
                type="Company",
                data={"canonical_name": company_name},
            ),
            GraphNode(
                id=event_id,
                label="General Update",
                type="Event",
                data={
                    "event_type": "news",
                    "event_label": "General Update",
                    "date": "",
                    "summary": f"News fetch failed. {error_message}",
                    "source_name": "Google News RSS",
                    "source_url": GOOGLE_NEWS_RSS_URL,
                    "company_name": company_name,
                },
            ),
            GraphNode(
                id=source_id,
                label="Google News RSS",
                type="Source",
                data={
                    "url": GOOGLE_NEWS_RSS_URL,
                    "source_name": "Google News RSS",
                    "company_name": company_name,
                },
            ),
        ],
        edges=[
            GraphEdge(
                id="edge:error:company",
                source=company_id,
                target=event_id,
                label="INVOLVED_IN",
                type="INVOLVED_IN",
            ),
            GraphEdge(
                id="edge:error:source",
                source=event_id,
                target=source_id,
                label="REPORTED_BY",
                type="REPORTED_BY",
            ),
        ],
        summary=GraphSummary(
            event_count=0,
            source_count=0,
            top_event_types=["news"],
        ),
    )


def event_type_to_label(event_type: str) -> str:
    mapping = {
        "partnership": "Partnership",
        "product_launch": "Product Launch",
        "earnings": "Earnings",
        "acquisition": "Acquisition",
        "leadership_change": "Leadership Change",
        "regulation": "Regulation",
        "news": "General Update",
    }
    return mapping.get(event_type, "General Update")
