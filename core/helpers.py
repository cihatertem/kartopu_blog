def normalize_search_query(q: str) -> list[str]:
    """
    Arama terimini tokenize eder.
    Sadece anlamlı kelimeleri bırakır.
    """
    tokens = [token for token in q.lower().split() if len(token) >= 3]
    return tokens
