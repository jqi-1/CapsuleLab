def recall_at_k(relevant_ids: set[int], retrieved_ids: list[int], k: int = 5) -> float:
    if not relevant_ids:
        return 0.0
    hits = relevant_ids.intersection(retrieved_ids[:k])
    return len(hits) / len(relevant_ids)


def summarize_run(query: str, relevant_ids: set[int], retrieved_ids: list[int]) -> dict:
    return {
        "query": query,
        "retrieved": retrieved_ids,
        "recall_at_5": recall_at_k(relevant_ids, retrieved_ids, k=5),
    }
