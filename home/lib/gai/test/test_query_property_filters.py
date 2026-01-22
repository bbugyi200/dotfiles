"""Tests for property filter functionality in the query language."""

from typing import Any

import pytest
from ace.query import (
    AndExpr,
    NotExpr,
    OrExpr,
    PropertyMatch,
    StringMatch,
    evaluate_query,
    parse_query,
    to_canonical_string,
)
from ace.query.tokenizer import TokenizerError, TokenType, tokenize

# --- Tokenizer Tests ---


def test_tokenize_status_shorthand_drafted() -> None:
    """Test tokenizing %d as status:DRAFTED."""
    tokens = list(tokenize("%d"))
    assert len(tokens) == 2
    assert tokens[0].type == TokenType.PROPERTY
    assert tokens[0].value == "DRAFTED"
    assert tokens[0].property_key == "status"
    assert tokens[1].type == TokenType.EOF


def test_tokenize_status_shorthand_mailed() -> None:
    """Test tokenizing %m as status:MAILED."""
    tokens = list(tokenize("%m"))
    assert tokens[0].type == TokenType.PROPERTY
    assert tokens[0].value == "MAILED"
    assert tokens[0].property_key == "status"


def test_tokenize_status_shorthand_submitted() -> None:
    """Test tokenizing %s as status:SUBMITTED."""
    tokens = list(tokenize("%s"))
    assert tokens[0].type == TokenType.PROPERTY
    assert tokens[0].value == "SUBMITTED"
    assert tokens[0].property_key == "status"


def test_tokenize_status_shorthand_reverted() -> None:
    """Test tokenizing %r as status:REVERTED."""
    tokens = list(tokenize("%r"))
    assert tokens[0].type == TokenType.PROPERTY
    assert tokens[0].value == "REVERTED"
    assert tokens[0].property_key == "status"


def test_tokenize_status_shorthand_wip() -> None:
    """Test tokenizing %w as status:WIP."""
    tokens = list(tokenize("%w"))
    assert tokens[0].type == TokenType.PROPERTY
    assert tokens[0].value == "WIP"
    assert tokens[0].property_key == "status"


def test_tokenize_status_shorthand_case_insensitive() -> None:
    """Test that %D (uppercase) also works as status shorthand."""
    tokens = list(tokenize("%D"))
    assert tokens[0].type == TokenType.PROPERTY
    assert tokens[0].value == "DRAFTED"
    assert tokens[0].property_key == "status"


def test_tokenize_status_shorthand_invalid() -> None:
    """Test that %x raises error for invalid status shorthand."""
    with pytest.raises(TokenizerError) as exc_info:
        list(tokenize("%x"))
    assert "Invalid status shorthand" in str(exc_info.value)


def test_tokenize_project_shorthand() -> None:
    """Test tokenizing +project as project:project."""
    tokens = list(tokenize("+myproject"))
    assert len(tokens) == 2
    assert tokens[0].type == TokenType.PROPERTY
    assert tokens[0].value == "myproject"
    assert tokens[0].property_key == "project"


def test_tokenize_project_shorthand_with_underscore() -> None:
    """Test tokenizing +my_project as project:my_project."""
    tokens = list(tokenize("+my_project"))
    assert tokens[0].type == TokenType.PROPERTY
    assert tokens[0].value == "my_project"
    assert tokens[0].property_key == "project"


def test_tokenize_project_shorthand_with_hyphen() -> None:
    """Test tokenizing +my-project as project:my-project."""
    tokens = list(tokenize("+my-project"))
    assert tokens[0].type == TokenType.PROPERTY
    assert tokens[0].value == "my-project"
    assert tokens[0].property_key == "project"


def test_tokenize_ancestor_shorthand() -> None:
    """Test tokenizing ^parent as ancestor:parent."""
    tokens = list(tokenize("^parent_name"))
    assert len(tokens) == 2
    assert tokens[0].type == TokenType.PROPERTY
    assert tokens[0].value == "parent_name"
    assert tokens[0].property_key == "ancestor"


def test_tokenize_explicit_status_property() -> None:
    """Test tokenizing status:DRAFTED explicitly."""
    tokens = list(tokenize("status:DRAFTED"))
    assert len(tokens) == 2
    assert tokens[0].type == TokenType.PROPERTY
    assert tokens[0].value == "DRAFTED"
    assert tokens[0].property_key == "status"


def test_tokenize_explicit_project_property() -> None:
    """Test tokenizing project:myproject explicitly."""
    tokens = list(tokenize("project:myproject"))
    assert tokens[0].type == TokenType.PROPERTY
    assert tokens[0].value == "myproject"
    assert tokens[0].property_key == "project"


