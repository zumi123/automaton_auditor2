"""Forensic tools for repository analysis - RepoInvestigator capabilities."""

import ast
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List

from src.state import Evidence


def _sanitize_url(url: str) -> str:
    """Basic URL sanitization to prevent injection."""
    if not url or not isinstance(url, str):
        raise ValueError("Repository URL must be a non-empty string")
    # Reject URLs that could be used for command injection
    dangerous = [";", "|", "&", "$", "`", "\n", "\r"]
    for char in dangerous:
        if char in url:
            raise ValueError(f"Invalid character in repository URL: {repr(char)}")
    # Must look like a git URL
    if not (url.startswith("https://") or url.startswith("http://") or "@" in url or url.endswith(".git")):
        raise ValueError("Repository URL must be a valid git URL")
    return url.strip()


def clone_repo(repo_url: str) -> tuple[str, List[Evidence]]:
    """
    Clone a repository into a sandboxed temporary directory.
    Uses tempfile.TemporaryDirectory and subprocess with proper error handling.
    Returns (clone_path, evidence_list). Caller is responsible for cleanup.
    """
    evidence_list: List[Evidence] = []
    url = _sanitize_url(repo_url)

    try:
        with tempfile.TemporaryDirectory(prefix="auditor_clone_") as tmpdir:
            result = subprocess.run(
                ["git", "clone", "--depth", "100", url, tmpdir],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=Path(tmpdir).parent,
            )

            if result.returncode != 0:
                stderr = result.stderr or "Unknown error"
                if "Authentication failed" in stderr or "Could not read" in stderr:
                    evidence_list.append(
                        Evidence(
                            goal="git_sandbox_clone",
                            found=False,
                            location=url,
                            rationale="Git authentication or access error",
                            confidence=0.0,
                            content=stderr[:500],
                        )
                    )
                else:
                    evidence_list.append(
                        Evidence(
                            goal="git_sandbox_clone",
                            found=False,
                            location=url,
                            rationale=f"Clone failed: {stderr[:200]}",
                            confidence=0.0,
                            content=stderr[:500],
                        )
                    )
                return ("", evidence_list)

            # Success - we need to return the path, but tmpdir will be deleted
            # So we clone again to a non-temp path or return a path the caller must manage
            pass

        # Re-clone to a persistent temp dir for the caller to use
        persist_dir = tempfile.mkdtemp(prefix="auditor_repo_")
        result2 = subprocess.run(
            ["git", "clone", "--depth", "100", url, persist_dir],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result2.returncode != 0:
            evidence_list.append(
                Evidence(
                    goal="git_sandbox_clone",
                    found=False,
                    location=url,
                    rationale="Clone to persistent dir failed",
                    confidence=0.0,
                )
            )
            return ("", evidence_list)

        evidence_list.append(
            Evidence(
                goal="git_sandbox_clone",
                found=True,
                location=persist_dir,
                rationale="Repository cloned successfully in temp directory",
                confidence=1.0,
                content=persist_dir,
            )
        )
        return (persist_dir, evidence_list)

    except subprocess.TimeoutExpired:
        evidence_list.append(
            Evidence(
                goal="git_sandbox_clone",
                found=False,
                location=url,
                rationale="Clone timed out",
                confidence=0.0,
            )
        )
        return ("", evidence_list)
    except Exception as e:
        evidence_list.append(
            Evidence(
                goal="git_sandbox_clone",
                found=False,
                location=url,
                rationale=str(e)[:200],
                confidence=0.0,
            )
        )
        return ("", evidence_list)


def extract_git_history(path: str) -> List[Evidence]:
    """
    Run git log --oneline --reverse and extract commit metadata.
    Returns Evidence objects for git forensic analysis.
    """
    evidence_list: List[Evidence] = []
    p = Path(path)
    if not p.exists() or not (p / ".git").exists():
        evidence_list.append(
            Evidence(
                goal="git_forensic_analysis",
                found=False,
                location=path,
                rationale="Not a git repository",
                confidence=0.0,
            )
        )
        return evidence_list

    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--reverse", "--format=%h %s %ci"],
            capture_output=True,
            text=True,
            cwd=path,
            timeout=30,
        )
        if result.returncode != 0:
            evidence_list.append(
                Evidence(
                    goal="git_forensic_analysis",
                    found=False,
                    location=path,
                    rationale=result.stderr or "git log failed",
                    confidence=0.0,
                )
            )
            return evidence_list

        lines = [l for l in result.stdout.strip().split("\n") if l]
        commit_count = len(lines)

        # Check patterns
        is_atomic = commit_count > 3
        has_progression = False
        if lines:
            msgs_lower = " ".join(line.split(maxsplit=2)[-1].lower() for line in lines)
            has_progression = any(
                k in msgs_lower
                for k in ["setup", "init", "graph", "node", "tool", "detective", "judge"]
            )

        success = is_atomic and (has_progression or commit_count >= 5)
        evidence_list.append(
            Evidence(
                goal="git_forensic_analysis",
                found=success,
                location=path,
                rationale=f"Commits: {commit_count}. Atomic: {is_atomic}. Progression hints: {has_progression}",
                confidence=0.9 if success else 0.5,
                content=result.stdout[:2000],
            )
        )
        return evidence_list

    except Exception as e:
        evidence_list.append(
            Evidence(
                goal="git_forensic_analysis",
                found=False,
                location=path,
                rationale=str(e)[:200],
                confidence=0.0,
            )
        )
        return evidence_list


