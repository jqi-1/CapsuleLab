from pathlib import Path


def load_corpus(data_dir: str = "data") -> list[str]:
    corpus_dir = Path(data_dir)
    if not corpus_dir.exists():
        return []
    texts: list[str] = []
    for path in sorted(corpus_dir.glob("**/*.txt")):
        texts.append(path.read_text(encoding="utf-8"))
    return texts


def keyword_search(query: str, documents: list[str], limit: int = 5) -> list[dict]:
    terms = {part.lower() for part in query.split() if part.strip()}
    scored = []
    for index, doc in enumerate(documents):
        lower = doc.lower()
        score = sum(1 for term in terms if term in lower)
        if score:
            scored.append({"index": index, "score": score, "text": doc[:500]})
    return sorted(scored, key=lambda row: row["score"], reverse=True)[:limit]
