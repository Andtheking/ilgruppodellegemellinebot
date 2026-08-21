from typing import Optional, Tuple
from models.models import EventSerie

def advance_episode(serie: EventSerie) -> Tuple[int, Optional[int]]:
    """_Increments the current episode count for an event series._

    Args:
        serie (EventSerie): _The event series._

    Returns:
        Tuple[int, Optional[int]]: _A tuple containing the new current episode and the total episodes._
    """

    serie.current_episode += 1
    serie.save()
    return serie.current_episode, serie.anilist_anime.total_episodes


def set_current_episode(serie_id: int, episode: int) -> None:
    """_Manually sets the current episode number for an event series._

    Args:
        serie_id (int): _The primary key ID of the event series._
        episode (int): _The episode number to set._
    """
    serie = EventSerie.get_by_id(serie_id)
    serie.current_episode = max(1, episode)
    serie.save()