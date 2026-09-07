"""Fetch random Wikipedia articles, archive them as PDFs, and ingest them via FastAPI.

Usage:
    python scripts/ingest_random_wikipedia.py --count 1000 --api-url http://127.0.0.1:8000

The script is intentionally API-based: it exercises the same ingestion path as a
client application instead of writing directly to PostgreSQL.
"""

import argparse
import base64
import json
import sys
import time
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


USER_AGENT = "Wikipedia-Knowledge-Assistant/0.1 (local batch importer)"


def get_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def random_titles(batch_size: int) -> list[str]:
    query = urlencode({"action": "query", "list": "random", "rnnamespace": 0, "rnlimit": batch_size, "format": "json"})
    data = get_json(f"https://en.wikipedia.org/w/api.php?{query}")
    return [item["title"] for item in data["query"]["random"]]


def fetch_article(title: str) -> dict:
    url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(title.replace(" ", "_"))
    return get_json(url)


def create_pdf(article: dict) -> bytes:
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(buffer, pagesize=LETTER, rightMargin=inch, leftMargin=inch, topMargin=inch, bottomMargin=inch)
    story = [Paragraph(escape(article["title"]), styles["Title"]), Spacer(1, 0.2 * inch)]
    if article.get("description"):
        story.append(Paragraph(escape(article["description"]), styles["Heading3"]))
        story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(escape(article.get("extract", "")), styles["BodyText"]))
    story.append(Spacer(1, 0.2 * inch))
    source_url = article.get("content_urls", {}).get("desktop", {}).get("page", "")
    story.append(Paragraph(f"Source: {escape(source_url)}", styles["Normal"]))
    document.build(story)
    return buffer.getvalue()


def post_to_api(api_url: str, article: dict) -> dict:
    pdf_data = create_pdf(article)
    payload = json.dumps({
        "title": article["title"],
        "text": article.get("extract", ""),
        "source_url": article.get("content_urls", {}).get("desktop", {}).get("page"),
        "pdf_base64": base64.b64encode(pdf_data).decode("ascii"),
    }).encode("utf-8")
    request = Request(api_url.rstrip("/") + "/ingest", data=payload, headers={"Content-Type": "application/json", "User-Agent": USER_AGENT}, method="POST")
    with urlopen(request, timeout=120) as response:
        return json.load(response)


def check_api(api_url: str) -> None:
    """Fail before downloading articles if the local API is unavailable."""
    try:
        data = get_json(api_url.rstrip("/") + "/health")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(
            f"FastAPI is not reachable at {api_url}. Start it with: "
            f"uvicorn main:app --reload ({exc})"
        ) from exc
    if data.get("database") == "unavailable":
        raise RuntimeError(f"FastAPI is running, but PostgreSQL is unavailable: {data.get('detail', 'unknown error')}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=1000, help="Number of articles to ingest")
    parser.add_argument("--batch-size", type=int, default=10, help="Wikipedia random titles per request")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000", help="Base URL of the FastAPI service")
    parser.add_argument("--delay", type=float, default=0.2, help="Delay between articles in seconds")
    args = parser.parse_args()
    if args.count < 1 or not 1 <= args.batch_size <= 20:
        parser.error("count must be positive and batch-size must be between 1 and 20")

    try:
        check_api(args.api_url)
    except RuntimeError as exc:
        parser.error(str(exc))

    imported = failed = 0
    seen: set[str] = set()
    while imported < args.count:
        try:
            titles = random_titles(min(args.batch_size, args.count - imported + 5))
        except (HTTPError, URLError, TimeoutError) as exc:
            print(f"Could not fetch random titles: {exc}", file=sys.stderr)
            time.sleep(2)
            continue
        for title in titles:
            if imported >= args.count or title in seen:
                continue
            seen.add(title)
            try:
                article = fetch_article(title)
                if len(article.get("extract", "").strip()) < 20:
                    print(f"SKIP  {title} (article summary is too short)")
                    continue
                result = post_to_api(args.api_url, article)
                imported += 1
                print(f"[{imported}/{args.count}] OK    {article['title']} -> PDF stored in PostgreSQL ({result['chunks_created']} chunks)", flush=True)
            except Exception as exc:
                failed += 1
                print(f"FAIL  {title}: {exc}", file=sys.stderr, flush=True)
            time.sleep(args.delay)
    print(f"Finished: imported={imported}, failed={failed}, PDFs stored in PostgreSQL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
