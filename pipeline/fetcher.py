"""Stage 1a: Fetch and keyword-filter content from configured sources."""

import argparse
import html as html_lib
import io
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus, unquote, urljoin

import httpx
import trafilatura
from markitdown import MarkItDown

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
CONFIG_DIR = ROOT / "config"
DATA_RAW = ROOT / "data" / "raw"

USER_AGENT = "Mozilla/5.0 (compatible; Scottish-VC-Tracker/1.0)"

GROUP_A = [
    "raise", "raised", "funding", "investment", "invested", "backed", "backer",
    "venture", "capital", "round", "seed", "series a", "series b", "series c",
    "pre-seed", "growth round", "angel", "strategic investor", "new backer",
    "secures", "closes", "equity investment", "equity round",
]
GROUP_B = [
    "million", "£", "$m", "€m", "scotland", "scottish", "edinburgh",
    "glasgow", "aberdeen", "dundee",
]

ATOM_NS = "http://www.w3.org/2005/Atom"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"

_MARKITDOWN = MarkItDown()


def _passes_filter(text: str) -> bool:
    lower = text.lower()
    return any(t in lower for t in GROUP_A) and any(t in lower for t in GROUP_B)


def _is_pdf(resp: httpx.Response) -> bool:
    content_type = resp.headers.get("content-type", "")
    return "application/pdf" in content_type.lower() or str(resp.url).lower().split("?")[0].endswith(".pdf")


def _extract_text(resp: httpx.Response) -> str | None:
    """Extract article text from a fetched response — PDF via markitdown, else HTML via trafilatura."""
    if _is_pdf(resp):
        try:
            result = _MARKITDOWN.convert_stream(io.BytesIO(resp.content), file_extension=".pdf")
            return result.text_content or None
        except Exception:
            return None
    return trafilatura.extract(resp.text)


