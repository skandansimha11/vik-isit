"""Ministry of Skill Development & Labour - Tier-B connector.

KPIs:
  * youth_neet_rate            - % of 15-29s not in employment, education or training
  * apprenticeship_utilisation - apprenticeship budget spent / allocated * 100
  * job_creation               - EPFO net new subscribers, lakh/year (proxy)
"""

from __future__ import annotations

from app.connectors.tier_b.base import TierBConnector


class SkillConnector(TierBConnector):
    ministry_code = "SKILL"
    dataset_files = {
        "neet": "skill/neet.csv",
        "apprenticeship": "skill/apprenticeship.csv",
        "jobs": "skill/jobs.csv",
    }
    valid_ranges = {
        "Youth NEET Rate": (5.0, 45.0),
        "Apprenticeship Utilisation": (0.0, 110.0),
        "Job Creation": (0.0, 250.0),
    }

    def _compute_youth_neet_rate(self, spec):
        return self._simple_series(
            spec,
            "neet",
            "neet_15_29_pct",
            formula="PLFS (usual status): persons 15-29 not in employment, education or training / population 15-29 * 100 ; secondary = female 15-29 NEET",
            secondary_col="female_neet_15_29_pct",
        )

    def _compute_apprenticeship_utilisation(self, spec):
        return self._simple_series(
            spec,
            "apprenticeship",
            "budget_utilisation_pct",
            formula="apprenticeship scheme actual expenditure / budget allocation * 100 (NAPS + NATS)",
            secondary_col="budget_allocated_rs_cr",
        )

    def _compute_job_creation(self, spec):
        return self._simple_series(
            spec,
            "jobs",
            "epfo_net_additions_lakh",
            formula="EPFO net new subscribers in the year (new joiners + rejoiners - exits), lakh ; secondary = share aged 18-28",
            secondary_col="age_18_28_share_pct",
        )


def get_skill_connector() -> SkillConnector:
    return SkillConnector()
