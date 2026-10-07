from typing import Tuple, List, Optional
from models.models import User, EventSerie, EventSerieSubscription, SharedEventSerie

def toggle_subscription(user_id: int, username: str, serie_id: int) -> Tuple[bool, str]:
    """_Toggles a user's subscription status for an event series._

    Args:
        user_id (int): _The unique Telegram ID of the user._
        username (str): _The Telegram username of the user._
        serie_id (int): _The primary key ID of the event series._

    Returns:
        Tuple[bool, str]: _A tuple containing the subscription state (True if subscribed, False if unsubscribed) and the series title._
    """

    user = User.get_by_id(user_id)
    serie = EventSerie.get_by_id(serie_id)

    subscription = EventSerieSubscription.get_or_none(
        (EventSerieSubscription.event_serie == serie) &
        (EventSerieSubscription.user == user)
    )

    if subscription:
        subscription.delete_instance()
        return False, serie.title
    else:
        EventSerieSubscription.create(event_serie=serie, user=user)
        return True, serie.title


def get_series_subscribers(serie_id: int) -> List[User]:
    """Retrieves all users subscribed to a specific event series.

    Args:
        serie_id (int): The primary key ID of the event series.

    Returns:
        List[User]: A list of User instances subscribed to the series.
    """
    return list(
        User
        .select()
        .join(EventSerieSubscription)
        .where(EventSerieSubscription.event_serie == serie_id)
    )


def force_subscribe_user(user_id: int, serie_id: int) -> Tuple[bool, str]:
    """_Forcefully subscribes a user to an event series if not already subscribed._

    Returns:
        Tuple[bool, str]: _(was_newly_created, serie_title)_
    """
    user = User.get_by_id(user_id)
    serie = EventSerie.get_by_id(serie_id)
    _, created = EventSerieSubscription.get_or_create(
        event_serie=serie,
        user=user
    )
    return created, serie.title


def force_unsubscribe_user(user_id: int, serie_id: int) -> Tuple[bool, str]:
    """_Forcefully un-subscribes a user from an event series._

    Returns:
        Tuple[bool, str]: _(was_removed, serie_title)_
    """
    serie = EventSerie.get_or_none(EventSerie.id == serie_id)
    if not serie:
        return False, ""

    deleted = (
        EventSerieSubscription
        .delete()
        .where(
            (EventSerieSubscription.event_serie == serie) &
            (EventSerieSubscription.user == user_id)
        )
        .execute()
    )
    return (deleted > 0), serie.title


def search_active_series_for_chat(chat_id: int, query: Optional[str] = None) -> List[EventSerie]:
    """_Returns active series available in a chat, optionally filtered by title substring._"""
    base_query = (
        EventSerie.select()
        .left_outer_join(SharedEventSerie, on=(SharedEventSerie.event_serie == EventSerie.id))
        .where(
            (EventSerie.is_active == True) &
            ((EventSerie.chat == chat_id) | (SharedEventSerie.chat == chat_id))
        )
        .order_by(EventSerie.title.asc())
        .distinct()
    )
    if not query:
        return list(base_query)

    clean_query = query.strip().lower()
    return [s for s in base_query if clean_query in s.title.lower()]