def _parse_feed(xml_text: str) -> list:
    """Parse RSS 2.0 or Atom feed into a list of item dicts."""
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    is_atom = ATOM_NS in root.tag or root.tag.lower() == "feed"

    if is_atom:
        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            title_el = entry.find(f"{{{ATOM_NS}}}title")
            link_el = entry.find(f"{{{ATOM_NS}}}link")
            pub_el = (
                entry.find(f"{{{ATOM_NS}}}published")
                or entry.find(f"{{{ATOM_NS}}}updated")
            )
            sum_el = entry.find(f"{{{ATOM_NS}}}summary") or entry.find(
                f"{{{ATOM_NS}}}content"
            )
            items.append(
                {
                    "title": title_el.text if title_el is not None else None,
                    "link": link_el.get("href") if link_el is not None else None,
                    "published": pub_el.text if pub_el is not None else None,
                    "description": sum_el.text if sum_el is not None else None,
                }
            )
    else:
        for item in root.iter("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            pub_el = item.find("pubDate")
            desc_el = item.find("description")
            content_el = item.find(f"{{{CONTENT_NS}}}encoded")
            description = (
                content_el.text if content_el is not None else None
            ) or (desc_el.text if desc_el is not None else None)
            items.append(
                {
                    "title": title_el.text if title_el is not None else None,
                    "link": link_el.text if link_el is not None else None,
                    "published": pub_el.text if pub_el is not None else None,
                    "description": description,
                }
            )

    return items


def _append_error(slug: str, url: str, error_msg: str, timestamp: str) -> None:
    errors_path = DATA_RAW / "errors.json"
    existing = []
    if errors_path.exists():
        try:
            existing = json.loads(errors_path.read_text())
        except Exception:
            existing = []
    existing.append({"source": slug, "url": url, "error": error_msg, "timestamp": timestamp})
    errors_path.write_text(json.dumps(existing, indent=2))


def _make_log_entry(slug: str) -> dict:
    return {
        "source_slug": slug,
        "url_fetched": "",
        "http_status": None,
        "items_found": 0,
        "items_passed_filter": 0,
        "candidates_added": 0,
        "text_extract_failures": 0,
        "error": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _fetch_rss(client: httpx.Client, source: dict, candidates: list, log: dict) -> None:
    rss_url = source["rss_url"]
    log["url_fetched"] = rss_url

    rss_ok = False
    items = []
    rss_error = None
    for attempt in range(2):
        try:
            resp = client.get(rss_url)
            log["http_status"] = resp.status_code
            resp.raise_for_status()
            items = _parse_feed(resp.text)
            rss_ok = True
            break
        except Exception as e:
            rss_error = f"RSS fetch failed: {e}"
            if attempt == 0:
                # Transient bot-protection blips (e.g. dailybusinessgroup.co.uk
                # 2026-07-13) have been observed to clear within hours — a short
                # single retry is cheap and catches the sub-minute cases.
                time.sleep(4)

    if not rss_ok or not items:
        if rss_ok and not items:
            rss_error = "RSS fetch succeeded but no items parsed"
        # Fall back to a direct page fetch with link extraction (see _fetch_page).
        # _fetch_page overwrites url_fetched/http_status/error on its own attempt —
        # preserve the original RSS failure reason rather than losing it.
        _fetch_page(client, source["url"], source, candidates, log)
        if rss_error:
            fallback_error = log.get("error")
            log["error"] = (
                f"{rss_error}; fallback page fetch also failed: {fallback_error}"
                if fallback_error
                else f"{rss_error} (fell back to page fetch, which succeeded)"
            )
        return

    log["items_found"] = len(items)
    passed = added = failures = 0

    for item in items:
        title = item.get("title") or ""
        description = item.get("description") or ""
        filter_text = (title + " " + description)[:2000]
        if not _passes_filter(filter_text):
            continue
        passed += 1

        link = item.get("link")
        article_text = None
        if link:
            try:
                article_resp = client.get(link)
                article_resp.raise_for_status()
                article_text = _extract_text(article_resp)
            except Exception:
                pass

        if not article_text:
            failures += 1
            article_text = description or title

        if article_text:
            candidates.append(
                {
                    "source_slug": source["slug"],
                    "source_name": source["name"],
                    "url": link or source["url"],
                    "title": title or None,
                    "published": item.get("published") or None,
                    "text": article_text,
                }
            )
            added += 1

    log["items_passed_filter"] = passed
    log["candidates_added"] = added
    log["text_extract_failures"] = failures


MAX_PAGE_LINKS = 20

_ANY_LINK_RE = re.compile(
    r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)


def _clean(s: str) -> str:
    # Strip entire style/script blocks first — some sites embed inline CSS inside
    # <a> tags (e.g. responsive-image styles), and a plain tag-strip would leave
    # the raw CSS/JS text behind as if it were link text.
    s = re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", s, flags=re.IGNORECASE | re.DOTALL)
    text = html_lib.unescape(re.sub(r"<[^>]+>", "", s))
    return re.sub(r"\s+", " ", text).strip()


def _extract_page_links(html: str, base_url: str) -> list:
    """Extract candidate article links (url, title) from an arbitrary listing/homepage.

    Generalizes the DuckDuckGo-specific parsing in `_parse_search_results` to any
    site: pull every <a> tag, resolve relative URLs, and drop obvious non-article
    links (nav, anchors, mailto). Titles under 10 chars are dropped as a cheap way
    to filter nav labels like "Home" or "About".
    """
    seen: set = set()
    links = []
    for href, title_raw in _ANY_LINK_RE.findall(html):
        if href.startswith(("#", "mailto:", "javascript:")):
            continue
        title = _clean(title_raw)
        if len(title) < 10:
            continue
        resolved = urljoin(base_url, href)
        if (
            not resolved.startswith("http")
            or resolved.rstrip("/") == base_url.rstrip("/")
            or resolved in seen
        ):
            continue
        seen.add(resolved)
        links.append({"url": resolved, "title": title})
    return links


def _fetch_page(client: httpx.Client, url: str, source: dict, candidates: list, log: dict) -> None:
    log["url_fetched"] = url
    log["items_found"] = 1

    try:
        resp = client.get(url)
        log["http_status"] = resp.status_code
        resp.raise_for_status()
    except Exception as e:
        log["error"] = str(e)
        return

    links = _extract_page_links(resp.text, url)
    passing_links = [link for link in links if _passes_filter(link["title"])][:MAX_PAGE_LINKS]

    if passing_links:
        log["items_found"] = len(links)
        passed = added = failures = 0
        for link in passing_links:
            passed += 1
            article_text = None
            try:
                article_resp = client.get(link["url"])
                article_resp.raise_for_status()
                article_text = _extract_text(article_resp)
            except Exception:
                pass

            if not article_text:
                failures += 1
                article_text = link["title"]

            candidates.append(
                {
                    "source_slug": source["slug"],
                    "source_name": source["name"],
                    "url": link["url"],
                    "title": link["title"],
                    "published": None,
                    "text": article_text,
                }
            )
            added += 1

        log["items_passed_filter"] = passed
        log["candidates_added"] = added
        log["text_extract_failures"] = failures
        return

    # No usable links found (e.g. url is itself a single article) — fall back to
    # whole-page extraction.
    text = _extract_text(resp)
    if not text:
        log["text_extract_failures"] = 1
        return

    if _passes_filter(text[:2000]):
        candidates.append(
            {
                "source_slug": source["slug"],
                "source_name": source["name"],
                "url": url,
                "title": None,
                "published": None,
                "text": text,
            }
        )
        log["items_passed_filter"] = 1
        log["candidates_added"] = 1


def _parse_search_results(html: str) -> list:
    """Extract individual result URLs and titles from a DuckDuckGo HTML results page."""
    results = []
    # Match <a ... class="result__a" ... href="URL">TITLE</a> (attribute order varies)
    link_re = re.compile(
        r'<a[^>]+class=["\']result__a["\'][^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    snippet_re = re.compile(
        r'class=["\']result__snippet["\'][^>]*>(.*?)</(?:a|span|div)>',
        re.IGNORECASE | re.DOTALL,
    )

    snippets = [_clean(m) for m in snippet_re.findall(html)]

    for i, (href, title_raw) in enumerate(link_re.findall(html)):
        # Resolve DuckDuckGo redirect URLs
        if "duckduckgo.com/l/" in href:
            m = re.search(r"uddg=([^&]+)", href)
            href = unquote(m.group(1)) if m else ""
        elif href.startswith("//"):
            href = "https:" + href

        if not href.startswith("http"):
            continue

        results.append(
            {
                "url": href,
                "title": _clean(title_raw),
                "snippet": snippets[i] if i < len(snippets) else "",
            }
        )

    return results


def _fetch_queries(client: httpx.Client, source: dict, candidates: list, log: dict) -> None:
    log["url_fetched"] = source["url"]
    queries = source.get("queries") or []
    total_found = total_passed = total_added = total_failures = 0
    last_status = None
    errors_list = []
    seen_urls: set = set()

    for i, query in enumerate(queries):
        if i > 0:
            time.sleep(2)
        search_url = f"{source['url']}?q={quote_plus(query)}"
        try:
            resp = client.get(search_url)
            last_status = resp.status_code
            resp.raise_for_status()

            results = _parse_search_results(resp.text)

            # Fall back to blob approach if parsing found nothing
            if not results:
                total_found += 1
                text = _extract_text(resp)
                if not text:
                    total_failures += 1
                elif _passes_filter(text[:2000]):
                    candidates.append(
                        {
                            "source_slug": source["slug"],
                            "source_name": source["name"],
                            "url": search_url,
                            "title": None,
                            "published": None,
                            "text": text,
                        }
                    )
                    total_passed += 1
                    total_added += 1
                continue

            total_found += len(results)

            for result in results:
                result_url = result["url"]
                if result_url in seen_urls:
                    continue

                filter_text = (result["title"] + " " + result["snippet"])[:2000]
                if not _passes_filter(filter_text):
                    continue

                seen_urls.add(result_url)
                total_passed += 1

                article_text = None
                try:
                    article_resp = client.get(result_url)
                    article_resp.raise_for_status()
                    article_text = _extract_text(article_resp)
                except Exception:
                    pass

                if not article_text:
                    total_failures += 1
                    article_text = result["snippet"] or result["title"]

                if article_text:
                    candidates.append(
                        {
                            "source_slug": source["slug"],
                            "source_name": source["name"],
                            "url": result_url,
                            "title": result["title"] or None,
                            "published": None,
                            "text": article_text,
                        }
                    )
                    total_added += 1

        except Exception as e:
            total_found += 1
            errors_list.append(f"query '{query}': {e}")

    log["http_status"] = last_status
    log["items_found"] = total_found
    log["items_passed_filter"] = total_passed
    log["candidates_added"] = total_added
    log["text_extract_failures"] = total_failures
    if errors_list:
        log["error"] = "; ".join(errors_list)


def _process_source(client: httpx.Client, source: dict, candidates: list) -> dict:
    if source.get("type") in ("browser", "firecrawl"):
        log = _make_log_entry(source["slug"])
        log["skipped"] = f"{source['type']} source — handled in Stage 1c"
        return log
    if (
        source.get("type") == "vc_newsrooms"
        and not source.get("rss_url")
        and not source.get("direct_fetch_confirmed")
    ):
        log = _make_log_entry(source["slug"])
        log["skipped"] = "vc_newsrooms without RSS — handled by Stage 1b scraper"
        return log
    if source.get("route_to_scraper"):
        log = _make_log_entry(source["slug"])
        log["skipped"] = "route_to_scraper — handled by Stage 1b scraper"
        return log
    log = _make_log_entry(source["slug"])
    try:
        if source.get("rss_url"):
            _fetch_rss(client, source, candidates, log)
        elif source.get("queries"):
            _fetch_queries(client, source, candidates, log)
        elif source.get("search_path"):
            url = source["url"].rstrip("/") + source["search_path"]
            _fetch_page(client, url, source, candidates, log)
        else:
            _fetch_page(client, source["url"], source, candidates, log)
    except Exception as e:
        log["error"] = str(e)
    return log


def run(date: str = None) -> dict:
    run_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    DATA_RAW.mkdir(parents=True, exist_ok=True)

    with open(CONFIG_DIR / "sources.json") as f:
        sources = json.load(f)["sources"]

    candidates: list = []
    fetch_log: list = []

    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=15.0,
        follow_redirects=True,
    ) as client:
        for source in sources:
            log_entry = _process_source(client, source, candidates)
            fetch_log.append(log_entry)
            if log_entry.get("error"):
                _append_error(
                    source["slug"],
                    log_entry.get("url_fetched") or source.get("url", ""),
                    log_entry["error"],
                    log_entry["timestamp"],
                )

    candidates_path = DATA_RAW / f"{run_date}_candidates.json"
    candidates_path.write_text(json.dumps(candidates, indent=2, ensure_ascii=False))

    fetch_log_path = DATA_RAW / f"{run_date}_fetch_log.json"
    fetch_log_path.write_text(json.dumps(fetch_log, indent=2, ensure_ascii=False))

    errors = sum(1 for e in fetch_log if e.get("error"))
    sources_ok = len(fetch_log) - errors

    print(f"Fetcher complete: {len(candidates)} candidates from {sources_ok} sources ({errors} errors)")

    return {
        "candidates": len(candidates),
        "sources_ok": sources_ok,
        "errors": errors,
        "fallback_needed": len(candidates) == 0,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser(description="Stage 1a: fetch and keyword-filter news sources")
    ap.add_argument("--date", default=None, help="Run date YYYY-MM-DD (default: today)")
    run(date=ap.parse_args().date)
