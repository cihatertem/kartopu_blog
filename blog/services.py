import re

GENERIC_PATTERN = re.compile(
    r"\{\{\s*(?P<tag>[a-zA-Z0-9_]+)(?::(?P<arg>[^\s\}]+))?\s*\}\}"
)

DEPENDENCY_GROUPS = {
    "portfolio": {
        "portfolio_summary",
        "portfolio_charts",
        "portfolio_irr_charts",
        "portfolio_category_summary",
        "portfolio_comparison_summary",
        "portfolio_comparison_charts",
    },
    "cashflow": {
        "cashflow_summary",
        "cashflow_charts",
        "cashflow_comparison_summary",
        "cashflow_comparison_charts",
    },
    "salary_savings": {
        "savings_rate_summary",
        "savings_rate_charts",
    },
    "dividend": {
        "dividend_summary",
        "dividend_charts",
        "dividend_comparison",
    },
}

def detect_content_dependencies(content: str) -> list[str]:
    """
    Analyzes the content for markers and returns a list of dependency groups.
    """
    if not content:
        return []
    
    found_tags = {match.group("tag") for match in GENERIC_PATTERN.finditer(content)}
    
    dependencies = []
    for group, tags in DEPENDENCY_GROUPS.items():
        if tags.intersection(found_tags):
            dependencies.append(group)
            
    return dependencies
