from backend.config import (
    VERDICT_APPROVE,
    VERDICT_REVIEW,
    VERDICT_REJECT,
    RISK_APPROVE_MAX,
    RISK_REVIEW_MAX,
)


REQUIRED_KEYS = {"invoice", "checks", "risk_score", "verdict", "summary"}


def evaluate(result: dict) -> dict:
    warnings = []

    missing = REQUIRED_KEYS - set(result.keys())
    if missing:
        warnings.append(f"Missing keys: {sorted(missing)}")

    checks = result.get("checks", [])
    if not checks:
        warnings.append("No checks returned by validator")
    elif not isinstance(checks, list):
        warnings.append("'checks' is not a list")

    score = result.get("risk_score")
    verdict = result.get("verdict")

    if not isinstance(score, int) or not (0 <= score <= 100):
        warnings.append(f"Invalid risk_score: {score}")

    expected_verdict = _verdict_for_score(score) if isinstance(score, int) else None
    if expected_verdict and verdict != expected_verdict:
        warnings.append(
            f"Verdict/score mismatch: verdict={verdict}, expected={expected_verdict}"
        )

    high_fail_count = sum(
        1 for c in checks
        if isinstance(c, dict)
        and c.get("status") == "fail"
        and c.get("severity") == "high"
    )
    if high_fail_count >= 3:
        warnings.append(f"{high_fail_count} high-severity rules failed")

    summary = result.get("summary")
    if not summary or not isinstance(summary, str) or len(summary.strip()) < 10:
        warnings.append("Summary is missing or too short")

    confidence = _compute_confidence(warnings, checks)

    final_verdict = verdict
    if warnings and verdict == VERDICT_APPROVE:
        final_verdict = VERDICT_REVIEW
    elif "Missing keys" in " ".join(warnings) or confidence < 0.3:
        final_verdict = VERDICT_REVIEW if verdict != VERDICT_REJECT else VERDICT_REJECT

    return {
        "passed": len(warnings) == 0,
        "confidence": confidence,
        "warnings": warnings,
        "final_verdict": final_verdict,
    }


def _verdict_for_score(score: int) -> str:
    if score <= RISK_APPROVE_MAX:
        return VERDICT_APPROVE
    if score <= RISK_REVIEW_MAX:
        return VERDICT_REVIEW
    return VERDICT_REJECT


def _compute_confidence(warnings: list, checks: list) -> float:
    base = 1.0
    base -= 0.15 * len(warnings)
    if not checks:
        base -= 0.3
    return max(0.0, round(base, 2))