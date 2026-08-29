from app.database import Base, SessionLocal, engine
from app.models import KPI, Ministry


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        existing = db.query(Ministry).filter(Ministry.code == "MOH").first()
        if existing:
            print("Ministry of Health already seeded, skipping.")
            return

        moh = Ministry(
            name="Ministry of Health",
            code="MOH",
            description="Responsible for public health policy, hospitals, and disease control.",
        )
        db.add(moh)
        db.flush()  # assigns moh.id without committing yet

        kpis = [
            KPI(
                ministry_id=moh.id,
                name="Hospital Bed Occupancy Rate",
                category="healthcare access",
                unit="%",
                current_value=78,
                target_value=85,
                period="Q2 2026",
            ),
            KPI(
                ministry_id=moh.id,
                name="Immunization Coverage",
                category="preventive care",
                unit="%",
                current_value=92,
                target_value=95,
                period="Q2 2026",
            ),
            KPI(
                ministry_id=moh.id,
                name="Average Patient Wait Time",
                category="service quality",
                unit=" min",
                current_value=45,
                target_value=30,
                period="Q2 2026",
            ),
            KPI(
                ministry_id=moh.id,
                name="Maternal Mortality Rate",
                category="public health outcomes",
                unit=" per 100,000",
                current_value=12,
                target_value=8,
                period="Q2 2026",
            ),
            KPI(
                ministry_id=moh.id,
                name="Health Budget Utilization",
                category="fiscal performance",
                unit="%",
                current_value=67,
                target_value=90,
                period="Q2 2026",
            ),
        ]
        db.add_all(kpis)
        db.commit()
        print(f"Seeded {moh.name} with {len(kpis)} KPIs.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
