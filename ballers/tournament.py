"""Countryball Cup: a single-elimination bracket of every country, played one
match per video.

  python -m ballers.tournament                   # progress and the next playable matches
  python -m ballers.tournament play              # export the next playable match, record the winner
  python -m ballers.tournament play --match 1-5  # a specific match (round-match, 1-based)
  python -m ballers.tournament bracket out.png   # full bracket as an image

256 slots; whoever has no first-round opponent gets a bye. The draw is seeded
and saved in tournaments/countries.json together with every result; countries
added to the roster later fill byes (see add_entrants). A match can be played
once both of its countries exist as fighters (ballers/countries/)."""
from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import registry
from .countries._roster import COUNTRIES, NAMES

ROUNDS = 8
SLOTS = 2 ** ROUNDS
ROUND_NAMES = ["First Round", "Round of 128", "Round of 64", "Round of 32", "Round of 16",
               "Quarter-final", "Semi-final", "Final"]
STATE_PATH = Path(__file__).resolve().parent.parent / "tournaments" / "countries.json"
OPENING_MATCH = ("libya", "armenia")
TITLE = "COUNTRYBALL CUP"

Match = tuple[int, int]   # (round, index within round), both 0-based


@dataclass
class Tournament:
    slots: list[str | None]                  # first-round slots, None = bye
    draw_seed: int = 0
    results: dict[str, dict] = field(default_factory=dict)   # "r-i" -> {"winner", "seed", "video"}

    @classmethod
    def draw(cls, draw_seed: int = 1) -> Tournament:
        keys = [key for key, _, _ in COUNTRIES]
        byes = SLOTS - len(keys)
        first = SLOTS // 2
        bye_matches = {int((k + 0.5) * first / byes) for k in range(byes)}
        assert len(bye_matches) == byes and 0 not in bye_matches
        rest = [k for k in keys if k not in OPENING_MATCH]
        random.Random(draw_seed).shuffle(rest)
        pool = iter(rest)
        slots: list[str | None] = list(OPENING_MATCH)
        for m in range(1, first):
            slots += [next(pool), None if m in bye_matches else next(pool)]
        assert next(pool, None) is None
        return cls(slots, draw_seed)

    # --- Persistence ----------------------------------------------------------

    @classmethod
    def load(cls, path: Path = STATE_PATH) -> Tournament:
        if not path.exists():
            t = cls.draw()
            t.save(path)
            return t
        data = json.loads(path.read_text())
        t = cls(data["slots"], data.get("draw_seed", 0), data.get("results", {}))
        missing = [key for key, _, _ in COUNTRIES if key not in t.slots]
        if missing:
            t.add_entrants(missing)
            t.save(path)
            print(f"Added to the bracket: {', '.join(NAMES[k] for k in missing)}")
        return t

    def save(self, path: Path = STATE_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"draw_seed": self.draw_seed, "slots": self.slots,
                                    "results": self.results}, indent=1, ensure_ascii=False))

    def add_entrants(self, keys: list[str]):
        """Put countries added to the roster after the draw into first-round byes.
        Byes next to a played match are skipped, so pairings already shown in a
        video stay the same."""
        rng = random.Random(f"{self.draw_seed}:{','.join(keys)}")
        open_byes = [i for i in range(SLOTS // 2) if self.is_bye((0, i))
                     and match_id((0, i ^ 1)) not in self.results and match_id((1, i // 2)) not in self.results]
        if len(open_byes) < len(keys):
            raise ValueError(f"Only {len(open_byes)} open byes left for {len(keys)} new countries")
        rng.shuffle(open_byes)
        keys = list(keys)
        rng.shuffle(keys)
        for i, key in zip(open_byes, keys):
            self.slots[2 * i + 1] = key

    def with_result(self, m: Match, winner: str, **info) -> Tournament:
        results = dict(self.results)
        results[match_id(m)] = {"winner": winner, **info}
        return Tournament(self.slots, self.draw_seed, results)

    # --- Bracket queries --------------------------------------------------------

    def entrant(self, r: int, p: int) -> str | None:
        """Who sits in slot p of round r (round ROUNDS = the champion); None if undecided."""
        return self.slots[p] if r == 0 else self.winner((r - 1, p))

    def players(self, m: Match) -> tuple[str | None, str | None]:
        r, i = m
        return self.entrant(r, 2 * i), self.entrant(r, 2 * i + 1)

    def is_bye(self, m: Match) -> bool:
        return m[0] == 0 and self.slots[2 * m[1] + 1] is None

    def winner(self, m: Match) -> str | None:
        if self.is_bye(m):
            return self.slots[2 * m[1]]
        result = self.results.get(match_id(m))
        return result["winner"] if result else None

    def loser(self, m: Match) -> str | None:
        win = self.winner(m)
        if win is None or self.is_bye(m):
            return None
        a, b = self.players(m)
        return b if win == a else a

    def eliminated(self) -> set[str]:
        return {self.loser(m) for m in all_matches() if self.loser(m)}

    def number(self, m: Match) -> tuple[int, int]:
        """(match number, matches in the round), counting real matches only (no byes)."""
        r, i = m
        real = [j for j in range(SLOTS >> (r + 1)) if not self.is_bye((r, j))]
        return real.index(i) + 1, len(real)

    def playable(self) -> list[Match]:
        fighters = {cls.key for cls in registry.all_fighters()}
        return [m for m in all_matches() if self.winner(m) is None
                and all(p is not None and p in fighters for p in self.players(m))]

    def label(self, m: Match) -> str:
        n, total = self.number(m)
        name = ROUND_NAMES[m[0]]
        return name if total == 1 else f"{name} · Match {n} of {total}"


def all_matches() -> list[Match]:
    return [(r, i) for r in range(ROUNDS) for i in range(SLOTS >> (r + 1))]


def match_id(m: Match) -> str:
    return f"{m[0]}-{m[1]}"


def parse_match(text: str, tour: Tournament) -> Match:
    """'1-5' = round 1, match 5 (1-based, byes not counted)."""
    r, n = (int(x) for x in text.split("-"))
    r -= 1
    real = [j for j in range(SLOTS >> (r + 1)) if not tour.is_bye((r, j))]
    return r, real[n - 1]


# --- Commands -------------------------------------------------------------------

def play(tour: Tournament, m: Match, best_of: int, out: Path | None):
    from . import bracket, export

    a, b = tour.players(m)
    types = [registry.get(a), registry.get(b)]
    print(f"{tour.label(m)}: {NAMES[a]} vs {NAMES[b]}")
    print(f"Searching {best_of} matches for the best one...")
    seed = export.pick_seed(types, best_of, None, 0)
    n, _ = tour.number(m)
    out = out or export.video_dir(types) / f"cup_r{m[0] + 1}_m{n}_{a}_vs_{b}_seed{seed}.mp4"
    result = export.export(types, seed, out, outro_time=bracket.WINNER_HOLD,
                           epilogue=bracket.epilogue(tour, m))
    tour.results[match_id(m)] = {"winner": result.winner.key, "seed": seed, "video": str(out)}
    tour.save()
    print(f"{NAMES[result.winner.key]} advances. Saved to {STATE_PATH}")


def status(tour: Tournament):
    done = sum(1 for m in all_matches() if tour.winner(m) and not tour.is_bye(m))
    total = sum(1 for m in all_matches() if not tour.is_bye(m))
    print(f"{TITLE}: {done}/{total} matches played, {len(COUNTRIES)} countries")
    champion = tour.entrant(ROUNDS, 0)
    if champion:
        print(f"Champion: {NAMES[champion]}")
    ready = tour.playable()
    if ready:
        print("Playable now:")
        for m in ready[:10]:
            a, b = tour.players(m)
            print(f"  {m[0] + 1}-{tour.number(m)[0]:<4} {tour.label(m)}: {NAMES[a]} vs {NAMES[b]}")
    else:
        print("No playable match: add fighters for the countries in the next matches:")
        upcoming = [m for m in all_matches() if tour.winner(m) is None and all(tour.players(m))][:5]
        for m in upcoming:
            a, b = tour.players(m)
            print(f"  {m[0] + 1}-{tour.number(m)[0]:<4} {NAMES[a]} vs {NAMES[b]}")


def main():
    parser = argparse.ArgumentParser(description="Countryball Cup tournament.")
    sub = parser.add_subparsers(dest="cmd")
    p_play = sub.add_parser("play", help="export the next playable match and record the result")
    p_play.add_argument("--match", help="round-match, e.g. 1-5 (1-based, byes not counted)")
    p_play.add_argument("--best-of", type=int, default=50)
    p_play.add_argument("-o", "--out", type=Path)
    p_img = sub.add_parser("bracket", help="save the full bracket as an image")
    p_img.add_argument("out", type=Path)
    args = parser.parse_args()

    tour = Tournament.load()
    if args.cmd == "play":
        if args.match:
            m = parse_match(args.match, tour)
            if m not in tour.playable():
                sys.exit("That match isn't playable (already played, or a country has no fighter yet).")
        else:
            ready = tour.playable()
            if not ready:
                sys.exit("No playable match; see `python -m ballers.tournament`.")
            m = ready[0]
        play(tour, m, args.best_of, args.out)
    elif args.cmd == "bracket":
        from . import bracket
        bracket.save_image(tour, args.out)
        print(f"Saved {args.out}")
    else:
        status(tour)


if __name__ == "__main__":
    main()
