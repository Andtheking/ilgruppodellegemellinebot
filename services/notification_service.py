import datetime
from typing import List, Tuple
from models.models import ActualEvent, EventSerieSubscription, User

def get_due_reminders() -> List[Tuple[ActualEvent, List[User]]]:
    """_Fetches all pending events whose reminder time has passed along with subscribed users._

    Returns:
        List[Tuple[ActualEvent, List[User]]]: _A list of tuples, each containing an ActualEvent and its subscribed users._
    """
    now = datetime.datetime.now()

    due_events = list(
        ActualEvent
        .select()
        .where(
            (ActualEvent.status == 'PENDING') &
            (ActualEvent.remind_datetime <= now)
        )
    )

    results: List[Tuple[ActualEvent, List[User]]] = []
    for event in due_events:
        subscribed_users = list(
            User
            .select()
            .join(EventSerieSubscription)
            .where(EventSerieSubscription.event_serie == event.event_serie)
        )
        results.append((event, subscribed_users))

    return results


def mark_events_as_sent(events: List[ActualEvent]) -> None:
    """_Updates the status of multiple actual events to SENT in the database._

    Args:
        events (List[ActualEvent]): _The list of event instances to update._
    """
    if not events:
        return

    event_ids = [e.id for e in events]
    ActualEvent.update(status='SENT').where(ActualEvent.id.in_(event_ids)).execute()