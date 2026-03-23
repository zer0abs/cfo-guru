"""Business health score logic for CFO AI."""

from dataclasses import dataclass


@dataclass(frozen=True)
class HealthScoreResult:
    """Final business health score and component breakdown."""

    score: int
    interpretation: str
    dimension_scores: dict[str, int]
    component_scores: dict[str, int]


# The framework below is intentionally simple and explainable.
# Each dimension is scored from 0-100 using a small number of visible KPIs.
# The overall score is just a weighted average of the four dimension scores.
# This keeps the model editable and avoids hidden or black-box math.
DIMENSION_WEIGHTS = {
    "profitability": 30,
    "liquidity": 25,
    "growth_efficiency": 25,
    "operational_efficiency": 20,
}


def calculate_business_health_score(kpis: dict[str, float | None]) -> HealthScoreResult:
    """Calculate a 0-100 health score from a KPI dictionary."""
    component_scores = {
        "revenue_growth": _score_revenue_growth(kpis.get("revenue_growth")),
        "gross_margin": _score_gross_margin(kpis.get("gross_margin")),
        "net_margin": _score_net_margin(kpis.get("net_margin")),
        "burn_rate": _score_burn_rate(kpis.get("burn_rate"), kpis.get("revenue")),
        "runway": _score_runway(kpis.get("runway")),
        "cac_ltv": _score_cac_ltv(kpis.get("ltv"), kpis.get("cac")),
        "aov": _score_aov(kpis.get("aov")),
        "return_rate": _score_return_rate(kpis.get("return_rate")),
        "inventory_turnover": _score_inventory_turnover(kpis.get("inventory_turnover")),
    }

    # Each dimension is a plain average of its component KPI scores.
    # That makes it obvious how a weak KPI pulls down the dimension.
    dimension_scores = {
        "profitability": _average_scores(
            component_scores["gross_margin"],
            component_scores["net_margin"],
        ),
        "liquidity": _average_scores(
            component_scores["burn_rate"],
            component_scores["runway"],
        ),
        "growth_efficiency": _average_scores(
            component_scores["revenue_growth"],
            component_scores["cac_ltv"],
            component_scores["aov"],
        ),
        "operational_efficiency": _average_scores(
            component_scores["inventory_turnover"],
            component_scores["return_rate"],
        ),
    }

    weighted_score = 0.0
    for dimension_name, weight in DIMENSION_WEIGHTS.items():
        weighted_score += (dimension_scores[dimension_name] / 100) * weight

    final_score = int(round(weighted_score))
    return HealthScoreResult(
        score=final_score,
        interpretation=_interpret_score(final_score),
        dimension_scores=dimension_scores,
        component_scores=component_scores,
    )


def _score_revenue_growth(value: float | None) -> int:
    """Score revenue growth on a practical SMB scale."""
    if value is None:
        return 50
    if value >= 0.20:
        return 100
    if value >= 0.10:
        return 85
    if value >= 0.05:
        return 70
    if value >= 0.0:
        return 55
    if value >= -0.05:
        return 35
    return 15


def _score_gross_margin(value: float | None) -> int:
    """Score gross margin quality."""
    if value is None:
        return 40
    if value >= 0.60:
        return 100
    if value >= 0.45:
        return 85
    if value >= 0.30:
        return 65
    if value >= 0.20:
        return 40
    return 15


def _score_net_margin(value: float | None) -> int:
    """Score bottom-line profitability."""
    if value is None:
        return 40
    if value >= 0.20:
        return 100
    if value >= 0.12:
        return 85
    if value >= 0.05:
        return 70
    if value >= 0.0:
        return 55
    if value >= -0.10:
        return 30
    return 10


def _score_burn_rate(burn_rate: float | None, revenue: float | None) -> int:
    """Score cash burn relative to revenue size."""
    if burn_rate is None or revenue is None:
        return 50
    if burn_rate <= 0:
        return 100

    burn_ratio = burn_rate / revenue if revenue > 0 else 1.0
    if burn_ratio <= 0.05:
        return 85
    if burn_ratio <= 0.10:
        return 65
    if burn_ratio <= 0.20:
        return 40
    return 15


def _score_runway(value: float | None) -> int:
    """Score liquidity runway in months."""
    if value is None:
        return 90
    if value >= 12:
        return 100
    if value >= 9:
        return 85
    if value >= 6:
        return 65
    if value >= 3:
        return 35
    return 10


def _score_cac_ltv(ltv: float | None, cac: float | None) -> int:
    """Score e-commerce unit economics using LTV to CAC ratio."""
    if ltv is None or cac is None or cac <= 0:
        return 40
    ratio = ltv / cac
    if ratio >= 4.0:
        return 100
    if ratio >= 3.0:
        return 85
    if ratio >= 2.0:
        return 60
    if ratio >= 1.0:
        return 30
    return 10


def _score_aov(value: float | None) -> int:
    """Score average order value using broad e-commerce-friendly ranges."""
    if value is None:
        return 50
    if value >= 100:
        return 100
    if value >= 75:
        return 80
    if value >= 50:
        return 60
    if value >= 35:
        return 40
    return 20


def _score_return_rate(value: float | None) -> int:
    """Score return or refund rate where lower is better."""
    if value is None:
        return 50
    if value <= 0.03:
        return 100
    if value <= 0.06:
        return 85
    if value <= 0.10:
        return 65
    if value <= 0.15:
        return 40
    return 15


def _score_inventory_turnover(value: float | None) -> int:
    """Score inventory efficiency with broad bands suitable for e-commerce brands."""
    if value is None:
        return 50
    if value >= 8.0:
        return 100
    if value >= 5.0:
        return 80
    if value >= 3.0:
        return 60
    if value >= 1.5:
        return 35
    return 15


def _interpret_score(score: int) -> str:
    """Map numeric scores to business health interpretation labels."""
    if score >= 80:
        return "Strong"
    if score >= 60:
        return "Moderate"
    return "At Risk"


def _average_scores(*scores: int) -> int:
    """Average component scores for a dimension and return an integer score."""
    return int(round(sum(scores) / len(scores)))
