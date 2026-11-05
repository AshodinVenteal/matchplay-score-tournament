from collections import Counter
from dataclasses import dataclass

UNKNOWN = "[unknown player]"
ERAS = ["old", "mid", "new"]
MAX_PER_ERA = 2
CARD_GAME_LIMIT = MAX_PER_ERA * len(ERAS)


@dataclass
class Tournament:
    arenas_by_id: dict[int, Arena]
    players_by_id: dict[int, str]

    def get_player(self, player_id: int):
        return self.players_by_id.get(player_id, UNKNOWN)


# "arena" means "pinball machine" in matchplay terminology.
@dataclass
class Arena:
    name: str
    short_name: str
    era: str
    multiplier: float


@dataclass
class SinglePlayerGame:
    arena_id: int
    game_name: str
    player_name: str
    score: int
    multiplier: float
    era: str

    def computed_score(self) -> int:
        return int(self.score * self.multiplier)


@dataclass
class Card:
    player_name: str
    games: list[SinglePlayerGame]

    def computed_score(self) -> int:
        return sum(game.computed_score() for game in self.games)

    def is_valid(self):
        counts = Counter(game.era for game in self.games)
        return all(counts[era] <= MAX_PER_ERA for era in ERAS)


ARENAS = [
    # Old (alphanumeric displays)
    Arena(name="Stars", short_name="Stars", era="old", multiplier=500),
    Arena(name="Viking", short_name="Viking", era="old", multiplier=180),
    Arena(name="Quicksilver", short_name="Quicksilver", era="old", multiplier=140),
    Arena(name="Eight Ball Deluxe", short_name="EBD", era="old", multiplier=75),
    Arena(name="Spooky", short_name="Spooky", era="old", multiplier=21),
    Arena(name="Taxi", short_name="Taxi", era="old", multiplier=35),
    # Mid (DMD displays)
    Arena(
        name="Creature from the Black Lagoon",
        short_name="Creature",
        era="mid",
        multiplier=0.8,
    ),
    Arena(name="White Water", short_name="White Water", era="mid", multiplier=0.4),
    Arena(name="Congo", short_name="Congo", era="mid", multiplier=0.13),
    Arena(name="Theatre of Magic", short_name="Theatre", era="mid", multiplier=0.12),
    Arena(name="Disney TRON: Legacy", short_name="TRON", era="mid", multiplier=3.1),
    Arena(name="Star Trek (Premium)", short_name="Star Trek", era="mid", multiplier=1),
    # New (full LCD displays)
    Arena(
        name="Jurassic Park (Pro)",
        short_name="Jurassic Park",
        era="new",
        multiplier=0.33,
    ),
    Arena(
        name="Iron Maiden: Legacy of the Beast (Pro)",
        short_name="Iron Maiden",
        era="new",
        multiplier=0.33,
    ),
    Arena(
        name="Avengers: Infinity Quest (Premium)",
        short_name="Avengers",
        era="new",
        multiplier=0.67,
    ),
    Arena(name="Pokémon (Premium)", short_name="Pokémon", era="new", multiplier=0.33),
    Arena(name="Dune", short_name="Dune", era="new", multiplier=0.36),
    Arena(name="Fallout (LE)", short_name="Fallout", era="new", multiplier=0.43),
    # Test / alternate games
    Arena(
        name="Bram Stoker's Dracula", short_name="Dracula", era="mid", multiplier=0.5
    ),
    Arena(name="Bad Cats", short_name="Bad Cats", era="old", multiplier=30),
    Arena(
        name="Winchester Mystery House",
        short_name="Winchester",
        era="new",
        multiplier=0.9,
    ),
    Arena(name="Pulp Fiction", short_name="Pulp Fiction", era="new", multiplier=60),
    Arena(name="Game of Thrones", short_name="GoT", era="mid", multiplier=0.14),
]


def get_arenas_by_id(arena_data: list[dict]) -> dict[int, Arena]:
    """
    Given a matchplay 'arenas' dictionary from tournaments/<id>?includeArenas=true,
    create a map from arena IDs to arenas.
    """
    arenas_by_name: dict[str, Arena] = {arena.name: arena for arena in ARENAS}
    arenas_by_id: dict[int, Arena] = {}
    for arena_item in arena_data:
        arena_id = arena_item["arenaId"]
        arena_name = arena_item["name"]
        if arena_name in arenas_by_name:
            arenas_by_id[arena_id] = arenas_by_name[arena_name]
        else:
            print(f"missing name: {arena_name}")
    return arenas_by_id


def get_players_by_id(player_data: list[dict]) -> dict[int, str]:
    players_by_id: dict[int, str] = {}
    for player in player_data:
        players_by_id[player["playerId"]] = player["name"]
    return players_by_id


def parse_tournament(tournament_data: dict):
    return Tournament(
        arenas_by_id=get_arenas_by_id(tournament_data["arenas"]),
        players_by_id=get_players_by_id(tournament_data["players"]),
    )


def parse_game(game: dict, tournament: Tournament):
    arena_id = game["arenaId"]
    player_id = game["playerId"]
    arena = tournament.arenas_by_id[arena_id]
    return SinglePlayerGame(
        arena_id=arena_id,
        game_name=arena.short_name,
        player_name=tournament.get_player(player_id),
        score=game["score"],
        multiplier=arena.multiplier,
        era=arena.era,
    )


def parse_card(card: dict, tournament: Tournament) -> Card:
    player_id = card["playerId"]
    return Card(
        player_name=tournament.get_player(player_id),
        games=[parse_game(game, tournament) for game in card["singlePlayerGames"]],
    )
