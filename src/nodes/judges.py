"""Judicial layer - Prosecutor, Defense, Tech Lead with distinct personas."""

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Literal

from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from src.state import AgentState, JudicialOpinion


def _load_rubric() -> Dict[str, Any]:
    with open(Path(__file__).resolve().parents[2] / "rubric.json") as f:
        return json.load(f)


def _get_llm():
    """Get LLM - Ollama (local, free) or Gemini (cloud)."""
    provider = (os.getenv("LLM_PROVIDER") or "ollama").lower()
    model = os.getenv("AUDITOR_LLM_MODEL", "llama3.2")

    if provider == "gemini":
        api_key = os.getenv("GOOGLE_API_KEY")
        return ChatGoogleGenerativeAI(
            model=model or "gemini-2.0-flash",
            google_api_key=api_key,
            temperature=0.3,
            request_options={"timeout": 300},
        )
    # Default: Ollama (local, no API key needed). Timeout so audit doesn't hang.
    return ChatOllama(
        model=model,
        temperature=0.3,
        client_kwargs={"timeout": 300.0},
    )


class JudgeOpinionsBatch(BaseModel):
    """Batch of JudicialOpinion for one judge across all criteria."""

    opinions: List[JudicialOpinion] = Field(description="One opinion per rubric criterion")


def _format_evidence_for_prompt(evidences: Dict[str, List]) -> str:
    out = []
    for key, items in (evidences or {}).items():
        if not isinstance(items, list):
            continue
        for it in items:
            if hasattr(it, "model_dump"):
                d = it.model_dump()
            elif isinstance(it, dict):
                d = it
            else:
                continue
            out.append(f"[{key}] goal={d.get('goal','')} found={d.get('found')} confidence={d.get('confidence')} rationale={d.get('rationale','')[:200]} content={str(d.get('content',''))[:300]}")
    return "\n".join(out) if out else "No evidence available."


PROSECUTOR_SYSTEM = """You are the PROSECUTOR in a Digital Courtroom. Your core philosophy: "Trust No One. Assume Vibe Coding."

Your job: Scrutinize the forensic evidence for gaps, security flaws, and laziness. Be adversarial.

RULES (Statute of Orchestration):
- If the StateGraph defines a purely linear flow instead of parallel fan-out: Charge "Orchestration Fraud." Max Score = 1 for LangGraph Architecture.
- If Judge nodes return freeform text without Pydantic validation: Charge "Hallucination Liability." Max Score = 2 for Judicial Nuance.
- If you identify raw os.system, unsanitized inputs, or security negligence: Argue for Score 1-2.
- Look for bypassed structure, missing reducers, and half-implemented features.

For EACH rubric criterion, output a JudicialOpinion with:
- judge: "Prosecutor"
- criterion_id: the dimension id
- score: 1-5 (be harsh; prefer 1-2 when evidence is weak)
- argument: Your adversarial reasoning, citing specific gaps
- cited_evidence: List of evidence snippets or identifiers you're citing

Be strict. Assume the worst. Your role is to find flaws."""


DEFENSE_SYSTEM = """You are the DEFENSE ATTORNEY in a Digital Courtroom. Your core philosophy: "Reward Effort and Intent. Look for the Spirit of the Law."

Your job: Highlight creative workarounds, deep thought, and effort even when implementation is imperfect.

RULES (Statute of Effort):
- If the graph fails to compile due to minor edge error but AST parsing is sophisticated: Argue "The engineer achieved deep code comprehension but tripped on framework syntax." Request Score 3 for Forensic Accuracy.
- If Chief Justice synthesis uses an LLM but Judge personas are distinct and disagree: Argue "Role separation yielded true dialectical tension." Request partial credit (Score 3-4) for Judicial Nuance.
- Look at Git History evidence: If commits tell a story of iteration and struggle, argue for "Engineering Process" credit.
- Reward intent and architectural understanding over perfect syntax.

For EACH rubric criterion, output a JudicialOpinion with:
- judge: "Defense"
- criterion_id: the dimension id
- score: 1-5 (be generous; prefer 3-5 when effort is visible)
- argument: Your optimistic reasoning
- cited_evidence: List of evidence that supports the defendant

Be charitable. Look for the spirit of the law."""


TECH_LEAD_SYSTEM = """You are the TECH LEAD in a Digital Courtroom. Your core philosophy: "Does it actually work? Is it maintainable?"

Your job: Evaluate architectural soundness, code cleanliness, and practical viability. You are the tie-breaker.

RULES (Statute of Engineering):
- If state uses plain dicts instead of Pydantic: Ruling "Technical Debt." Score = 3.
- If git clone uses os.system without sandboxing: Ruling "Security Negligence." Override effort points.
- If the Tech Lead confirms the architecture is modular and workable: This carries HIGHEST weight for Architecture criterion.
- Ignore "vibe" and "struggle." Focus on artifacts. Is operator.add reducer used? Are tool calls safe?

For EACH rubric criterion, output a JudicialOpinion with:
- judge: "TechLead"
- criterion_id: the dimension id
- score: 1-5 (be realistic; 1, 3, or 5 based on technical merit)
- argument: Your pragmatic reasoning and remediation advice
- cited_evidence: List of evidence you're basing your assessment on

Be pragmatic. You are the tie-breaker between Prosecutor and Defense."""


