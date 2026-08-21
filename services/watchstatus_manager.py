from typing import List, Tuple
from models.models import User, EventSerie
from services.anilist_manager import get_users_anime_progress


def categorize_subscribers_progress(
    serie: EventSerie, 
    subscribers: List[User]
) -> Tuple[List[str], List[str], List[str]]:
    """_Categorizes subscribers into caught-up, behind, or unlinked based on AniList progress._

    Args:
        serie (EventSerie): _The event series being screened._
        subscribers (List[User]): _The list of subscribed users._

    Returns:
        Tuple[List[str], List[str], List[str]]: _Three lists of formatted mentions: caught up, behind, and unlinked._
    """
    target_ep = serie.current_episode

    # If series has no linked AniList record, format everyone as standard mention
    if not serie.anilist_anime:
        standard_tags = [
            f"{u.username}" if u.username else f'<a href="tg://user?id={u.id}">Utente</a>'
            for u in subscribers
        ]
        return standard_tags, [], []

    media_id = serie.anilist_anime.anilist_media_id
    linked_users = [u for u in subscribers if u.anilist_username]
    unlinked_users = [u for u in subscribers if not u.anilist_username]

    anilist_names = [u.anilist_username for u in linked_users if u.anilist_username]
    progress_map = get_users_anime_progress(media_id, anilist_names) if anilist_names else {}

    caught_up: List[str] = []
    behind: List[str] = []
    not_linked: List[str] = [
        f"{u.username}" if u.username else f'<a href="tg://user?id={u.id}">Utente</a>'
        for u in unlinked_users
    ]

    for user in linked_users:
        mention = f"@{user.username}" if user.username else f'<a href="tg://user?id={user.id}">Utente</a>'
        user_anilist = (user.anilist_username or "").lower()
        user_ep = progress_map.get(user_anilist, 0)

        # Caught up if at least watched up to the previous episode
        if user_ep >= target_ep - 1:
            caught_up.append(f"{mention} (Ep. {user_ep})")
        else:
            behind.append(f"{mention} (Ep. {user_ep}/{target_ep - 1})")

    return caught_up, behind, not_linked