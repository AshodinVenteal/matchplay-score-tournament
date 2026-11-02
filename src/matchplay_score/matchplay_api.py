import requests


def get_tournament_data(tournament_id: int) -> dict:
    url = f"https://api.matchplay.events/api/tournaments/{tournament_id}?includeArenas=true&includePlayers=true"
    response = requests.get(url)
    return response.json()["data"]


def get_cards(tournament_id: int) -> list[dict]:
    url = f"https://api.matchplay.events/api/tournaments/{tournament_id}/cards"
    return get_paginated_data(url)


def get_paginated_data(url: str) -> list[dict]:
    response_json = requests.get(url).json()
    items: list = response_json["data"]
    next: str = response_json["links"]["next"]
    if next is not None:
        return items + get_paginated_data(next)
    else:
        return items
