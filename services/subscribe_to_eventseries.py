# services/subscription_service.py
from typing import Tuple, List

from peewee import ModelSelect
from models.models import User, EventSerie, EventSerieSubscription

def toggle_subscription(user_id: int, username: str, serie_id: int) -> Tuple[bool, str]:
    """Toggles a user's subscription status for an event series.

    Args:
        user_id (int): The unique Telegram ID of the user.
        username (str): The Telegram username of the user.
        serie_id (int): The primary key ID of the event series.

    Returns:
        Tuple[bool, str]: A tuple containing the subscription state (True if subscribed, False if unsubscribed) and the series title.
    """

    user = User.get_by_id(id=user_id)
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
    return List(
        User
        .select()
        .join(EventSerieSubscription)
        .where(EventSerieSubscription.event_serie_id == serie_id)
    )