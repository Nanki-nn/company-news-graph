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
import shutil
import subprocess
from typing import Iterable
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import requests

from app.schemas.graph import GraphEdge, GraphNode, GraphResponse, GraphSummary


GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions"
logger = logging.getLogger("company_news_graph")

_SEC_TICKERS_CACHE: dict[str, object] | None = None


def fetch_sec_tickers() -> dict[str, object]:
    global _SEC_TICKERS_CACHE
    if _SEC_TICKERS_CACHE is None:
        _SEC_TICKERS_CACHE = fetch_json(SEC_TICKERS_URL, headers=build_sec_headers())
    return _SEC_TICKERS_CACHE


COMPANY_ALIASES: dict[str, list[str]] = {
    "google": ["Alphabet", "Google", "GOOGL", "GOOG"],
    "alphabet": ["Alphabet", "Google", "GOOGL", "GOOG"],
    "googl": ["Alphabet", "Google", "GOOGL", "GOOG"],
    "goog": ["Alphabet", "Google", "GOOGL", "GOOG"],
    "facebook": ["Meta", "Meta Platforms", "Facebook", "META"],
    "meta": ["Meta", "Meta Platforms", "Facebook", "META"],
    "meta platforms": ["Meta", "Meta Platforms", "Facebook", "META"],
    "meta platforms inc": ["Meta", "Meta Platforms", "Facebook", "META"],
    "meta platforms inc class a": ["Meta", "Meta Platforms", "Facebook", "META"],
    "oracle": ["Oracle", "ORCL"],
    "orcl": ["Oracle", "ORCL"],
    "tesla": ["Tesla", "TSLA"],
    "tsla": ["Tesla", "TSLA"],
    "amazon": ["Amazon", "AMZN"],
    "amzn": ["Amazon", "AMZN"],
    "apple": ["Apple", "AAPL"],
    "aapl": ["Apple", "AAPL"],
    "microsoft": ["Microsoft", "MSFT"],
    "msft": ["Microsoft", "MSFT"],
    "netflix": ["Netflix", "NFLX"],
    "nflx": ["Netflix", "NFLX"],
}


@dataclass
class NewsArticle:
    title: str
    url: str
    source_name: str
    published_at: datetime
    snippet: str
    source_category: str = "news"
    form_type: str | None = None
    detail_score: int = 0


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
    ticker: str


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
    event_type: str
    officialness: str
    impact_direction: str
    impact_level: str
    price_sensitive: bool
    generated_by: str
    ai_reason: str
    raw_llm_output: str


def run_news_research(company_name: str, ticker: str, start_date: date, end_date: date) -> GraphResponse:
    try:
        official_articles = fetch_sec_edgar_articles(company_name, ticker, start_date, end_date)
        sec_company = lookup_sec_company(company_name, ticker)
        sec_title = str(sec_company.get("title") or "").strip() if sec_company else ""
        news_articles = fetch_google_news_articles(company_name, ticker, start_date, end_date, sec_resolved_name=sec_title or None)
        articles = sort_articles_by_priority(official_articles + news_articles)
        filtered_articles = [
            article for article in articles if is_investment_relevant_article(article)
        ]
        filtered_articles = rebalance_sparse_official_articles(filtered_articles)
        if not filtered_articles:
            filtered_articles = articles[:10]
        events = [
            extract_event(company_name, ticker, article)
            for article in filtered_articles
        ]
        return build_news_graph(company_name, events)
    except Exception as exc:
        return build_error_graph(company_name, str(exc))


def sort_articles_by_priority(articles: list[NewsArticle]) -> list[NewsArticle]:
    return sorted(
        deduplicate_articles(articles),
        key=lambda article: (
            0 if article.source_category == "official" and article.detail_score >= 2 else 1,
            2 if article.source_category == "official" else 0,
            -article.detail_score,
            -article.published_at.timestamp(),
        ),
    )


def rebalance_sparse_official_articles(articles: list[NewsArticle]) -> list[NewsArticle]:
    return articles