def analyze_graph_structure(path: str) -> List[Evidence]:
    """
    Use AST parsing to verify StateGraph, add_edge, add_conditional_edges,
    and parallelism (fan-out/fan-in).
    """
    evidence_list: List[Evidence] = []
    base = Path(path)
    if not base.exists():
        evidence_list.append(
            Evidence(
                goal="graph_orchestration",
                found=False,
                location=path,
                rationale="Path does not exist",
                confidence=0.0,
            )
        )
        return evidence_list

    # Find graph definition
    graph_files = list(base.rglob("**/graph.py")) + list(base.rglob("**/*graph*.py"))
    graph_py = [f for f in graph_files if "graph" in f.name.lower()][:3]

    if not graph_py:
        evidence_list.append(
            Evidence(
                goal="graph_orchestration",
                found=False,
                location=str(base),
                rationale="No graph.py found",
                confidence=0.0,
            )
        )
        return evidence_list

    for gf in graph_py:
        try:
            content = gf.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content)

            has_state_graph = False
            add_edge_calls: List[ast.Call] = []
            add_conditional_calls: List[ast.Call] = []

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        name = node.func.attr
                        if "StateGraph" in ast.unparse(node.func) if hasattr(ast, "unparse") else "StateGraph" in content:
                            # Check for StateGraph instantiation
                            try:
                                src = ast.get_source_segment(content, node)
                                if src and "StateGraph" in src:
                                    has_state_graph = True
                            except Exception:
                                pass
                        if name == "add_edge":
                            add_edge_calls.append(node)
                        elif name == "add_conditional_edges":
                            add_conditional_calls.append(node)

            # Heuristic: parallel fan-out usually has multiple add_edge from same source
            edge_count = len(add_edge_calls) + len(add_conditional_calls)
            has_parallel = edge_count >= 4  # Detectives + Judges + aggregation

            # Check for EvidenceAggregator or similar
            has_aggregator = "EvidenceAggregator" in content or "evidence_aggregat" in content.lower()

            found = has_state_graph and has_parallel
            evidence_list.append(
                Evidence(
                    goal="graph_orchestration",
                    found=found,
                    location=str(gf),
                    rationale=f"StateGraph: {has_state_graph}, edges: {edge_count}, aggregator: {has_aggregator}",
                    confidence=0.85 if found else 0.4,
                    content=content[:1500],
                )
            )

        except SyntaxError as e:
            evidence_list.append(
                Evidence(
                    goal="graph_orchestration",
                    found=False,
                    location=str(gf),
                    rationale=f"Syntax error: {e}",
                    confidence=0.0,
                )
            )

    # State management check
    state_files = list(base.rglob("**/state.py"))
    for sf in state_files[:2]:
        try:
            content = sf.read_text(encoding="utf-8", errors="replace")
            has_base_model = "BaseModel" in content
            has_typed_dict = "TypedDict" in content
            has_operator = "operator.add" in content or "operator.ior" in content
            has_evidence = "Evidence" in content
            has_judicial = "JudicialOpinion" in content

            state_ok = (has_base_model or has_typed_dict) and (has_evidence or has_judicial)
            evidence_list.append(
                Evidence(
                    goal="state_management_rigor",
                    found=state_ok,
                    location=str(sf),
                    rationale=f"BaseModel/TypedDict: {has_base_model or has_typed_dict}, reducers: {has_operator}, Evidence/Judicial: {has_evidence and has_judicial}",
                    confidence=0.9 if state_ok else 0.3,
                    content=content[:1200],
                )
            )
        except Exception:
            pass

    # Safe tool engineering check
    tools_dir = base / "src" / "tools"
    if tools_dir.exists():
        for tf in tools_dir.glob("*.py"):
            try:
                content = tf.read_text(encoding="utf-8", errors="replace")
                has_tempfile = "TemporaryDirectory" in content or "mkdtemp" in content
                has_os_system = "os.system" in content
                uses_subprocess = "subprocess" in content
                evidence_list.append(
                    Evidence(
                        goal="safe_tool_engineering",
                        found=has_tempfile and not has_os_system and uses_subprocess,
                        location=str(tf),
                        rationale=f"Sandbox: {has_tempfile}, no os.system: {not has_os_system}, subprocess: {uses_subprocess}",
                        confidence=0.9 if (has_tempfile and not has_os_system) else 0.3,
                        content=content[:800],
                    )
                )
            except Exception:
                pass

    return evidence_list