def test_tokenize_explicit_ancestor_property() -> None:
    """Test tokenizing ancestor:parent explicitly."""
    tokens = list(tokenize("ancestor:parent"))
    assert tokens[0].type == TokenType.PROPERTY
    assert tokens[0].value == "parent"
    assert tokens[0].property_key == "ancestor"


def test_tokenize_property_with_quoted_value() -> None:
    """Test tokenizing property with quoted value."""
    tokens = list(tokenize('status:"my status"'))
    assert tokens[0].type == TokenType.PROPERTY
    assert tokens[0].value == "my status"
    assert tokens[0].property_key == "status"


def test_tokenize_invalid_property_key() -> None:
    """Test that unknown property key raises error."""
    with pytest.raises(TokenizerError) as exc_info:
        list(tokenize("unknown:value"))
    assert "Unknown property key" in str(exc_info.value)


def test_tokenize_property_in_expression() -> None:
    """Test property filter in complex expression."""
    tokens = list(tokenize('%d AND "foo"'))
    assert tokens[0].type == TokenType.PROPERTY
    assert tokens[0].value == "DRAFTED"
    assert tokens[1].type == TokenType.AND
    assert tokens[2].type == TokenType.STRING
    assert tokens[2].value == "foo"


def test_tokenize_multiple_properties() -> None:
    """Test multiple property filters in expression."""
    tokens = list(tokenize("%d +myproject"))
    assert tokens[0].type == TokenType.PROPERTY
    assert tokens[0].property_key == "status"
    assert tokens[1].type == TokenType.PROPERTY
    assert tokens[1].property_key == "project"


# --- Parser Tests ---


def test_parse_status_property() -> None:
    """Test parsing status property filter."""
    result = parse_query("%d")
    assert isinstance(result, PropertyMatch)
    assert result.key == "status"
    assert result.value == "DRAFTED"


def test_parse_project_property() -> None:
    """Test parsing project property filter."""
    result = parse_query("+myproject")
    assert isinstance(result, PropertyMatch)
    assert result.key == "project"
    assert result.value == "myproject"


def test_parse_ancestor_property() -> None:
    """Test parsing ancestor property filter."""
    result = parse_query("^parent")
    assert isinstance(result, PropertyMatch)
    assert result.key == "ancestor"
    assert result.value == "parent"


def test_parse_explicit_property() -> None:
    """Test parsing explicit property syntax."""
    result = parse_query("status:MAILED")
    assert isinstance(result, PropertyMatch)
    assert result.key == "status"
    assert result.value == "MAILED"


def test_parse_status_shorthand_in_and_expression() -> None:
    """Test parsing status shorthand in AND expression."""
    result = parse_query('%d AND "foo"')
    assert isinstance(result, AndExpr)
    assert len(result.operands) == 2
    assert isinstance(result.operands[0], PropertyMatch)
    assert result.operands[0].key == "status"
    assert isinstance(result.operands[1], StringMatch)


def test_parse_status_shorthand_in_or_expression() -> None:
    """Test parsing status shorthands combined with OR."""
    result = parse_query("%d OR %m")
    assert isinstance(result, OrExpr)
    assert len(result.operands) == 2
    assert isinstance(result.operands[0], PropertyMatch)
    assert result.operands[0].value == "DRAFTED"
    assert isinstance(result.operands[1], PropertyMatch)
    assert result.operands[1].value == "MAILED"


def test_parse_property_with_not() -> None:
    """Test parsing NOT with property filter."""
    result = parse_query("!%r")
    assert isinstance(result, NotExpr)
    assert isinstance(result.operand, PropertyMatch)
    assert result.operand.key == "status"
    assert result.operand.value == "REVERTED"


def test_parse_combined_properties() -> None:
    """Test parsing multiple property filters."""
    result = parse_query("%d +myproject")
    assert isinstance(result, AndExpr)
    assert len(result.operands) == 2
    assert isinstance(result.operands[0], PropertyMatch)
    assert result.operands[0].key == "status"
    assert isinstance(result.operands[1], PropertyMatch)
    assert result.operands[1].key == "project"


def test_parse_property_with_string() -> None:
    """Test parsing property with string search."""
    result = parse_query('^parent "feature"')
    assert isinstance(result, AndExpr)
    assert len(result.operands) == 2
    assert isinstance(result.operands[0], PropertyMatch)
    assert result.operands[0].key == "ancestor"
    assert isinstance(result.operands[1], StringMatch)


# --- Canonicalization Tests ---


def test_canonical_status_property() -> None:
    """Test canonicalization of status property."""
    result = parse_query("%d")
    assert to_canonical_string(result) == "status:DRAFTED"


