"""CLI entry point for the Automaton Auditor."""

import argparse

from dotenv import load_dotenv

load_dotenv()
from pathlib import Path

from src.graph import run_audit
from src.nodes.justice import report_to_markdown


def main():
    parser = argparse.ArgumentParser(description="Automaton Auditor - Digital Courtroom")
    parser.add_argument("repo_url", help="GitHub repository URL to audit")
    parser.add_argument("pdf_path", help="Path to architectural PDF report")
    parser.add_argument("-o", "--output", default="audit/report.md", help="Output Markdown path")
    args = parser.parse_args()

    pdf = Path(args.pdf_path)
    if not pdf.exists():
        print(f"Error: PDF not found: {args.pdf_path}")
        return 1

    print(f"Auditing {args.repo_url} with report {args.pdf_path}...")
    result = run_audit(args.repo_url, str(pdf))
    report = result.get("final_report")
    if not report:
        print("Error: No final report produced.")
        return 1

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    md = report_to_markdown(report)
    out.write_text(md, encoding="utf-8")
    print(f"Report written to {out}")
    print(f"Overall score: {report.overall_score}/5")
    return 0


if __name__ == "__main__":
    exit(main())
