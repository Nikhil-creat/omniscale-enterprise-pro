# OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import InferenceJob, JobStatus, Subscription, SubscriptionStatus, SubscriptionTier, User
from backend.tasks import cleanup_stale_jobs, downgrade_expired_subscriptions

SYNC_TEST_DB = "sqlite:///./test_tasks.db"


@pytest.fixture
def sync_session(monkeypatch):
    engine = create_engine(SYNC_TEST_DB)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    # Point backend.tasks.SyncSession at this test engine/session for the
    # duration of the test.
    import backend.tasks as tasks_module

    monkeypatch.setattr(tasks_module, "SyncSession", Session)

    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def _make_user(session, email="scheduler@omniscale.dev"):
    user = User(email=email, hashed_password="x")
    session.add(user)
    session.flush()
    return user


def test_cleanup_stale_jobs_marks_timed_out_jobs_failed(sync_session):
    user = _make_user(sync_session)
    old_pending = InferenceJob(
        user_id=user.id,
        job_type="cnn",
        status=JobStatus.PENDING,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=90),
    )
    recent_pending = InferenceJob(
        user_id=user.id,
        job_type="cnn",
        status=JobStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )
    sync_session.add_all([old_pending, recent_pending])
    sync_session.commit()

    result = cleanup_stale_jobs(timeout_minutes=30)

    assert result["cleaned_up"] == 1
    sync_session.refresh(old_pending)
    sync_session.refresh(recent_pending)
    assert old_pending.status == JobStatus.FAILED
    assert "Timed out" in old_pending.error_message
    assert recent_pending.status == JobStatus.PENDING


def test_downgrade_expired_subscriptions_downgrades_overdue_past_due(sync_session):
    user = _make_user(sync_session, email="pastdue@omniscale.dev")
    overdue_sub = Subscription(
        user_id=user.id,
        tier=SubscriptionTier.PRO,
        status=SubscriptionStatus.PAST_DUE,
    )
    sync_session.add(overdue_sub)
    sync_session.commit()
    # Simulate it having been past_due for a while by backdating updated_at directly.
    sync_session.query(Subscription).filter_by(id=overdue_sub.id).update(
        {"updated_at": datetime.now(timezone.utc) - timedelta(days=10)}
    )
    sync_session.commit()

    result = downgrade_expired_subscriptions(grace_period_days=3)

    assert result["downgraded"] == 1
    sync_session.refresh(overdue_sub)
    assert overdue_sub.tier == SubscriptionTier.FREE
    assert overdue_sub.status == SubscriptionStatus.CANCELED


def test_downgrade_expired_subscriptions_leaves_recent_past_due_alone(sync_session):
    user = _make_user(sync_session, email="recentpastdue@omniscale.dev")
    recent_sub = Subscription(
        user_id=user.id,
        tier=SubscriptionTier.PRO,
        status=SubscriptionStatus.PAST_DUE,
    )
    sync_session.add(recent_sub)
    sync_session.commit()

    result = downgrade_expired_subscriptions(grace_period_days=3)

    assert result["downgraded"] == 0
    sync_session.refresh(recent_sub)
    assert recent_sub.tier == SubscriptionTier.PRO
