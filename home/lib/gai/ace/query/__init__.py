"""Query language for filtering ChangeSpecs.

This package provides a query language for filtering ChangeSpecs using
boolean expressions with string matching and property filters.

Query Language Examples:
    foobar                     - Case-insensitive match (bare word)
    "foo bar"                  - Case-insensitive match (quoted, allows spaces)
    c"FooBar"                  - Case-sensitive match
    !draft                     - NOT containing "draft"
    feature AND test           - Contains both
    feature test               - Same as above (implicit AND)
    feature OR bugfix          - Contains either
    (a OR b) AND !skip         - Grouped expression

Property Filters:
    %d, %m, %s, %r             - Status shortcuts (DRAFTED, MAILED, SUBMITTED, REVERTED)
    status:DRAFTED             - Explicit status filter
    +myproject                 - Project filter shortcut
    project:myproject          - Explicit project filter
    ^parent                    - Ancestor filter shortcut
    ancestor:parent            - Explicit ancestor filter

Precedence (tightest to loosest):
    1. ! (NOT)
    2. AND (explicit or implicit via juxtaposition)
    3. OR
    Parentheses override precedence.
"""

from .evaluator import evaluate_query
from .parser import QueryParseError, parse_query
from .types import (
    AndExpr,
    NotExpr,
    OrExpr,
    PropertyMatch,
    QueryExpr,
    StringMatch,
    to_canonical_string,
)

__all__ = [
    # Parser
    "parse_query",
    "QueryParseError",
    # Evaluator
    "evaluate_query",
    # Types
    "QueryExpr",
    "StringMatch",
    "PropertyMatch",
    "NotExpr",
    "AndExpr",
    "OrExpr",
    # Utilities
    "to_canonical_string",
]
