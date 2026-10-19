from datetime import date
import logging

import aiohttp

from .state import State

log = logging.getLogger(__name__)


def parse_names(payload: dict, day: date) -> list[str]:
    response = payload["response"]
    query = response["query"]
    if (int(query["annee"]), int(query["mois"]), int(query["jour"])) != (day.year, day.month, day.day):
        raise ValueError("La date renvoyée par Nominis ne correspond pas à la date demandée.")
    names = list(response["prenoms"]["majeurs"])
    if not names or any(not isinstance(n, str) or not n.strip() or len(n) > 80 for n in names):
        raise ValueError("Liste de prénoms invalide.")
    return names[:6]


async def get_names(session: aiohttp.ClientSession, state: State, day: date):
    cached = state.cached_names(day)
    if cached:
        return cached
    try:
        async with session.get("https://nominis.cef.fr/json/nominis.php",
                               params={"annee": day.year, "mois": day.month, "jour": day.day},
                               timeout=aiohttp.ClientTimeout(total=12)) as response:
            response.raise_for_status()
            names = parse_names(await response.json(content_type=None), day)
        state.cache_names(day, names)
        return names
    except (aiohttp.ClientError, TimeoutError, ValueError, KeyError, TypeError):
        log.warning("Calendrier des prénoms indisponible pour %s ; publication sans prénom.", day)
        return None
