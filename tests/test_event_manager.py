import datetime
import pytest
import os
from peewee import SqliteDatabase

from models.models import User, Chat, EventSerie, EventSerieSubscription, ActualEvent, AnilistAnime, SharedEventSerie
from services.actualevent_manager import populate_rolling_events_for_series, sync_all_active_series

db_test = SqliteDatabase(':memory:', pragmas={'foreign_keys': 1})
MODELS = [User, Chat, AnilistAnime, EventSerie, EventSerieSubscription, ActualEvent, SharedEventSerie]
WEEKS_AHEAD = 4

@pytest.fixture(autouse=True)
def setup_test_database():
    """_Initialize DB and destroys it at the end of each test_"""
    db_test.bind(MODELS, bind_refs=False, bind_backrefs=False)
    db_test.connect()
    db_test.create_tables(MODELS)
    yield
    db_test.drop_tables(MODELS)
    db_test.close()

def test_populate_initial_events():
    """_Check that event series are populated_"""
    chat = Chat.create(id=123456, title="Gruppo Watchparty")
    
    today = datetime.date.today()
    series = EventSerie.create(
        chat=chat,
        title="Anime Night",
        default_event_time=datetime.time(21, 30),
        default_remind_time=datetime.time(20, 30),
        day_of_week=today.weekday(),
        start_date=today,
        end_date=today + datetime.timedelta(days=90),
        is_active=True
    )

    created = populate_rolling_events_for_series(series, weeks_ahead=WEEKS_AHEAD)
    assert created >= WEEKS_AHEAD
    assert ActualEvent.select().where(ActualEvent.event_serie == series).count() == created

def test_4_week_sync():
    """_If the event series has already been populated for the horizon weeks, 
    it should not be populated anymore._"""
    chat = Chat.create(id=999, title="Series Test")
    today = datetime.date.today()

    series = EventSerie.create(
        chat=chat,
        title="Gaming Night",
        default_event_time=datetime.time(21, 00),
        default_remind_time=datetime.time(20, 00),
        day_of_week=(today.weekday() + 1) % 7, # tomorrow
        start_date=today,
        end_date=today + datetime.timedelta(days=60),
        is_active=True
    )

    first_time = sync_all_active_series()
    assert first_time > 0

    second_time = sync_all_active_series()
    assert second_time == 0 # no actual event created

def test_series_without_end_date():
    """Check that series with end_date=None are supported and populated correctly."""
    chat = Chat.create(id=111, title="No End Date Chat")
    today = datetime.date.today()

    series = EventSerie.create(
        chat=chat,
        title="Ongoing Anime",
        default_event_time=datetime.time(21, 00),
        default_remind_time=datetime.time(20, 00),
        day_of_week=today.weekday(),
        start_date=today,
        end_date=None,
        is_active=True
    )

    created = populate_rolling_events_for_series(series, weeks_ahead=WEEKS_AHEAD)
    assert created >= WEEKS_AHEAD

    # sync should also work without throwing TypeError
    synced = sync_all_active_series()
    assert synced == 0

def test_advance_episode_without_anilist():
    """advance_episode should return None for total_episodes when anilist_anime is None."""
    from services.episodes_manager import advance_episode
    chat = Chat.create(id=222, title="No AniList Chat")
    today = datetime.date.today()

    series = EventSerie.create(
        chat=chat,
        title="Custom Movie Night",
        default_event_time=datetime.time(21, 00),
        default_remind_time=datetime.time(20, 00),
        day_of_week=today.weekday(),
        start_date=today,
        end_date=None,
        is_active=True,
        anilist_anime=None,
        current_episode=1
    )

    new_ep, total_eps = advance_episode(series)
    assert new_ep == 2
    assert total_eps is None

def test_user_mention_html_escaping():
    """Verify that mentions properly escape HTML characters."""
    from services.watchstatus_manager import format_user_mention
    user_with_tags = User.create(id=123, username="<hacker>&co")
    mention = format_user_mention(user_with_tags)
    assert "&lt;hacker&gt;&amp;co" in mention
    assert "<hacker>" not in mention

def test_delete_series_as_owner():
    """Deleting a series as owner removes the series and related events/subscriptions."""
    from services.eventseries_manager import delete_or_unlink_series
    chat = Chat.create(id=301, title="Owner Chat")
    user = User.create(id=501, username="sub_user")
    today = datetime.date.today()

    series = EventSerie.create(
        chat=chat,
        title="Owner Serie",
        default_event_time=datetime.time(21, 00),
        default_remind_time=datetime.time(20, 00),
        day_of_week=today.weekday(),
        start_date=today,
        end_date=None,
        is_active=True
    )
    populate_rolling_events_for_series(series)
    EventSerieSubscription.create(event_serie=series, user=user)

    result, title = delete_or_unlink_series(series.id, chat.id)
    assert result == "deleted"
    assert title == "Owner Serie"
    assert EventSerie.get_or_none(EventSerie.id == series.id) is None
    assert ActualEvent.select().where(ActualEvent.event_serie == series.id).count() == 0
    assert EventSerieSubscription.select().where(EventSerieSubscription.event_serie == series.id).count() == 0

