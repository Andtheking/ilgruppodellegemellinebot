import asyncio
import time
from typing import Any, Dict, List, Optional
import httpx

from utils.log import log

ANILIST_API_URL = "https://graphql.anilist.co"

QUERY_USER_PROGRESS = """
query ($mediaId: Int, $userName: String) {
  MediaList (mediaId: $mediaId, userName: $userName, type: ANIME) {
    status
    progress
  }
}
"""

_PROGRESS_CACHE: Dict[tuple, tuple] = {}
CACHE_TTL = 300  # 5 minuti


async def _fetch_single_user_progress(
    client: httpx.AsyncClient, media_id: int, username: str
) -> Optional[tuple]:
    cache_key = (media_id, username.lower())
    now = time.time()
    if cache_key in _PROGRESS_CACHE:
        prog, exp = _PROGRESS_CACHE[cache_key]
        if now < exp:
            return (username.lower(), prog)

    variables = {"mediaId": media_id, "userName": username}
    try:
        response = await client.post(
            ANILIST_API_URL,
            json={"query": QUERY_USER_PROGRESS, "variables": variables},
            timeout=5.0,
        )
        if response.status_code == 200:
            data = response.json().get("data", {}).get("MediaList")
            if data and "progress" in data:
                prog = data["progress"]
                _PROGRESS_CACHE[cache_key] = (prog, now + CACHE_TTL)
                return (username.lower(), prog)
    except Exception as error:
        log(f"Errore recupero AniList per {username}: {error}")
    return None


async def get_users_anime_progress_async(
    media_id: int, 
    usernames: List[str]
) -> Dict[str, int]:
    """_Asynchronously fetches watch progress for AniList usernames concurrently._"""
    if not usernames:
        return {}

    progress_map: Dict[str, int] = {}
    async with httpx.AsyncClient() as client:
        tasks = [_fetch_single_user_progress(client, media_id, u) for u in usernames]
        results = await asyncio.gather(*tasks)
        for res in results:
            if res:
                progress_map[res[0]] = res[1]

    return progress_map


def get_users_anime_progress(
    media_id: int, 
    usernames: List[str]
) -> Dict[str, int]:
    """_Fetches watch progress for a list of AniList usernames for a specific anime._"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            return executor.submit(
                lambda: asyncio.run(get_users_anime_progress_async(media_id, usernames))
            ).result()
    else:
        return asyncio.run(get_users_anime_progress_async(media_id, usernames))


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


async def fetch_anime_info_by_id_async(anilist_id: int) -> Optional[Dict[str, Any]]:
    """_Asynchronously fetches anime metadata from the AniList GraphQL API using a media ID._"""
    variables = {"id": anilist_id}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                ANILIST_API_URL,
                json={"query": QUERY_GET_ANIME_BY_ID, "variables": variables},
                timeout=5.0,
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
                "site_url": data["siteUrl"],
            }
    except Exception as error:
        log(f"Errore durante la chiamata ad AniList: {error}")
        return None


def fetch_anime_info_by_id(anilist_id: int) -> Optional[Dict[str, Any]]:
    """_Fetches anime metadata from the AniList GraphQL API using a media ID._"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            return executor.submit(
                lambda: asyncio.run(fetch_anime_info_by_id_async(anilist_id))
            ).result()
    else:
        return asyncio.run(fetch_anime_info_by_id_async(anilist_id))


QUERY_CHECK_USER = """
query ($name: String) {
  User (name: $name) {
    id
    name
  }
}
"""


async def verify_anilist_user_async(username: str) -> Optional[str]:
    """_Asynchronously verifies if an AniList username exists and returns its canonical casing._"""
    variables = {"name": username.strip()}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                ANILIST_API_URL,
                json={"query": QUERY_CHECK_USER, "variables": variables},
                timeout=5.0,
            )
            if response.status_code != 200:
                return None

            data = response.json().get("data", {}).get("User")
            return data["name"] if data else None
    except Exception as error:
        log(f"Errore verifica utente AniList: {error}")
        return None


def verify_anilist_user(username: str) -> Optional[str]:
    """_Verifies if an AniList username exists and returns its canonical casing._"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            return executor.submit(
                lambda: asyncio.run(verify_anilist_user_async(username))
            ).result()
    else:
        return asyncio.run(verify_anilist_user_async(username))