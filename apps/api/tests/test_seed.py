def test_demo_seed_is_repeatable_and_never_creates_financial_records(db, settings):
    from safer import seed
    from safer.models import Institution, Instrument, User
    from sqlalchemy import func, select

    seed.populate(db, settings.oidc_issuer)
    seed.populate(db, settings.oidc_issuer)
    assert db.scalar(select(func.count()).select_from(Institution)) == 3
    assert db.scalar(select(func.count()).select_from(User)) == 7
    assert db.scalar(select(func.count()).select_from(Instrument)) == 0
