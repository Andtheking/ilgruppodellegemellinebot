# services/subscription_service.py
from typing import Tuple, List

from models.models import User, EventSerie, EventSerieSubscription

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