def test_unlink_shared_series():
    """Unlinking a shared series removes only the shared relationship for that chat."""
    from services.eventseries_manager import delete_or_unlink_series
    owner_chat = Chat.create(id=401, title="Original Owner")
    guest_chat = Chat.create(id=402, title="Guest Group")
    today = datetime.date.today()

    series = EventSerie.create(
        chat=owner_chat,
        title="Shared Serie",
        default_event_time=datetime.time(21, 00),
        default_remind_time=datetime.time(20, 00),
        day_of_week=today.weekday(),
        start_date=today,
        end_date=None,
        is_active=True
    )
    SharedEventSerie.create(event_serie=series, chat=guest_chat)

    result, title = delete_or_unlink_series(series.id, guest_chat.id)
    assert result == "unlinked"
    assert title == "Shared Serie"
    # Series still exists for the owner
    assert EventSerie.get_or_none(EventSerie.id == series.id) is not None
    # Shared link for guest chat is gone
    assert SharedEventSerie.get_or_none((SharedEventSerie.event_serie == series) & (SharedEventSerie.chat == guest_chat)) is None

def test_skip_actual_event():
    """Skipping an actual event sets status to SKIPPED and excludes it from due reminders."""
    from services.actualevent_manager import get_next_actual_event, skip_actual_event
    from services.notification_service import get_due_reminders
    chat = Chat.create(id=501, title="Skip Test Chat")
    today = datetime.date.today()

    series = EventSerie.create(
        chat=chat,
        title="Skip Serie",
        default_event_time=datetime.time(21, 00),
        default_remind_time=datetime.time(20, 00),
        day_of_week=today.weekday(),
        start_date=today,
        end_date=None,
        is_active=True
    )
    populate_rolling_events_for_series(series)

    next_event = get_next_actual_event(series.id)
    assert next_event is not None
    assert next_event.status == "PENDING"

    skipped = skip_actual_event(next_event.id)
    assert skipped is not None
    assert skipped.status == "SKIPPED"

    # Due reminders should not include SKIPPED events even if remind_datetime is past
    skipped.remind_datetime = datetime.datetime.now() - datetime.timedelta(minutes=5)
    skipped.save()
    due = get_due_reminders()
    due_ids = [e.id for e, _ in due]
    assert skipped.id not in due_ids


def test_force_subscribe_and_unsubscribe():
    """Admin can force subscribe and unsubscribe an existing user."""
    from services.subscribe_to_eventseries import force_subscribe_user, force_unsubscribe_user, get_series_subscribers
    chat = Chat.create(id=601, title="Force Sub Chat")
    user = User.create(id=602, username="force_target")
    today = datetime.date.today()

    series = EventSerie.create(
        chat=chat,
        title="Weekly Anime",
        default_event_time=datetime.time(21, 00),
        default_remind_time=datetime.time(20, 00),
        day_of_week=today.weekday(),
        start_date=today,
        end_date=None,
        is_active=True
    )

    created, title = force_subscribe_user(user.id, series.id)
    assert created is True
    assert title == "Weekly Anime"
    assert any(u.id == user.id for u in get_series_subscribers(series.id))

    # Second call should not duplicate
    created_again, _ = force_subscribe_user(user.id, series.id)
    assert created_again is False

    # Unsubscribe
    removed, _ = force_unsubscribe_user(user.id, series.id)
    assert removed is True
    assert not any(u.id == user.id for u in get_series_subscribers(series.id))


def test_search_active_series_for_chat():
    """search_active_series_for_chat filters active series by query."""
    from services.subscribe_to_eventseries import search_active_series_for_chat
    chat = Chat.create(id=701, title="Search Chat")
    today = datetime.date.today()

    s1 = EventSerie.create(
        chat=chat,
        title="Frieren Watchparty",
        default_event_time=datetime.time(21, 00),
        default_remind_time=datetime.time(20, 00),
        day_of_week=today.weekday(),
        start_date=today,
        end_date=None,
        is_active=True
    )
    s2 = EventSerie.create(
        chat=chat,
        title="Dungeon Meshi",
        default_event_time=datetime.time(21, 00),
        default_remind_time=datetime.time(20, 00),
        day_of_week=today.weekday(),
        start_date=today,
        end_date=None,
        is_active=True
    )
    # Inactive serie
    s3 = EventSerie.create(
        chat=chat,
        title="Old Frieren",
        default_event_time=datetime.time(21, 00),
        default_remind_time=datetime.time(20, 00),
        day_of_week=today.weekday(),
        start_date=today,
        end_date=None,
        is_active=False
    )

    results = search_active_series_for_chat(chat.id, "frieren")
    assert len(results) == 1
    assert results[0].id == s1.id

    all_active = search_active_series_for_chat(chat.id)
    assert len(all_active) == 2


