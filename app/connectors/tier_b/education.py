"""Ministry of Education — Tier-B connector.

KPIs:
  * learning_outcomes    — % of Class 3 children who can read a Class 2 text (ASER)
  * exam_integrity       — major paper leaks / cancellations per year (proxy)
  * enrollment_quality   — senior-secondary Gross Enrolment Ratio (UDISE+)
"""

from __future__ import annotations

from app.connectors.tier_b.base import TierBConnector


class EducationConnector(TierBConnector):
    ministry_code = "EDU"
    dataset_files = {
        "learning": "education/learning.csv",
        "exam_integrity": "education/exam_integrity.csv",
        "enrolment": "education/enrolment.csv",
    }
    valid_ranges = {
        "Learning Outcomes": (0.0, 100.0),
        "Exam Integrity": (0.0, 40.0),
        "Enrollment Quality": (30.0, 110.0),
    }

    def _compute_learning_outcomes(self, spec):
        return self._simple_series(
            spec,
            "learning",
            "aser_std3_can_read_std2_pct",
            formula="ASER: children enrolled in Std III who can read a Std II level text / children assessed * 100 (rural); secondary = NAS Grade-3 language proficiency",
            secondary_col="nas_grade3_language_pct",
        )

    def _compute_exam_integrity(self, spec):
        return self._simple_series(
            spec,
            "exam_integrity",
            "major_leak_or_cancellation_incidents",
            formula="count of major documented paper leaks / exam cancellations across national + state board, entrance and recruitment exams (press-compiled)",
            secondary_col="aspirants_affected_lakh",
        )

    def _compute_enrollment_quality(self, spec):
        return self._simple_series(
            spec,
            "enrolment",
            "ger_senior_secondary_pct",
            formula="UDISE+ Gross Enrolment Ratio, senior secondary (Classes 11-12) = enrolment in Cl.11-12 / population aged 16-17 * 100 ; secondary = elementary pupil-teacher ratio",
            secondary_col="pupil_teacher_ratio_elementary",
        )


def get_education_connector() -> EducationConnector:
    return EducationConnector()