def fetch_google_news_articles(
    company_name: str,
    ticker: str,
    start_date: date,
    end_date: date,
    limit: int = 15,
    sec_resolved_name: str | None = None,
) -> list[NewsArticle]:
    query = build_google_news_query(company_name, ticker, start_date, end_date, sec_resolved_name=sec_resolved_name)
    url = f"{GOOGLE_NEWS_RSS_URL}?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    logger.info("[datasource] Google News RSS query=%r url=%s", query, url)
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; CompanyNewsGraph/0.1; +https://github.com/Nanki-nn/company-news-graph)"
        },
    )

    with urlopen(request, timeout=20) as response:
        payload = response.read()

    articles = parse_google_news_rss(payload, start_date, end_date)[:limit]
    logger.info("[datasource] Google News RSS returned %d articles for %r", len(articles), company_name)
    for i, article in enumerate(articles, start=1):
        logger.debug("[datasource] article[%d] title=%r source=%r published=%s url=%s",
                     i, article.title, article.source_name, article.published_at.date().isoformat(), article.url)
    return articles


def strip_corporate_suffix(title: str) -> str:
    suffixes = {"INC", "CORP", "CORPORATION", "CO", "LTD", "LIMITED", "PLC", "HOLDINGS", "GROUP", "LLC", "LP", "NV", "SA"}
    words = title.split()
    while words and words[-1].rstrip(".").upper() in suffixes:
        words = words[:-1]
    return " ".join(words).strip()


def build_google_news_query(
    company_name: str,
    ticker: str,
    start_date: date,
    end_date: date,
    sec_resolved_name: str | None = None,
) -> str:
    aliases = get_company_aliases(company_name, ticker)
    if sec_resolved_name:
        clean_name = strip_corporate_suffix(sec_resolved_name).title()
        for candidate in (clean_name, sec_resolved_name):
            if not candidate:
                continue
            normalized = normalize_company_name(candidate)
            existing_normalized = {normalize_company_name(a) for a in aliases}
            if normalized and normalized not in existing_normalized:
                aliases.insert(1, candidate)
                break
    if len(aliases) == 1:
        query_company = f'"{aliases[0]}"'
    else:
        query_company = " OR ".join(f'"{alias}"' for alias in aliases[:4])
        query_company = f"({query_company})"
    return f'{query_company} after:{start_date.isoformat()} before:{end_date.isoformat()}'


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
                source_category="news",
                detail_score=score_article_detail(clean_title, snippet),
            )
        )
    return deduplicate_articles(articles)


def fetch_sec_edgar_articles(
    company_name: str,
    ticker: str,
    start_date: date,
    end_date: date,
    limit: int = 12,
) -> list[NewsArticle]:
    company_record = lookup_sec_company(company_name, ticker)
    if company_record is None:
        logger.info("[datasource] SEC EDGAR: no company record found for %r / %r", company_name, ticker)
        return []

    cik = str(company_record["cik_str"]).zfill(10)
    sec_url = f"{SEC_SUBMISSIONS_URL}/CIK{cik}.json"
    logger.info("[datasource] SEC EDGAR company=%r ticker=%r cik=%s url=%s", company_name, ticker, cik, sec_url)
    payload = fetch_json(
        sec_url,
        headers=build_sec_headers(),
    )
    recent = payload.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])
    accession_numbers = recent.get("accessionNumber", [])
    primary_documents = recent.get("primaryDocument", [])
    descriptions = recent.get("primaryDocDescription", [])

    articles: list[NewsArticle] = []
    for index, form in enumerate(forms):
        if index >= len(filing_dates) or index >= len(accession_numbers) or index >= len(primary_documents):
            continue
        form_name = str(form or "").strip()
        if not is_investment_relevant_form(form_name):
            continue

        published_at = parse_iso_datetime(str(filing_dates[index] or ""))
        if published_at is None:
            continue
        if published_at.date() < start_date or published_at.date() > end_date:
            continue

        accession_number = str(accession_numbers[index] or "").strip()
        primary_document = str(primary_documents[index] or "").strip()
        description = str(descriptions[index] or "").strip() if index < len(descriptions) else ""
        filing_title = build_sec_article_title(form_name, description, str(company_record.get("title") or company_name))
        filing_snippet = build_sec_article_snippet(form_name, description, str(company_record.get("title") or company_name))
        articles.append(
            NewsArticle(
                title=filing_title,
                url=build_sec_filing_url(cik, accession_number, primary_document),
                source_name="SEC EDGAR",
                published_at=published_at,
                snippet=filing_snippet,
                source_category="official",
                form_type=form_name,
                detail_score=score_sec_article_detail(form_name, description),
            )
        )
        if len(articles) >= limit:
            break

    logger.info("[datasource] SEC EDGAR returned %d filings for %r", len(articles), company_name)
    for i, article in enumerate(articles, start=1):
        logger.debug("[datasource] filing[%d] form=%r title=%r published=%s url=%s",
                     i, article.form_type, article.title, article.published_at.date().isoformat(), article.url)
    return articles


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


def parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=UTC)
    except ValueError:
        return None


def lookup_sec_company(company_name: str, ticker: str) -> dict[str, object] | None:
    payload = fetch_sec_tickers()
    aliases = get_company_aliases(company_name, ticker)
    normalized_queries = {normalize_company_name(alias) for alias in aliases}
    ticker_queries = {alias.lower() for alias in aliases}
    candidates: list[dict[str, object]] = []

    iterable = payload.values() if isinstance(payload, dict) else []
    for item in iterable:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").strip().lower()
        title = str(item.get("title") or "").strip()
        normalized_title = normalize_company_name(title)
        if ticker in ticker_queries:
            return item
        if normalized_title in normalized_queries:
            return item
        if any(query and query in normalized_title for query in normalized_queries):
            candidates.append(item)

    return candidates[0] if candidates else None


def get_company_aliases(company_name: str, ticker: str) -> list[str]:
    normalized = normalize_company_name(company_name)
    aliases = COMPANY_ALIASES.get(normalized, []).copy()
    merged = [company_name]
    if ticker.strip():
        merged.append(ticker.strip().upper())
    merged.extend(aliases)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in merged:
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped or [company_name]


def normalize_company_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    suffixes = {
        "inc", "corp", "corporation", "company", "co", "limited", "ltd",
        "plc", "holdings", "group",
    }
    return " ".join(token for token in normalized.split() if token not in suffixes)


def fetch_json(url: str, headers: dict[str, str]) -> dict[str, object]:
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def build_sec_headers() -> dict[str, str]:
    return {
        "User-Agent": os.getenv(
            "SEC_USER_AGENT",
            "CompanyNewsGraph/0.1 research@company-news-graph.local",
        ),
        "Accept": "application/json",
    }


def build_sec_filing_url(cik: str, accession_number: str, primary_document: str) -> str:
    accession_compact = accession_number.replace("-", "")
    cik_compact = str(int(cik))
    return f"https://www.sec.gov/Archives/edgar/data/{cik_compact}/{accession_compact}/{primary_document.lstrip('/')}"


def build_sec_article_title(form_name: str, description: str, company_title: str) -> str:
    if is_informative_sec_description(form_name, description):
        return f"{form_name}: {description.rstrip('.')}"
    return f"{company_title} filed {form_name}"


def build_sec_article_snippet(form_name: str, description: str, company_title: str) -> str:
    if is_informative_sec_description(form_name, description):
        return description
    return f"{company_title} filed {form_name} with the SEC. Open the filing for full details."


def is_informative_sec_description(form_name: str, description: str) -> bool:
    cleaned = description.strip().strip(".").lower()
    if not cleaned:
        return False
    generic_values = {
        form_name.strip().lower(),
        "8-k",
        "10-q",
        "10-k",
        "6-k",
        "current report",
        "quarterly report",
        "annual report",
    }
    return cleaned not in generic_values and len(cleaned) >= 12


def is_investment_relevant_form(form_name: str) -> bool:
    return form_name.upper() in {
        "8-K", "10-K", "10-Q", "6-K", "20-F", "40-F", "DEF 14A",
        "SC 13D", "SC 13G", "S-1", "S-3", "424B3", "425",
    }


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


def score_article_detail(title: str, snippet: str) -> int:
    text = f"{title} {snippet}".strip()
    if not text:
        return 0
    generic_patterns = {
        "8-k", "10-q", "10-k", "current report", "quarterly report", "annual report",
    }
    normalized = text.lower()
    if any(pattern == normalized.strip() for pattern in generic_patterns):
        return 0
    score = 1
    if len(snippet.strip()) >= 40:
        score += 1
    if len(re.findall(r"[A-Za-z]{4,}", text)) >= 8:
        score += 1
    if any(keyword in normalized for keyword in (
        "earnings", "guidance", "merger", "acquisition", "layoff", "severance",
        "investigation", "lawsuit", "buyback", "dividend", "offering",
    )):
        score += 1
    return score


