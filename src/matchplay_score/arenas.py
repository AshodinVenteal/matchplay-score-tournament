from dataclasses import dataclass
# "arenas" means "pinball tables" in matchplay terminology.

@dataclass
class Arena:
    name: str
    short_name: str
    era: str
    multiplier: float

ARENAS = [
    Arena(name="Quicksilver", short_name="Quicksilver", era="old", multiplier=350),
    Arena(name="Taxi", short_name="Taxi", era="old", multiplier=82),
    Arena(name="Spooky", short_name="Spooky", era="old", multiplier=50),
    Arena(name="Stars", short_name="Stars", era="old", multiplier=1200),
    Arena(name="Viking", short_name="Viking", era="old", multiplier=440),
    Arena(name="Eight Ball Deluxe", short_name="EBD", era="old", multiplier=180),

    Arena(name="Star Trek (Premium)", short_name="Star Trek", era="mid", multiplier=2.6),
    Arena(name="White Water", short_name="White Water", era="mid", multiplier=1),
    Arena(name="Theatre of Magic", short_name="Theatre", era="mid", multiplier=0.31),
    Arena(name="Creature from the Black Lagoon", short_name="Creature", era="mid", multiplier=2.1),
    Arena(name="Disney TRON: Legacy", short_name="TRON", era="mid", multiplier=8),
    Arena(name="Congo", short_name="Congo", era="mid", multiplier=0.35),

    Arena(name="Pokémon (Premium)", short_name="Pokémon", era="new", multiplier=1.2),
    Arena(name="Fallout (LE)", short_name="Fallout", era="new", multiplier=1.3),
    Arena(name="Dune", short_name="Dune", era="new", multiplier=0.95),
    Arena(name="Jurassic Park (Pro)", short_name="Jurassic Park", era="new", multiplier=0.95),
    Arena(name="Iron Maiden: Legacy of the Beast", short_name="Iron Maiden", era="new", multiplier=0.9),
    Arena(name="Avengers: Infinity Quest (Premium)", short_name="Avengers", era="new", multiplier=1.75),
]

print(ARENAS)