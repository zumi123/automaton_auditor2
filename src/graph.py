"""LangGraph StateGraph - Digital Courtroom orchestration."""

from langgraph.graph import END, START, StateGraph

from src.state import AgentState
from src.nodes.detectives import (
    DocAnalystNode,
    EvidenceAggregatorNode,
    RepoInvestigatorNode,
    VisionInspectorNode,
)
from src.nodes.judges import DefenseNode, ProsecutorNode, TechLeadNode
from src.nodes.justice import ChiefJusticeNode


def build_auditor_graph():
    """
    Build the complete Digital Courtroom graph:
    START -> [Detectives parallel] -> EvidenceAggregator -> [Judges parallel] -> ChiefJustice -> END
    """
    builder = StateGraph(AgentState)

    # Layer 1: Detectives (fan-out)
    builder.add_node("RepoInvestigator", RepoInvestigatorNode)
    builder.add_node("DocAnalyst", DocAnalystNode)
    builder.add_node("VisionInspector", VisionInspectorNode)

    # Fan-in: Evidence aggregation
    builder.add_node("EvidenceAggregator", EvidenceAggregatorNode)

    # Layer 2: Judges (fan-out)
    builder.add_node("Prosecutor", ProsecutorNode)
    builder.add_node("Defense", DefenseNode)
    builder.add_node("TechLead", TechLeadNode)

    # Layer 3: Synthesis
    builder.add_node("ChiefJustice", ChiefJusticeNode)

    # Edges: parallel detectives from START
    builder.add_edge(START, "RepoInvestigator")
    builder.add_edge(START, "DocAnalyst")
    builder.add_edge(START, "VisionInspector")

    # Fan-in to EvidenceAggregator (all detectives must complete)
    builder.add_edge("RepoInvestigator", "EvidenceAggregator")
    builder.add_edge("DocAnalyst", "EvidenceAggregator")
    builder.add_edge("VisionInspector", "EvidenceAggregator")

    # Fan-out to Judges (parallel)
    builder.add_edge("EvidenceAggregator", "Prosecutor")
    builder.add_edge("EvidenceAggregator", "Defense")
    builder.add_edge("EvidenceAggregator", "TechLead")

    # Fan-in to ChiefJustice (all judges must complete)
    builder.add_edge("Prosecutor", "ChiefJustice")
    builder.add_edge("Defense", "ChiefJustice")
    builder.add_edge("TechLead", "ChiefJustice")

    # End
    builder.add_edge("ChiefJustice", END)

    return builder.compile()


def run_audit(repo_url: str, pdf_path: str) -> dict:
    """
    Run the auditor against a repo URL and PDF report.
    Returns final state including final_report.
    """
    graph = build_auditor_graph()
    initial: AgentState = {
        "repo_url": repo_url,
        "pdf_path": pdf_path,
        "evidences": {},
        "opinions": [],
    }
    result = graph.invoke(initial)
    return result
