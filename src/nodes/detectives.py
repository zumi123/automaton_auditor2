"""Detective layer nodes - RepoInvestigator, DocAnalyst, VisionInspector."""

import json
from pathlib import Path
from typing import Any, Dict, List

from src.state import AgentState, Evidence
from src.tools.doc_tools import extract_images_from_pdf, ingest_pdf, query_pdf_chunks
from src.tools.repo_tools import analyze_graph_structure, clone_repo, extract_git_history


def _load_rubric() -> Dict[str, Any]:
    with open(Path(__file__).resolve().parents[2] / "rubric.json") as f:
        return json.load(f)


def _get_forensic_instructions(target: str) -> List[Dict[str, Any]]:
    """Filter rubric dimensions by target_artifact."""
    rubric = _load_rubric()
    return [
        d for d in rubric.get("dimensions", [])
        if d.get("target_artifact") == target
    ]


def RepoInvestigatorNode(state: AgentState) -> Dict[str, Any]:
    """
    The Code Detective. Clones repo, extracts git history, analyzes AST.
    Outputs structured Evidence keyed by dimension id.
    """
    print("  RepoInvestigator: cloning repo and analyzing...", flush=True)
    repo_url = state.get("repo_url", "")
    if not repo_url:
        return {"evidences": {"repo": [Evidence(goal="clone", found=False, location="", rationale="No repo_url", confidence=0.0)]}}

    clone_path, clone_evidences = clone_repo(repo_url)
    evidences: Dict[str, List[Evidence]] = {"repo": list(clone_evidences)}

    if not clone_path:
        return {"evidences": evidences}

    # Git history
    git_evidences = extract_git_history(clone_path)
    evidences["repo"] = evidences.get("repo", []) + git_evidences

    # Graph and structure analysis
    struct_evidences = analyze_graph_structure(clone_path)
    evidences["repo"] = evidences.get("repo", []) + struct_evidences

    # Map by dimension for downstream
    by_dim: Dict[str, List[Evidence]] = {}
    for e in evidences["repo"]:
        dim = "git_forensic_analysis" if "git" in e.goal.lower() else \
              "state_management_rigor" if "state" in e.goal.lower() else \
              "graph_orchestration" if "graph" in e.goal.lower() else \
              "safe_tool_engineering" if "sandbox" in e.goal.lower() or "tool" in e.goal.lower() else "repo"
        by_dim.setdefault(dim, []).append(e)
    by_dim["repo_general"] = evidences["repo"]

    return {"evidences": by_dim}


def DocAnalystNode(state: AgentState) -> Dict[str, Any]:
    """
    The Paperwork Detective. Ingests PDF, queries for theoretical depth,
    cross-references file paths with RepoInvestigator evidence.
    """
    print("  DocAnalyst: ingesting PDF...", flush=True)
    pdf_path = state.get("pdf_path", "")
    evidences: Dict[str, List[Evidence]] = {"doc": []}

    if not pdf_path or not Path(pdf_path).exists():
        ev = Evidence(goal="pdf_ingest", found=False, location=pdf_path or "", rationale="PDF not found", confidence=0.0)
        return {"evidences": {"doc": [ev], "theoretical_depth": [ev], "report_accuracy": [ev]}}

    chunks, err = ingest_pdf(pdf_path)
    if err:
        ev = Evidence(goal="pdf_ingest", found=False, location=pdf_path, rationale=err, confidence=0.0)
        return {"evidences": {"doc": [ev], "theoretical_depth": [ev], "report_accuracy": [ev]}}

    # Theoretical depth - keyword search
    keywords = ["Dialectical Synthesis", "Fan-In", "Fan-Out", "Metacognition", "State Synchronization"]
    found_contexts = []
    for kw in keywords:
        hits = query_pdf_chunks(chunks, kw)
        if hits:
            found_contexts.extend(hits[:2])

    has_depth = len(found_contexts) >= 2
    th_ev = Evidence(
        goal="theoretical_depth",
        found=has_depth,
        location=pdf_path,
        rationale=f"Keywords found in {len(found_contexts)} chunks",
        confidence=0.8 if has_depth else 0.4,
        content="\n---\n".join(found_contexts[:5])[:2000] if found_contexts else None,
    )
    acc_ev = Evidence(
        goal="report_accuracy",
        found=True,
        location=pdf_path,
        rationale="PDF ingested; cross-ref requires repo evidence from RepoInvestigator",
        confidence=0.6,
        content="\n".join(chunks[:3])[:1500] if chunks else None,
    )
    # Key by dimension for ChiefJustice
    return {"evidences": {"doc": [th_ev, acc_ev], "theoretical_depth": [th_ev], "report_accuracy": [acc_ev]}}


def VisionInspectorNode(state: AgentState) -> Dict[str, Any]:
    """
    The Diagram Detective. Extracts images from PDF.
    Optional: pass to vision model for diagram classification.
    """
    print("  VisionInspector: checking PDF images...", flush=True)
    pdf_path = state.get("pdf_path", "")
    evidences: Dict[str, List[Evidence]] = {"vision": []}

    if not pdf_path or not Path(pdf_path).exists():
        ev = Evidence(goal="swarm_visual", found=False, location=pdf_path or "", rationale="PDF not found", confidence=0.0)
        return {"evidences": {"vision": [ev], "swarm_visual": [ev]}}

    images = extract_images_from_pdf(pdf_path)
    if not images:
        ev = Evidence(goal="swarm_visual", found=False, location=pdf_path, rationale="No images in PDF", confidence=0.5)
        return {"evidences": {"vision": [ev], "swarm_visual": [ev]}}

    ev = Evidence(
        goal="swarm_visual",
        found=True,
        location=pdf_path,
        rationale=f"Extracted {len(images)} image(s) from PDF",
        confidence=0.7,
        content=f"{len(images)} images available for classification",
    )
    return {"evidences": {"vision": [ev], "swarm_visual": [ev]}}


def EvidenceAggregatorNode(state: AgentState) -> Dict[str, Any]:
    """
    Fan-in synchronization. All detective evidences are already merged via
    operator.ior. This node acts as a sync point before Judges; no mutation.
    """
    return {}