def test_canonical_project_property() -> None:
    """Test canonicalization of project property."""
    result = parse_query("+myproject")
    assert to_canonical_string(result) == "project:myproject"


def test_canonical_ancestor_property() -> None:
    """Test canonicalization of ancestor property."""
    result = parse_query("^parent")
    assert to_canonical_string(result) == "ancestor:parent"


def test_canonical_property_in_expression() -> None:
    """Test canonicalization of property in expression."""
    result = parse_query('%d "foo"')
    assert to_canonical_string(result) == 'status:DRAFTED AND "foo"'


def test_canonical_status_or_expression() -> None:
    """Test canonicalization of OR status expression."""
    result = parse_query("%d OR %m")
    assert to_canonical_string(result) == "status:DRAFTED OR status:MAILED"


# --- Evaluator Tests ---


def test_evaluate_status_drafted(
    make_changespec: Any,
) -> None:
    """Test status:DRAFTED matches Drafted status."""
    query = parse_query("%d")
    cs = make_changespec.create(status="Drafted")
    assert evaluate_query(query, cs) is True


def test_evaluate_status_case_insensitive(
    make_changespec: Any,
) -> None:
    """Test status matching is case-insensitive."""
    query = parse_query("status:drafted")
    cs = make_changespec.create(status="Drafted")
    assert evaluate_query(query, cs) is True


def test_evaluate_status_with_workspace_suffix(
    make_changespec: Any,
) -> None:
    """Test status matches even with workspace suffix."""
    query = parse_query("%d")
    cs = make_changespec.create(status="Drafted (fig_1)")
    assert evaluate_query(query, cs) is True


def test_evaluate_status_with_ready_to_mail_suffix(
    make_changespec: Any,
) -> None:
    """Test status matches even with READY TO MAIL suffix."""
    query = parse_query("%d")
    cs = make_changespec.create(status="Drafted - (!: READY TO MAIL)")
    assert evaluate_query(query, cs) is True


def test_evaluate_status_no_match(
    make_changespec: Any,
) -> None:
    """Test status filter does not match different status."""
    query = parse_query("%d")
    cs = make_changespec.create(status="Mailed")
    assert evaluate_query(query, cs) is False


def test_evaluate_project_match(
    make_changespec: Any,
) -> None:
    """Test project filter matches project basename."""
    query = parse_query("+myproject")
    cs = make_changespec.create(
        file_path="/home/user/.gai/projects/myproject/myproject.gp"
    )
    assert evaluate_query(query, cs) is True


def test_evaluate_project_case_insensitive(
    make_changespec: Any,
) -> None:
    """Test project matching is case-insensitive."""
    query = parse_query("+MYPROJECT")
    cs = make_changespec.create(
        file_path="/home/user/.gai/projects/myproject/myproject.gp"
    )
    assert evaluate_query(query, cs) is True


def test_evaluate_project_no_match(
    make_changespec: Any,
) -> None:
    """Test project filter does not match different project."""
    query = parse_query("+otherproject")
    cs = make_changespec.create(
        file_path="/home/user/.gai/projects/myproject/myproject.gp"
    )
    assert evaluate_query(query, cs) is False


def test_evaluate_ancestor_matches_name(
    make_changespec: Any,
) -> None:
    """Test ancestor filter matches ChangeSpec's own name."""
    query = parse_query("^myfeature")
    cs = make_changespec.create(name="myfeature")
    all_cs = [cs]
    assert evaluate_query(query, cs, all_cs) is True


def test_evaluate_ancestor_matches_parent(
    make_changespec: Any,
) -> None:
    """Test ancestor filter matches direct parent."""
    query = parse_query("^parent_feature")
    parent_cs = make_changespec.create(name="parent_feature")
    child_cs = make_changespec.create(name="child_feature", parent="parent_feature")
    all_cs = [parent_cs, child_cs]
    assert evaluate_query(query, child_cs, all_cs) is True


def test_evaluate_ancestor_matches_grandparent(
    make_changespec: Any,
) -> None:
    """Test ancestor filter matches grandparent through chain."""
    query = parse_query("^grandparent")
    grandparent_cs = make_changespec.create(name="grandparent")
    parent_cs = make_changespec.create(name="parent", parent="grandparent")
    child_cs = make_changespec.create(name="child", parent="parent")
    all_cs = [grandparent_cs, parent_cs, child_cs]
    assert evaluate_query(query, child_cs, all_cs) is True


def test_evaluate_ancestor_case_insensitive(
    make_changespec: Any,
) -> None:
    """Test ancestor matching is case-insensitive."""
    query = parse_query("^PARENT")
    parent_cs = make_changespec.create(name="parent")
    child_cs = make_changespec.create(name="child", parent="parent")
    all_cs = [parent_cs, child_cs]
    assert evaluate_query(query, child_cs, all_cs) is True


