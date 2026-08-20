#!/usr/bin/env python3
"""
Cross-model verification CLI — sends Top-5 claims to a second model for independent review.

Uses the OpenAI API (GPT-4o by default) as the cross-model provider.
Requires OPENAI_API_KEY environment variable to be set.
CROSS_MODEL_ENABLED=true must also be set to activate.

This is an OPTIONAL enhancement. If the API key is not set or the call fails,
the system skips cross-model verification gracefully and proceeds with main model results only.

Usage:
    python cross_model_verify.py \
        --input manuscript.txt \
        --claims claims.json \
        --provider openai \
        --model gpt-4o \
        --output cross_model_report.json

Dependencies: openai (pip install openai)
"""

import argparse
import json
import os
import sys
from datetime import datetime


def parse_args():
    parser = argparse.ArgumentParser(description="Cross-model verification")
    parser.add_argument("--input", required=True, help="Path to manuscript text file")
    parser.add_argument("--claims", required=True, help="Path to claims JSON file (Top-5 claims)")
    parser.add_argument("--provider", default="openai", choices=["openai"], help="Cross-model provider")
    parser.add_argument("--model", default="gpt-4o", help="Model name (default: gpt-4o)")
    parser.add_argument("--output", required=True, help="Output JSON file path")
    return parser.parse_args()


def load_claims(claims_path):
    """Load Top-5 claims from JSON file.

    Expected format:
    [
        {"id": 1, "claim": "...", "citation": "...", "context": "..."},
        ...
    ]
    """
    if not os.path.exists(claims_path):
        print(f"WARNING: Claims file not found: {claims_path}")
        return []
    try:
        with open(claims_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"WARNING: Claims file contains invalid JSON: {e}")
        return []


def load_manuscript(text_path):
    """Load manuscript text."""
    if not os.path.exists(text_path):
        print(f"WARNING: Manuscript not found: {text_path}")
        return ""
    with open(text_path, "r", encoding="utf-8") as f:
        return f.read()


def verify_with_openai(claims, manuscript, model="gpt-4o"):
    """Send Top-5 claims to OpenAI for independent review."""
    try:
        from openai import OpenAI
    except ImportError:
        print("WARNING: openai package not installed. Install with: pip install openai")
        return None

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("WARNING: OPENAI_API_KEY not set. Skipping cross-model verification.")
        return None

    client = OpenAI(api_key=api_key)
    results = []

    for claim in claims:
        claim_id = claim.get("id", 0)
        claim_text = claim.get("claim", "")
        citation = claim.get("citation", "")
        context = claim.get("context", "")

        prompt = (
            "You are an independent scientific reviewer. You are reviewing a manuscript's claims "
            "and their supporting citations. For each claim, determine:\n"
            "1. Does the citation actually support the claim? (SUPPORTS / PARTIALLY / DOES NOT SUPPORT)\n"
            "2. Is the claim factually accurate based on the manuscript's own data? (ACCURATE / PARTIALLY / INACCURATE)\n"
            "3. Is the logic consistent? (CONSISTENT / MINOR_ISSUE / MAJOR_ISSUE)\n\n"
            f"## Manuscript context\n{context}\n\n"
            f"## Claim\n{claim_text}\n\n"
            f"## Cited reference\n{citation}\n\n"
            "## Response format (JSON)\n"
            "{\"verdict\": \"SUPPORTS|PARTIALLY|DOES_NOT_SUPPORT\", "
            "\"factual_accuracy\": \"ACCURATE|PARTIALLY|INACCURATE\", "
            "\"logic_consistency\": \"CONSISTENT|MINOR_ISSUE|MAJOR_ISSUE\", "
            "\"confidence\": <1-10>, "
            "\"rationale\": \"<brief explanation>\"}"
        )

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=500,
            )
            result = json.loads(response.choices[0].message.content)
            result["claim_id"] = claim_id
            result["claim_text"] = claim_text
            results.append(result)
            print(f"  Claim {claim_id}: {result.get('verdict', 'ERROR')} (confidence: {result.get('confidence', 'N/A')}/10)")
        except Exception as e:
            print(f"  ERROR verifying claim {claim_id}: {e}")
            results.append({
                "claim_id": claim_id,
                "claim_text": claim_text,
                "error": str(e),
            })

    return results


def main():
    args = parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY not set. Cross-model verification skipped.")
        print("Set OPENAI_API_KEY=sk-... to enable.")
        report = {
            "status": "SKIPPED",
            "reason": "OPENAI_API_KEY not set",
            "provider": args.provider,
            "model": args.model,
            "generated_at": datetime.now().isoformat(),
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"Wrote skip report to {args.output}")
        return

    print(f"Loading claims from: {args.claims}")
    claims = load_claims(args.claims)
    if not claims:
        print("WARNING: No claims loaded. Generating empty report.")
        report = {"status": "EMPTY", "reason": "No claims provided", "results": []}
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        return

    manuscript = load_manuscript(args.input)

    print(f"Verifying {len(claims)} claims with {args.provider} ({args.model})...")
    results = verify_with_openai(claims, manuscript, args.model)

    if results is None:
        report = {"status": "SKIPPED", "reason": "OpenAI API call failed", "results": []}
    else:
        # Count disagreements with main model
        disagreements = sum(1 for r in results if r.get("verdict") == "DOES_NOT_SUPPORT")
        total = len(results)
        disagreement_rate = disagreements / total if total > 0 else 0

        report = {
            "status": "COMPLETED",
            "provider": args.provider,
            "model": args.model,
            "total_claims": total,
            "disagreement_count": disagreements,
            "disagreement_rate": round(disagreement_rate, 2),
            "cross_model_disagreement_flag": disagreement_rate > 0.3,
            "results": results,
            "generated_at": datetime.now().isoformat(),
        }

        if disagreement_rate > 0.3:
            print(f"  [CROSS-MODEL-DISAGREEMENT] Disagreement rate: {disagreement_rate:.0%} (>30%)")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Cross-model verification report written to: {args.output}")
    print(f"Status: {report['status']}")


if __name__ == "__main__":
    main()