def score_sec_article_detail(form_name: str, description: str) -> int:
    if not is_informative_sec_description(form_name, description):
        return 1
    score = 2
    normalized = description.lower()
    if any(keyword in normalized for keyword in (
        "earnings", "guidance", "merger", "acquisition", "layoff", "severance",
        "investigation", "lawsuit", "buyback", "dividend", "offering",
    )):
        score += 1
    if len(re.findall(r"[A-Za-z]{4,}", description)) >= 8:
        score += 1
    return score


EVENT_RULES: list[tuple[str, tuple[str, ...], str]] = [
    ("guidance_update", ("raises guidance", "cuts guidance", "guidance update", "outlook", "forecast"), "Guidance Update"),
    ("earnings_result", ("eps", "revenue", "net income", "reported results", "quarterly results", "beat", "miss"), "Earnings Result"),
    ("earnings_schedule", ("conference call", "announce results on", "will release", "date for results", "earnings call"), "Earnings Schedule"),
    ("partnership", ("partner", "partnership", "collaboration", "deal with", "agreement"), "Partnership"),
    ("product_launch", ("launch", "introduce", "release", "unveil", "announce"), "Product Launch"),
    ("acquisition", ("acquire", "acquisition", "buy", "merge", "merger"), "Acquisition"),
    ("leadership_change", ("ceo", "cfo", "chairman", "appoint", "steps down", "resign"), "Leadership Change"),
    ("regulation", ("lawsuit", "probe", "investigation", "regulator", "fine", "ban"), "Regulation"),
    ("layoffs", ("layoff", "job cut", "workforce reduction", "severance", "redundancies"), "Layoffs"),
    ("capital_markets", ("buyback", "dividend", "offering", "share repurchase", "financing"), "Capital Markets"),
]


def extract_event(company_name: str, ticker: str, article: NewsArticle) -> ExtractedEvent:
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
        ticker=ticker.strip().upper(),
    )


def is_investment_relevant_article(article: NewsArticle) -> bool:
    if article.source_category == "official":
        return True

    haystack = f"{article.title} {article.snippet}".lower()
    noise_keywords = (
        "stock quote", "price and forecast", "price forecast", "stock forecast",
        "how to get paid to buy", "discount", "quote price",
    )
    if any(keyword in haystack for keyword in noise_keywords):
        return False
    return True


def derive_officialness(group: list[ExtractedEvent]) -> str:
    has_official = any(item.source_name == "SEC EDGAR" for item in group)
    has_media = any(item.source_name != "SEC EDGAR" for item in group)
    if has_official and has_media:
        return "mixed"
    if has_official:
        return "official"
    return "media"


def derive_impact_direction(event_type: str, group: list[ExtractedEvent]) -> str:
    negative_types = {"layoffs", "regulation", "guidance_update"}
    positive_types = {"partnership", "capital_markets"}
    neutral_types = {"earnings_schedule"}
    if event_type in negative_types:
        return "negative"
    if event_type in positive_types:
        return "positive"
    if event_type in neutral_types:
        return "neutral"
    haystack = " ".join(f"{item.source_title} {item.summary}" for item in group).lower()
    if any(keyword in haystack for keyword in ("misses", "cuts guidance", "probe", "lawsuit", "layoffs", "severance")):
        return "negative"
    if any(keyword in haystack for keyword in ("beats", "raises guidance", "buyback", "dividend", "partnership")):
        return "positive"
    return "neutral"


def derive_impact_level(event_type: str, group: list[ExtractedEvent]) -> str:
    high_types = {"earnings_result", "guidance_update", "acquisition", "layoffs", "regulation", "capital_markets"}
    low_types = {"earnings_schedule"}
    if event_type in high_types:
        return "high"
    if event_type in low_types:
        return "low"
    if len(group) >= 3:
        return "medium"
    return "low"