def test_change_series_day_of_week_basic():
    """Verify that changing a series day updates day_of_week and regenerates pending events."""
    from services.eventseries_manager import change_series_day_of_week
    chat = Chat.create(id=801, title="Day Change Chat")
    today = datetime.date.today()
    initial_day = 0  # Monday
    new_day = 3      # Thursday

    series = EventSerie.create(
        chat=chat,
        title="Day Change Test",
        default_event_time=datetime.time(21, 00),
        default_remind_time=datetime.time(20, 00),
        day_of_week=initial_day,
        start_date=today,
        end_date=None,
        is_active=True
    )
    populate_rolling_events_for_series(series)

    # All initial events should be Monday (0)
    initial_events = list(ActualEvent.select().where(ActualEvent.event_serie == series))
    assert len(initial_events) > 0
    for ev in initial_events:
        assert ev.event_datetime.weekday() == initial_day

    # Change day to Thursday (3)
    updated_serie, count = change_series_day_of_week(series.id, new_day)
    assert updated_serie is not None
    assert updated_serie.day_of_week == new_day
    assert count > 0

    new_events = list(ActualEvent.select().where(ActualEvent.event_serie == series))
    assert len(new_events) == count
    for ev in new_events:
        assert ev.event_datetime.weekday() == new_day
        assert ev.status == 'PENDING'


def test_change_series_day_of_week_preserves_past_events():
    """Verify that past SENT events are kept intact when shifting days."""
    from services.eventseries_manager import change_series_day_of_week
    chat = Chat.create(id=802, title="Preserve Past Chat")
    today = datetime.date.today()

    series = EventSerie.create(
        chat=chat,
        title="History Test",
        default_event_time=datetime.time(21, 00),
        default_remind_time=datetime.time(20, 00),
        day_of_week=1, # Tuesday
        start_date=today - datetime.timedelta(days=30),
        end_date=None,
        is_active=True
    )

    # Insert a past sent event
    past_dt = datetime.datetime.now() - datetime.timedelta(days=7)
    past_event = ActualEvent.create(
        event_serie=series,
        event_datetime=past_dt,
        remind_datetime=past_dt - datetime.timedelta(hours=1),
        status='SENT'
    )

    populate_rolling_events_for_series(series)

    # Shift to Friday (4)
    updated_serie, count = change_series_day_of_week(series.id, 4)
    assert updated_serie is not None
    assert count > 0

    # Past event still exists
    assert ActualEvent.get_or_none(ActualEvent.id == past_event.id) is not None
    assert ActualEvent.get_by_id(past_event.id).status == 'SENT'

    # Future events are Friday
    future_events = list(ActualEvent.select().where(
        (ActualEvent.event_serie == series) & (ActualEvent.status == 'PENDING')
    ))
    for ev in future_events:
        assert ev.event_datetime.weekday() == 4


def test_change_series_day_of_week_removes_future_skipped():
    """Verify that future skipped events on the old day are cleaned up."""
    from services.eventseries_manager import change_series_day_of_week
    chat = Chat.create(id=803, title="Skipped Cleanup Chat")
    today = datetime.date.today()

    series = EventSerie.create(
        chat=chat,
        title="Skipped Clean Test",
        default_event_time=datetime.time(21, 00),
        default_remind_time=datetime.time(20, 00),
        day_of_week=2, # Wednesday
        start_date=today,
        end_date=None,
        is_active=True
    )
    populate_rolling_events_for_series(series)

    # Mark the first pending event as SKIPPED
    first_event = ActualEvent.select().where(ActualEvent.event_serie == series).order_by(ActualEvent.event_datetime.asc()).first()
    first_event.status = 'SKIPPED'
    first_event.save()

    # Change day to Saturday (5)
    updated_serie, count = change_series_day_of_week(series.id, 5)
    assert updated_serie is not None

    # The skipped event on Wednesday should be gone
    assert ActualEvent.select().where(ActualEvent.status == 'SKIPPED').count() == 0

    # All current events should be PENDING on Saturday
    for ev in ActualEvent.select().where(ActualEvent.event_serie == series):
        assert ev.status == 'PENDING'
        assert ev.event_datetime.weekday() == 5


