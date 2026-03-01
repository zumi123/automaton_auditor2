"""Typed state definitions for the Automaton Auditor swarm."""

import operator
from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# --- Detective Output ---


class Evidence(BaseModel):
    """Structured forensic evidence from a Detective agent."""

    goal: str = Field(description="The forensic goal being investigated")
    found: bool = Field(description="Whether the artifact exists or criterion is met")
    content: Optional[str] = Field(default=None, description="Raw content or snippet")
    location: str = Field(
        description="File path or commit hash where evidence was found"
    )
    rationale: str = Field(
        description="Rationale for confidence in this evidence"
    )
    confidence: float = Field(ge=0.0, le=1.0)


# --- Judge Output ---


class JudicialOpinion(BaseModel):
    """Structured opinion from a Judge persona."""

    judge: Literal["Prosecutor", "Defense", "TechLead"]
    criterion_id: str
    score: int = Field(ge=1, le=5)
    argument: str
    cited_evidence: List[str] = Field(default_factory=list)


# --- Chief Justice Output ---


class CriterionResult(BaseModel):
    """Final verdict for a single rubric criterion."""

    dimension_id: str
    dimension_name: str
    final_score: int = Field(ge=1, le=5)
    judge_opinions: List[JudicialOpinion] = Field(default_factory=list)
    dissent_summary: Optional[str] = Field(
        default=None,
        description="Required when score variance > 2",
    )
    remediation: str = Field(
        description="Specific file-level instructions for improvement"
    )


class AuditReport(BaseModel):
    """Final audit report produced by Chief Justice."""

    repo_url: str
    executive_summary: str
    overall_score: float = Field(ge=1.0, le=5.0)
    criteria: List[CriterionResult] = Field(default_factory=list)
    remediation_plan: str


# --- Graph State ---


class AgentState(TypedDict, total=False):
    """State passed through the LangGraph; uses reducers for parallel safety."""

    repo_url: str
    pdf_path: str
    rubric_dimensions: List[Dict[str, Any]]
    evidences: Annotated[Dict[str, List[Evidence]], operator.ior]
    opinions: Annotated[List[JudicialOpinion], operator.add]
    final_report: Optional[AuditReport]
    error: Optional[str]