def test_evaluate_ancestor_no_match(
    make_changespec: Any,
) -> None:
    """Test ancestor filter does not match unrelated ChangeSpec."""
    query = parse_query("^unrelated")
    cs = make_changespec.create(name="feature", parent="different_parent")
    all_cs = [cs]
    assert evaluate_query(query, cs, all_cs) is False


def test_evaluate_ancestor_without_all_changespecs(
    make_changespec: Any,
) -> None:
    """Test ancestor filter returns False when all_changespecs is None."""
    query = parse_query("^parent")
    cs = make_changespec.create(name="feature", parent="parent")
    # all_changespecs=None (default)
    assert evaluate_query(query, cs) is False


def test_evaluate_ancestor_handles_cycle(
    make_changespec: Any,
) -> None:
    """Test ancestor filter handles cycles without infinite loop."""
    query = parse_query("^unrelated")
    # Create a cycle: A -> B -> A
    cs_a = make_changespec.create(name="A", parent="B")
    cs_b = make_changespec.create(name="B", parent="A")
    all_cs = [cs_a, cs_b]
    # Should not hang, should return False since "unrelated" is not in the cycle
    assert evaluate_query(query, cs_a, all_cs) is False


def test_evaluate_combined_status_and_project(
    make_changespec: Any,
) -> None:
    """Test combining status and project filters."""
    query = parse_query("%d +myproject")
    cs1 = make_changespec.create(
        status="Drafted",
        file_path="/home/user/.gai/projects/myproject/myproject.gp",
    )
    assert evaluate_query(query, cs1) is True

    cs2 = make_changespec.create(
        status="Mailed",
        file_path="/home/user/.gai/projects/myproject/myproject.gp",
    )
    assert evaluate_query(query, cs2) is False

    cs3 = make_changespec.create(
        status="Drafted",
        file_path="/home/user/.gai/projects/otherproject/otherproject.gp",
    )
    assert evaluate_query(query, cs3) is False


def test_evaluate_status_or_combined(
    make_changespec: Any,
) -> None:
    """Test OR combination of status filters."""
    query = parse_query("%d OR %m")
    cs_drafted = make_changespec.create(status="Drafted")
    cs_mailed = make_changespec.create(status="Mailed")
    cs_submitted = make_changespec.create(status="Submitted")

    assert evaluate_query(query, cs_drafted) is True
    assert evaluate_query(query, cs_mailed) is True
    assert evaluate_query(query, cs_submitted) is False


def test_evaluate_not_status(
    make_changespec: Any,
) -> None:
    """Test NOT with status filter."""
    query = parse_query("!%r")
    cs_drafted = make_changespec.create(status="Drafted")
    cs_reverted = make_changespec.create(status="Reverted")

    assert evaluate_query(query, cs_drafted) is True
    assert evaluate_query(query, cs_reverted) is False


# --- Integration Tests ---


def test_full_pipeline_with_property_filters(
    make_changespec: Any,
) -> None:
    """Test full pipeline with property filters."""
    changespecs = [
        make_changespec.create(
            name="feature_a",
            status="Drafted",
            file_path="/home/user/.gai/projects/projectA/projectA.gp",
        ),
        make_changespec.create(
            name="feature_b",
            status="Mailed",
            file_path="/home/user/.gai/projects/projectA/projectA.gp",
        ),
        make_changespec.create(
            name="feature_c",
            status="Drafted",
            file_path="/home/user/.gai/projects/projectB/projectB.gp",
        ),
    ]

    # Filter by status and project
    query = parse_query("%d +projectA")
    results = [cs for cs in changespecs if evaluate_query(query, cs)]
    assert len(results) == 1
    assert results[0].name == "feature_a"


def test_full_pipeline_ancestor_chain(
    make_changespec: Any,
) -> None:
    """Test full pipeline with ancestor filter on parent chain."""
    parent = make_changespec.create(name="parent_feature")
    child = make_changespec.create(name="child_feature", parent="parent_feature")
    grandchild = make_changespec.create(name="grandchild", parent="child_feature")
    unrelated = make_changespec.create(name="unrelated_feature")

    all_cs = [parent, child, grandchild, unrelated]

    query = parse_query("^parent_feature")
    results = [cs for cs in all_cs if evaluate_query(query, cs, all_cs)]

    # Should match: parent (name match), child (parent match), grandchild (grandparent)
    # Should NOT match: unrelated
    assert len(results) == 3
    names = [cs.name for cs in results]
    assert "parent_feature" in names
    assert "child_feature" in names
    assert "grandchild" in names
    assert "unrelated_feature" not in names
