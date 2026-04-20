import requests
import feedparser
from datetime import datetime

def search_arxiv(query: str, max_results: int = 8) -> list[dict]:
    url = (
        "http://export.arxiv.org/api/query?"
        f"search_query=all:{requests.utils.quote(query)}"
        f"&start=0&max_results={max_results}"
        f"&sortBy=relevance&sortOrder=descending"
    )
    try:
        resp = requests.get(url, timeout=15)
        feed = feedparser.parse(resp.text)
    except Exception as e:
        return []

    papers = []
    for entry in feed.entries:
        published = entry.get("published", "")
        year = published[:4] if published else "unknown"
        authors = [a.name for a in getattr(entry, "authors", [])]
        categories = [t.get("term","") for t in getattr(entry, "tags", [])]
        papers.append({
            "id":         entry.get("id","").split("/")[-1],
            "title":      entry.get("title","").replace("\\n"," ").strip(),
            "summary":    entry.get("summary","").replace("\\n"," ").strip(),
            "link":       entry.get("link",""),
            "authors":    authors,
            "year":       year,
            "published":  published,
            "categories": categories,
            "source":     "arXiv",
        })
    return papers
