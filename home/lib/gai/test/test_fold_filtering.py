"""Tests for filter_agents_by_fold_state."""

from ace.tui.models.agent import Agent, AgentType
from ace.tui.models.agent_loader import filter_agents_by_fold_state
from ace.tui.models.fold_state import FoldStateManager


def _make_parent(raw_suffix: str, cl_name: str = "test_cl") -> Agent:
    """Create a workflow parent agent."""
    return Agent(
        agent_type=AgentType.WORKFLOW,
        cl_name=cl_name,
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=None,
        raw_suffix=raw_suffix,
    )


def _make_child(
    parent_timestamp: str,
    step_name: str = "step",
    is_hidden: bool = False,
) -> Agent:
    """Create a workflow child agent."""
    return Agent(
        agent_type=AgentType.WORKFLOW,
        cl_name=step_name,
        project_file="/tmp/test.gp",
        status="DONE",
        start_time=None,
        parent_workflow="test-workflow",
        parent_timestamp=parent_timestamp,
        step_name=step_name,
        is_hidden_step=is_hidden,
        raw_suffix=parent_timestamp,
    )


def _make_appears_as_agent(raw_suffix: str) -> Agent:
    """Create a workflow that appears as a regular agent."""
    return Agent(
        agent_type=AgentType.WORKFLOW,
        cl_name="agent_workflow",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=None,
        raw_suffix=raw_suffix,
        appears_as_agent=True,
    )


def test_collapsed_hides_all_children() -> None:
    """Test COLLAPSED state hides all children."""
    parent = _make_parent("ts1")
    child1 = _make_child("ts1", "step1")
    child2 = _make_child("ts1", "step2")
    agents = [parent, child1, child2]

    mgr = FoldStateManager()
    # Default is COLLAPSED
    filtered, counts = filter_agents_by_fold_state(agents, mgr)

    assert len(filtered) == 1
    assert filtered[0] is parent
    assert counts["ts1"] == (2, 0)  # 2 non-hidden, 0 hidden


def test_expanded_shows_non_hidden_children() -> None:
    """Test EXPANDED state shows non-hidden children only."""
    parent = _make_parent("ts1")
    child1 = _make_child("ts1", "step1")
    child2 = _make_child("ts1", "step2", is_hidden=True)
    agents = [parent, child1, child2]

    mgr = FoldStateManager()
    mgr.expand("ts1")  # COLLAPSED -> EXPANDED
    filtered, counts = filter_agents_by_fold_state(agents, mgr)

    assert len(filtered) == 2
    assert filtered[0] is parent
    assert filtered[1] is child1
    assert counts["ts1"] == (1, 1)  # 1 non-hidden, 1 hidden


def test_fully_expanded_shows_all_children() -> None:
    """Test FULLY_EXPANDED state shows all children including hidden."""
    parent = _make_parent("ts1")
    child1 = _make_child("ts1", "step1")
    child2 = _make_child("ts1", "step2", is_hidden=True)
    agents = [parent, child1, child2]

    mgr = FoldStateManager()
    mgr.expand("ts1")  # -> EXPANDED
    mgr.expand("ts1")  # -> FULLY_EXPANDED
    filtered, counts = filter_agents_by_fold_state(agents, mgr)

    assert len(filtered) == 3
    assert counts["ts1"] == (1, 1)


def test_appears_as_agent_is_foldable() -> None:
    """Test workflows that appear as agents are foldable."""
    agent = _make_appears_as_agent("ts1")
    child = _make_child("ts1", "step1")
    agents = [agent, child]

    mgr = FoldStateManager()
    # Default is COLLAPSED - child should be hidden
    filtered, counts = filter_agents_by_fold_state(agents, mgr)

    assert len(filtered) == 1
    assert filtered[0] is agent
    assert counts["ts1"] == (1, 0)

    # Expand - child should now be visible
    mgr.expand("ts1")
    filtered, counts = filter_agents_by_fold_state(agents, mgr)

    assert len(filtered) == 2
    assert filtered[0] is agent
    assert filtered[1] is child
    assert counts["ts1"] == (1, 0)


def test_multiple_parents_independent_fold_state() -> None:
    """Test multiple parents have independent fold states."""
    parent1 = _make_parent("ts1", "cl1")
    child1 = _make_child("ts1", "step1")
    parent2 = _make_parent("ts2", "cl2")
    child2 = _make_child("ts2", "step2")
    agents = [parent1, child1, parent2, child2]

    mgr = FoldStateManager()
    mgr.expand("ts1")  # Expand only first parent

    filtered, counts = filter_agents_by_fold_state(agents, mgr)

    assert len(filtered) == 3  # parent1 + child1 + parent2 (child2 hidden)
    assert filtered[0] is parent1
    assert filtered[1] is child1
    assert filtered[2] is parent2


def test_non_workflow_agents_pass_through() -> None:
    """Test non-workflow agents are always included."""
    running = Agent(
        agent_type=AgentType.RUNNING,
        cl_name="running_agent",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=None,
    )
    parent = _make_parent("ts1")
    child = _make_child("ts1", "step1")
    agents = [running, parent, child]

    mgr = FoldStateManager()
    filtered, counts = filter_agents_by_fold_state(agents, mgr)

    assert len(filtered) == 2  # running + parent (child collapsed)
    assert filtered[0] is running
    assert filtered[1] is parent


def test_correct_counts_with_mixed_hidden() -> None:
    """Test fold counts correctly separate hidden and non-hidden."""
    parent = _make_parent("ts1")
    child1 = _make_child("ts1", "step1", is_hidden=False)
    child2 = _make_child("ts1", "step2", is_hidden=True)
    child3 = _make_child("ts1", "step3", is_hidden=False)
    child4 = _make_child("ts1", "step4", is_hidden=True)
    agents = [parent, child1, child2, child3, child4]

    mgr = FoldStateManager()
    _, counts = filter_agents_by_fold_state(agents, mgr)

    assert counts["ts1"] == (2, 2)  # 2 non-hidden, 2 hidden


def test_empty_agents_list() -> None:
    """Test with empty agents list."""
    mgr = FoldStateManager()
    filtered, counts = filter_agents_by_fold_state([], mgr)

    assert filtered == []
    assert counts == {}