def test_change_series_day_of_week_non_existent():
    """Non-existent series ID returns None and 0."""
    from services.eventseries_manager import change_series_day_of_week
    serie, count = change_series_day_of_week(999999, 1)
    assert serie is None
    assert count == 0


def test_update_series_times():
    """Verify that updating series times changes defaults and pending actual events."""
    from services.eventseries_manager import update_series_times
    chat = Chat.create(id=901, title="Times Chat")
    today = datetime.date.today()
    series = EventSerie.create(
        chat=chat,
        title="Times Test",
        default_event_time=datetime.time(20, 00),
        default_remind_time=datetime.time(19, 00),
        day_of_week=today.weekday(),
        start_date=today,
        end_date=None,
        is_active=True
    )
    populate_rolling_events_for_series(series)

    new_event_time = datetime.time(22, 15)
    new_remind_time = datetime.time(21, 15)
    updated, count = update_series_times(series.id, new_event_time, new_remind_time)

    assert updated is not None
    assert updated.default_event_time == new_event_time
    assert updated.default_remind_time == new_remind_time
    assert count > 0

    for ev in ActualEvent.select().where(ActualEvent.event_serie == series):
        assert ev.event_datetime.time() == new_event_time
        assert ev.remind_datetime.time() == new_remind_time


def test_update_series_title():
    """Verify title updates and validation."""
    from services.eventseries_manager import update_series_title
    chat = Chat.create(id=902, title="Title Chat")
    today = datetime.date.today()
    series = EventSerie.create(
        chat=chat,
        title="Old Title",
        default_event_time=datetime.time(21, 00),
        default_remind_time=datetime.time(20, 00),
        day_of_week=today.weekday(),
        start_date=today,
        end_date=None,
        is_active=True
    )

    updated = update_series_title(series.id, "New Wonderful Title")
    assert updated is not None
    assert updated.title == "New Wonderful Title"
    assert EventSerie.get_by_id(series.id).title == "New Wonderful Title"

    # Empty title returns None and does not change title
    assert update_series_title(series.id, "   ") is None
    assert EventSerie.get_by_id(series.id).title == "New Wonderful Title"


def test_update_series_episode():
    """Verify current episode index update."""
    from services.eventseries_manager import update_series_episode
    chat = Chat.create(id=903, title="Episode Chat")
    today = datetime.date.today()
    series = EventSerie.create(
        chat=chat,
        title="Ep Test",
        default_event_time=datetime.time(21, 00),
        default_remind_time=datetime.time(20, 00),
        day_of_week=today.weekday(),
        start_date=today,
        end_date=None,
        is_active=True,
        current_episode=1
    )

    updated = update_series_episode(series.id, 12)
    assert updated is not None
    assert updated.current_episode == 12
    assert EventSerie.get_by_id(series.id).current_episode == 12

    # Negative episode defaults to 1
    update_series_episode(series.id, -5)
    assert EventSerie.get_by_id(series.id).current_episode == 1


def test_update_series_anilist():
    """Verify attaching and detaching AniList anime."""
    from services.eventseries_manager import update_series_anilist
    chat = Chat.create(id=904, title="AniList Chat")
    today = datetime.date.today()
    anime = AnilistAnime.create(anilist_media_id=99999, total_episodes=24)
    series = EventSerie.create(
        chat=chat,
        title="Ani Test",
        default_event_time=datetime.time(21, 00),
        default_remind_time=datetime.time(20, 00),
        day_of_week=today.weekday(),
        start_date=today,
        end_date=None,
        is_active=True,
        anilist_anime=None
    )

    # Attach
    updated = update_series_anilist(series.id, anime)
    assert updated is not None
    assert updated.anilist_anime_id == anime.anilist_media_id

    # Detach
    detached = update_series_anilist(series.id, None)
    assert detached is not None
    assert detached.anilist_anime is None


def test_update_series_end_date():
    """Verify updating end date recalculates rolling events."""
    from services.eventseries_manager import update_series_end_date
    chat = Chat.create(id=905, title="End Date Chat")
    today = datetime.date.today()
    series = EventSerie.create(
        chat=chat,
        title="End Date Test",
        default_event_time=datetime.time(21, 00),
        default_remind_time=datetime.time(20, 00),
        day_of_week=today.weekday(),
        start_date=today,
        end_date=None,
        is_active=True
    )
    populate_rolling_events_for_series(series)

    # Set end_date to 1 week from now
    target_end = today + datetime.timedelta(days=7)
    updated, count = update_series_end_date(series.id, target_end)
    assert updated is not None
    assert updated.end_date == target_end

    events = list(ActualEvent.select().where(ActualEvent.event_serie == series))
    for ev in events:
        assert ev.event_datetime.date() <= target_end