def build_news_graph(company_name: str, events: list[ExtractedEvent]) -> GraphResponse:
    company_ticker = next((event.ticker for event in events if event.ticker), "")
    company_id = "company:target"
    nodes: list[GraphNode] = [
        GraphNode(
            id=company_id,
            label=company_name,
            type="Company",
            data={"canonical_name": company_name, "ticker": company_ticker},
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
                "ticker": item.ticker,
            }
            for item in group
        ]
        nodes.append(
            GraphNode(
                id=event_id,
                label=cluster_summary.title,
                type="Event",
                data={
                    "event_type": cluster_summary.event_type or representative.event_type,
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
                    "ticker": representative.ticker,
                    "article_count": len(group),
                    "article_titles": article_titles,
                    "articles": articles,
                    "key_points": cluster_summary.key_points,
                    "confidence": cluster_summary.confidence,
                    "officialness": cluster_summary.officialness,
                    "impact_direction": cluster_summary.impact_direction,
                    "impact_level": cluster_summary.impact_level,
                    "price_sensitive": cluster_summary.price_sensitive,
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
                        "ticker": item.ticker,
                        "officialness": "official" if item.source_name == "SEC EDGAR" else "media",
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

    clusters = sorted(
        clusters,
        key=lambda cluster: cluster.items[0].published_at,
        reverse=True,
    )
    return prune_redundant_schedule_clusters(clusters)


def prune_redundant_schedule_clusters(clusters: list[EventCluster]) -> list[EventCluster]:
    if not clusters:
        return []

    result_clusters = [
        cluster for cluster in clusters
        if cluster.event_type in {"earnings_result", "guidance_update"}
    ]
    if not result_clusters:
        return clusters

    kept: list[EventCluster] = []
    for cluster in clusters:
        if cluster.event_type != "earnings_schedule":
            kept.append(cluster)
            continue

        schedule_date = cluster.items[0].published_at.date()
        should_drop = any(
            abs((result_cluster.items[0].published_at.date() - schedule_date).days) <= 21
            for result_cluster in result_clusters
        )
        if not should_drop:
            kept.append(cluster)

    return kept


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
        return f"{company_name}近期出现一条与{event_type_to_zh_label(cluster.event_type)}相关的动态：{representative.summary}"

    title_samples = [item.source_title for item in cluster.items[:3]]
    summary = (
        f"{company_name}近期出现{article_count}条与{event_type_to_zh_label(cluster.event_type)}相关的报道。"
        f"代表性标题包括：{'；'.join(title_samples)}。"
    )
    if source_names:
        summary += f" 主要来源包括：{'、'.join(source_names[:3])}。"
    return summary[:420]


def summarize_cluster(company_name: str, cluster: EventCluster) -> ClusterSummary:
    ai_summary, ai_reason = summarize_cluster_with_ai(company_name, cluster)
    if ai_summary is not None:
        return ai_summary

    officialness = derive_officialness(cluster.items)
    impact_direction = derive_impact_direction(cluster.event_type, cluster.items)
    impact_level = derive_impact_level(cluster.event_type, cluster.items)
    return ClusterSummary(
        title=build_cluster_title(company_name, cluster),
        summary=build_cluster_summary(company_name, cluster),
        key_points=build_cluster_key_points(cluster),
        confidence="heuristic",
        event_type=cluster.event_type,
        officialness=officialness,
        impact_direction=impact_direction,
        impact_level=impact_level,
        price_sensitive=impact_level in {"high", "medium"},
        generated_by="rules",
        ai_reason=ai_reason,
        raw_llm_output="",
    )


def build_cluster_key_points(cluster: EventCluster) -> list[str]:
    points: list[str] = []
    unique_sources = sorted({item.source_name for item in cluster.items if item.source_name})
    if cluster.items:
        points.append(f"该事件聚合了 {len(cluster.items)} 条相关新闻。")
        points.append(f"最新报道日期为 {cluster.items[0].published_date}。")
    if unique_sources:
        points.append(f"报道来源包括：{'、'.join(unique_sources[:3])}。")
    headline = cluster.items[0].source_title if cluster.items else ""
    if headline:
        points.append(f"代表性标题：{headline}。")
    return points[:4]


def summarize_cluster_with_ai(
    company_name: str,
    cluster: EventCluster,
) -> tuple[ClusterSummary | None, str]:
    if os.getenv("COMPANY_NEWS_USE_AI", "0") not in {"1", "true", "TRUE", "yes", "YES"}:
        return None, "COMPANY_NEWS_USE_AI is disabled"

    provider = os.getenv("LLM_PROVIDER", "openai-compatible").strip().lower()
    if provider in {"claude-cli", "claude-code"}:
        return summarize_cluster_with_claude_cli(company_name, cluster)
    if provider in {"openai-compatible", "openai"}:
        return summarize_cluster_with_openai_compatible(company_name, cluster)
    if provider in {"anthropic", "claude"}:
        return summarize_cluster_with_anthropic(company_name, cluster)
    return None, f"Unsupported LLM_PROVIDER: {provider}"


def summarize_cluster_with_claude_cli(
    company_name: str,
    cluster: EventCluster,
) -> tuple[ClusterSummary | None, str]:
    cli_command = os.getenv("CLAUDE_CLI_COMMAND", "claude").strip() or "claude"
    if shutil.which(cli_command) is None:
        return None, f"{cli_command} command not found"

    prompt = build_claude_cli_prompt(company_name, cluster)
    logger.info("[ai-input] claude-cli company=%r event_type=%r cluster_size=%d",
                company_name, cluster.event_type, len(cluster.items))
    logger.debug("[ai-input] claude-cli prompt:\n%s", prompt)
    try:
        completed = subprocess.run(
            [cli_command, "-p", prompt],
            check=False,
            capture_output=True,
            text=True,
            timeout=int(os.getenv("CLAUDE_CLI_TIMEOUT_SECONDS", "120")),
        )
    except subprocess.TimeoutExpired:
        return None, "Claude CLI request timed out"
    except Exception as exc:
        return None, f"Claude CLI request failed: {exc}"

    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "").strip()
        return None, f"Claude CLI invoke failed: {stderr[:500] or f'exit code {completed.returncode}'}"

    content = (completed.stdout or "").strip()
    if not content:
        return None, "Claude CLI returned empty content"

    logger.info("[ai-output] claude-cli company=%r event_type=%r response_len=%d",
                company_name, cluster.event_type, len(content))
    logger.debug("[ai-output] claude-cli raw response:\n%s", content)
    return parse_cluster_summary_response(content, "claude-cli", cluster)


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

    logger.info("[ai-input] openai-compatible model=%r endpoint=%s company=%r event_type=%r cluster_size=%d",
                model, endpoint, company_name, cluster.event_type, len(cluster.items))
    logger.debug("[ai-input] openai-compatible messages:\n%s", json.dumps(messages_payload, ensure_ascii=False, indent=2))

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

    logger.info("[ai-output] openai-compatible model=%r company=%r event_type=%r response_len=%d",
                model, company_name, cluster.event_type, len(content))
    logger.debug("[ai-output] openai-compatible raw response:\n%s", content)
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
            "You are an investment research analyst. "
            "Return strict JSON with keys: "
            "title, summary, key_points, event_type, officialness, impact_direction, impact_level, price_sensitive, confidence. "
            "title: <= 12 words. summary: <= 90 words. key_points: array of 2 to 4 short bullets. "
            "event_type: one of earnings_schedule, earnings_result, guidance_update, acquisition, partnership, layoffs, regulation, capital_markets, leadership_change, product_launch, news. "
            "officialness: one of official, media, mixed. "
            "impact_direction: one of positive, negative, neutral. "
            "impact_level: one of high, medium, low. "
            "price_sensitive: boolean. "
            "confidence: one of high, medium, low. "
            "Do not include markdown."
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

    user_message = payload["messages"][0]["content"] if payload.get("messages") else ""
    logger.info("[ai-input] anthropic model=%r endpoint=%s company=%r event_type=%r cluster_size=%d",
                model, endpoint, company_name, cluster.event_type, len(cluster.items))
    logger.debug("[ai-input] anthropic system:\n%s", payload.get("system", ""))
    logger.debug("[ai-input] anthropic user message:\n%s", user_message)

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

    logger.info("[ai-output] anthropic model=%r company=%r event_type=%r response_len=%d",
                model, company_name, cluster.event_type, len(content))
    logger.debug("[ai-output] anthropic raw response:\n%s", content)
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
                "你是一名公司研究分析师。请把一组相关新闻总结为一个中文关键事件。"
                "必须返回严格 JSON，字段为 title, summary, key_points, confidence。"
                "同时返回 event_type, officialness, impact_direction, impact_level, price_sensitive。"
                "title：中文标题，不超过18个汉字。"
                "summary：中文摘要，80到140字。"
                "key_points：2到4条中文要点。"
                "event_type：只能是 earnings_schedule、earnings_result、guidance_update、acquisition、partnership、layoffs、regulation、capital_markets、leadership_change、product_launch、news 之一。"
                "officialness：只能是 official、media、mixed。"
                "impact_direction：只能是 positive、negative、neutral。"
                "impact_level：只能是 high、medium、low。"
                "price_sensitive：只能是 true 或 false。"
                "confidence：只能是 high、medium、low。"
                "不要输出 markdown，不要输出解释文字。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"公司：{company_name}\n"
                f"事件类型：{event_type_to_zh_label(cluster.event_type)}\n"
                f"聚类新闻数量：{len(cluster.items)}\n"
                f"新闻列表：\n{'\n'.join(article_lines)}"
            ),
        },
    ]


