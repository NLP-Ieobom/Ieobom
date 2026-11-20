import os
from datetime import datetime, timezone
from urllib.parse import urlencode

from app.integrations.learning_http import ProviderError, request_json


def search_recent_papers(query: str, year: int) -> list[dict]:
    params = urlencode({
        "query": query[:200],
        "year": f"{year - 4}-{year}",
        "limit": 8,
        "fields": "paperId,title,year,abstract",
    })
    key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    response = request_json(
        f"https://api.semanticscholar.org/graph/v1/paper/search?{params}",
        provider="Semantic Scholar",
        headers={"x-api-key": key} if key else {},
        timeout=float(os.environ.get("SEMANTIC_SCHOLAR_TIMEOUT", "20")),
    )
    papers = response.get("data") if isinstance(response, dict) else None
    if not isinstance(papers, list) or any(not isinstance(paper, dict) for paper in papers):
        raise ProviderError("Semantic Scholar returned an invalid paper list")
    now = datetime.now(timezone.utc).isoformat()
    unique = {}
    for paper in papers:
        paper_id = paper.get("paperId")
        if (
            isinstance(paper_id, str) and len(paper_id) == 40
            and all(character in "0123456789abcdef" for character in paper_id)
            and isinstance(paper.get("title"), str) and paper["title"].strip()
            and isinstance(paper.get("abstract"), str) and paper["abstract"].strip()
            and isinstance(paper.get("year"), int) and year - 4 <= paper["year"] <= year
        ):
            unique[paper_id] = {
                "paper_id": paper_id,
                "title": paper["title"].strip(),
                "abstract": paper["abstract"][:5000],
                "year": paper["year"],
                "url": f"https://www.semanticscholar.org/paper/{paper_id}",
                "searched_at": now,
            }
    return list(unique.values())