def _run_judge(role: Literal["Prosecutor", "Defense", "TechLead"], state: Dict[str, Any]) -> List[JudicialOpinion]:
    print(f"  Running judge: {role}...", flush=True)
    rubric = _load_rubric()
    dimensions = rubric.get("dimensions", [])
    evidences = state.get("evidences") or {}
    ev_text = _format_evidence_for_prompt(evidences)

    systems = {
        "Prosecutor": PROSECUTOR_SYSTEM,
        "Defense": DEFENSE_SYSTEM,
        "TechLead": TECH_LEAD_SYSTEM,
    }
    system = systems[role]

    prompt = f"""Evidence from Detectives:

{ev_text}

Rubric dimensions to evaluate:
{json.dumps([{"id": d["id"], "name": d["name"], "success_pattern": d.get("success_pattern",""), "failure_pattern": d.get("failure_pattern","")} for d in dimensions], indent=2)}

Produce ONE JudicialOpinion per dimension. For each, set judge="{role}", criterion_id to the dimension id, score (1-5), argument, and cited_evidence."""

    llm = _get_llm()
    json_schema = json.dumps(JudgeOpinionsBatch.model_json_schema(), indent=2)

    def _invoke_structured() -> List[JudicialOpinion]:
        try:
            structured_llm = llm.with_structured_output(JudgeOpinionsBatch)
            result = structured_llm.invoke(
                [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
            )
        except NotImplementedError:
            # Ollama may not support with_structured_output; fallback to JSON parse
            json_prompt = f"{prompt}\n\nRespond with valid JSON matching this schema:\n{json_schema}"
            raw = llm.invoke(
                [{"role": "system", "content": system}, {"role": "user", "content": json_prompt}]
            )
            text = getattr(raw, "content", str(raw))
            # Extract JSON block if wrapped in markdown
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text) or re.search(r"(\{[\s\S]*\})", text)
            parsed = JudgeOpinionsBatch.model_validate_json(match.group(1) if match else text)
            result = parsed
        if isinstance(result, JudgeOpinionsBatch):
            return result.opinions
        return getattr(result, "opinions", [])

    def _short_error(err: Exception) -> str:
        s = str(err).lower()
        if "429" in s or "quota" in s or "resource_exhausted" in s:
            return "API quota exceeded. Use Ollama (LLM_PROVIDER=ollama) for unlimited local runs."
        if "404" in s or "not_found" in s:
            return "Model not found. For Ollama: run 'ollama pull <model>'. For Gemini: set AUDITOR_LLM_MODEL."
        if "401" in s or "unauthorized" in s or "invalid" in s:
            return "Invalid or missing GOOGLE_API_KEY. Or use Ollama: LLM_PROVIDER=ollama"
        if "connection" in s or "refused" in s or "connect" in s:
            return "Ollama not running. Start with: ollama serve (then ollama pull llama3.2)"
        if "validation" in s or "no json" in s:
            return "Model returned invalid JSON. Try llama3.2 or mistral: ollama pull llama3.2"
        return "LLM call failed. See console for details."

    last_err = None
    for attempt in range(3):
        try:
            if attempt > 0:
                time.sleep(2**attempt)  # 2s, 4s backoff
            opinions = _invoke_structured()
            for o in opinions:
                if not getattr(o, "judge", None):
                    o.judge = role  # type: ignore
            return opinions
        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            if "429" in err_str or "resource_exhausted" in err_str:
                continue  # Retry on quota
            break  # Don't retry other errors

    return [
        JudicialOpinion(judge=role, criterion_id=d["id"], score=3, argument=_short_error(last_err or Exception()), cited_evidence=[])
        for d in dimensions
    ]


def ProsecutorNode(state: AgentState) -> Dict[str, Any]:
    """The Critical Lens. Harsh scorer."""
    opinions = _run_judge("Prosecutor", state)
    return {"opinions": opinions}


def DefenseNode(state: AgentState) -> Dict[str, Any]:
    """The Optimistic Lens. Generous scorer."""
    opinions = _run_judge("Defense", state)
    return {"opinions": opinions}


def TechLeadNode(state: AgentState) -> Dict[str, Any]:
    """The Pragmatic Lens. Tie-breaker."""
    opinions = _run_judge("TechLead", state)
    return {"opinions": opinions}
