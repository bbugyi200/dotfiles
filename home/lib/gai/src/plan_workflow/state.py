"""State definition for the plan workflow."""

from typing import TypedDict


class PlanState(TypedDict):
    """State for the plan workflow LangGraph pipeline."""

    # Core inputs
    plan_name: str
    user_query: str
    plan_path: str

    # Stage outputs (may come from CLI or AI)
    sections: str | None  # Section names (newline-separated)
    qa_content: str | None  # Q&A content
    design_doc: str | None  # Current design document

    # Stage completion flags
    sections_from_cli: bool
    qa_from_cli: bool
    design_from_cli: bool

    # Refinement loop state
    refinement_query: str | None  # User's refinement request
    user_approved: bool  # True when user approves design

    # Workflow metadata
    current_stage: str  # "sections", "qa", "design", "refine"
    iteration: int  # Refinement iteration count
    failure_reason: str | None  # Set if workflow fails