def build_claude_cli_prompt(company_name: str, cluster: EventCluster) -> str:
    article_lines = "\n".join(build_article_lines(cluster))
    return (
        "你是一名公司研究分析师。请把一组相关新闻总结为一个中文关键事件。\n"
        "必须返回严格 JSON，字段为 title, summary, key_points, event_type, officialness, impact_direction, impact_level, price_sensitive, confidence。\n"
        "title：中文标题，不超过18个汉字。\n"
        "summary：中文摘要，80到140字。\n"
        "key_points：2到4条中文要点。\n"
        "event_type：只能是 earnings_schedule、earnings_result、guidance_update、acquisition、partnership、layoffs、regulation、capital_markets、leadership_change、product_launch、news 之一。\n"
        "officialness：只能是 official、media、mixed。\n"
        "impact_direction：只能是 positive、negative、neutral。\n"
        "impact_level：只能是 high、medium、low。\n"
        "price_sensitive：只能是 true 或 false。\n"
        "confidence：只能是 high、medium、low。\n"
        "不要输出 markdown，不要输出解释文字。\n\n"
        f"公司：{company_name}\n"
        f"事件类型：{event_type_to_zh_label(cluster.event_type)}\n"
        f"聚类新闻数量：{len(cluster.items)}\n"
        f"新闻列表：\n{article_lines}\n"
    )


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
    event_type = str(parsed.get("event_type") or cluster.event_type).strip()
    officialness = str(parsed.get("officialness") or derive_officialness(cluster.items)).strip().lower()
    impact_direction = str(parsed.get("impact_direction") or derive_impact_direction(cluster.event_type, cluster.items)).strip().lower()
    impact_level = str(parsed.get("impact_level") or derive_impact_level(cluster.event_type, cluster.items)).strip().lower()
    price_sensitive_raw = parsed.get("price_sensitive")
    if not title or not summary:
        return None

    key_points = [str(item).strip() for item in key_points_raw if str(item).strip()]
    if not key_points:
        key_points = build_cluster_key_points(cluster)
    price_sensitive = normalize_price_sensitive(price_sensitive_raw, impact_level)

    return ClusterSummary(
        title=title[:120],
        summary=summary[:600],
        key_points=key_points[:4],
        confidence=confidence if confidence in {"high", "medium", "low"} else "medium",
        event_type=event_type if event_type in {
            "earnings_schedule", "earnings_result", "guidance_update",
            "acquisition", "partnership", "layoffs", "regulation",
            "capital_markets", "leadership_change", "product_launch", "news"
        } else cluster.event_type,
        officialness=officialness if officialness in {"official", "media", "mixed"} else derive_officialness(cluster.items),
        impact_direction=impact_direction if impact_direction in {"positive", "negative", "neutral"} else derive_impact_direction(cluster.event_type, cluster.items),
        impact_level=impact_level if impact_level in {"high", "medium", "low"} else derive_impact_level(cluster.event_type, cluster.items),
        price_sensitive=price_sensitive,
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

    extracted_title = extract_json_string_field(cleaned, "title")
    extracted_summary = extract_json_string_field(cleaned, "summary")
    extracted_confidence = extract_json_string_field(cleaned, "confidence")
    extracted_event_type = extract_json_string_field(cleaned, "event_type")
    extracted_officialness = extract_json_string_field(cleaned, "officialness")
    extracted_impact_direction = extract_json_string_field(cleaned, "impact_direction")
    extracted_impact_level = extract_json_string_field(cleaned, "impact_level")
    extracted_price_sensitive = extract_json_scalar_field(cleaned, "price_sensitive")
    extracted_key_points = extract_json_array_strings(cleaned, "key_points")

    lines = [line.strip("-* \t") for line in cleaned.splitlines() if line.strip()]
    title = extracted_title or ""
    summary = extracted_summary or ""
    key_points: list[str] = extracted_key_points[:]
    confidence = (extracted_confidence or "medium").strip().lower()
    event_type = (extracted_event_type or cluster.event_type).strip()
    officialness = (extracted_officialness or derive_officialness(cluster.items)).strip().lower()
    impact_direction = (extracted_impact_direction or derive_impact_direction(cluster.event_type, cluster.items)).strip().lower()
    impact_level = (extracted_impact_level or derive_impact_level(cluster.event_type, cluster.items)).strip().lower()

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

    title = sanitize_cluster_title(title, cluster)
    if not title:
        title = build_cluster_title(cluster.items[0].company_name, cluster)

    return ClusterSummary(
        title=title[:120],
        summary=summary[:600],
        key_points=key_points[:4],
        confidence=confidence if confidence in {"high", "medium", "low"} else "medium",
        event_type=event_type if event_type in {
            "earnings_schedule", "earnings_result", "guidance_update",
            "acquisition", "partnership", "layoffs", "regulation",
            "capital_markets", "leadership_change", "product_launch", "news"
        } else cluster.event_type,
        officialness=officialness if officialness in {"official", "media", "mixed"} else derive_officialness(cluster.items),
        impact_direction=impact_direction if impact_direction in {"positive", "negative", "neutral"} else derive_impact_direction(cluster.event_type, cluster.items),
        impact_level=impact_level if impact_level in {"high", "medium", "low"} else derive_impact_level(cluster.event_type, cluster.items),
        price_sensitive=normalize_price_sensitive(extracted_price_sensitive, impact_level),
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


def extract_json_string_field(text: str, field_name: str) -> str | None:
    pattern = rf'"{re.escape(field_name)}"\s*:\s*"((?:\\.|[^"\\])*)"'
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return None
    value = decode_json_string_fragment(match.group(1))
    return value.strip() or None


def extract_json_array_strings(text: str, field_name: str) -> list[str]:
    pattern = rf'"{re.escape(field_name)}"\s*:\s*\[(.*?)\]'
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return []
    array_content = match.group(1)
    return [
        decode_json_string_fragment(item).strip()
        for item in re.findall(r'"((?:\\.|[^"\\])*)"', array_content)
        if item.strip()
    ]


def extract_json_scalar_field(text: str, field_name: str) -> str | None:
    pattern = rf'"{re.escape(field_name)}"\s*:\s*(true|false|"[^"]*")'
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).strip()
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def decode_json_string_fragment(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return value


def normalize_price_sensitive(value: object, impact_level: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return impact_level in {"high", "medium"}


def sanitize_cluster_title(title: str, cluster: EventCluster) -> str:
    cleaned = title.strip().strip('"').strip("'")
    if not cleaned:
        return ""
    if cleaned.startswith("{") or cleaned.startswith("["):
        return ""
    if '"summary"' in cleaned or '"title"' in cleaned or cleaned.count(":") >= 2:
        extracted_title = extract_json_string_field(cleaned, "title")
        if extracted_title:
            return extracted_title[:120]
        return ""
    return cleaned[:120]


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


def event_type_to_zh_label(event_type: str) -> str:
    mapping = {
        "earnings_schedule": "财报日程",
        "earnings_result": "财报结果",
        "guidance_update": "业绩指引",
        "partnership": "合作进展",
        "product_launch": "产品发布",
        "acquisition": "并购交易",
        "leadership_change": "高管变动",
        "regulation": "监管事件",
        "layoffs": "裁员重组",
        "capital_markets": "资本运作",
        "news": "一般动态",
    }
    return mapping.get(event_type, "一般动态")


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
        "earnings_schedule": "Earnings Schedule",
        "earnings_result": "Earnings Result",
        "guidance_update": "Guidance Update",
        "partnership": "Partnership",
        "product_launch": "Product Launch",
        "acquisition": "Acquisition",
        "leadership_change": "Leadership Change",
        "regulation": "Regulation",
        "layoffs": "Layoffs",
        "capital_markets": "Capital Markets",
        "news": "General Update",
    }
    return mapping.get(event_type, "General Update")
