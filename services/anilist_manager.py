from typing import Any, Dict, List, Optional, Tuple
import requests

ANILIST_API_URL = "https://graphql.anilist.co"

QUERY_USER_PROGRESS = """
query ($mediaId: Int, $userName: String) {
  MediaList (mediaId: $mediaId, userName: $userName, type: ANIME) {
    status
    progress
  }
}
"""


def get_users_anime_progress(
    media_id: int, 
    usernames: List[str]
) -> Dict[str, int]:
    """_Fetches watch progress for a list of AniList usernames for a specific anime._

    Args:
        media_id (int): _The AniList media ID of the anime._
        usernames (List[str]): _List of AniList usernames to check._

    Returns:
        Dict[str, int]: _A mapping of lowercase AniList username to the watched episode count._
    """
    progress_map: Dict[str, int] = {}

    for username in usernames:
        variables = {"mediaId": media_id, "userName": username}
        try:
            response = requests.post(
                ANILIST_API_URL,
                json={"query": QUERY_USER_PROGRESS, "variables": variables},
                timeout=4
            )
            if response.status_code == 200:
                data = response.json().get("data", {}).get("MediaList")
                if data and "progress" in data:
                    progress_map[username.lower()] = data["progress"]
        except Exception as error:
            print(f"Errore recupero AniList per {username}: {error}")

    return progress_map


QUERY_GET_ANIME_BY_ID = """
query ($id: Int) {
  Media (id: $id, type: ANIME) {
    id
    title {
      romaji
      english
    }
    episodes
    coverImage {
      large
    }
    siteUrl
  }
}
"""


def fetch_anime_info_by_id(anilist_id: int) -> Optional[Dict[str, Any]]:
    """_Fetches anime metadata from the AniList GraphQL API using a media ID._

    Args:
        anilist_id (int): _The AniList media ID._

    Returns:
        Optional[Dict[str, Any]]: _A dictionary containing anilist_id, title, total_episodes, cover_image, and site_url, or None if not found._
    """
    variables = {"id": anilist_id}
    try:
        response = requests.post(
            ANILIST_API_URL,
            json={"query": QUERY_GET_ANIME_BY_ID, "variables": variables},
            timeout=5
        )
        if response.status_code != 200:
            return None

        data = response.json().get("data", {}).get("Media")
        if not data:
            return None

        display_title = data["title"]["english"] or data["title"]["romaji"]
        return {
            "anilist_id": data["id"],
            "title": display_title,
            "total_episodes": data["episodes"],
            "cover_image": data["coverImage"]["large"],
            "site_url": data["siteUrl"]
        }
    except Exception as error:
        print(f"Errore durante la chiamata ad AniList: {error}")
        return None


QUERY_CHECK_USER = """
query ($name: String) {
  User (name: $name) {
    id
    name
  }
}
"""


def verify_anilist_user(username: str) -> Optional[str]:
    """_Verifies if an AniList username exists and returns its canonical casing._

    Args:
        username (str): _The AniList username to verify._

    Returns:
        Optional[str]: _The exact canonical username if found, None otherwise._
    """
    variables = {"name": username.strip()}
    try:
        response = requests.post(
            ANILIST_API_URL,
            json={"query": QUERY_CHECK_USER, "variables": variables},
            timeout=5,
        )
        if response.status_code != 200:
            return None

        data = response.json().get("data", {}).get("User")
        return data["name"] if data else None
    except Exception as error:
        print(f"Errore verifica utente AniList: {error}")
        return None