"""Headless balance testing: python -m ballers.sim naruto sasuke -n 500"""
import argparse
from collections import Counter

from . import registry
from .match import Match


def main():
    parser = argparse.ArgumentParser(description="Run many headless matches and report win rates.")
    parser.add_argument("balls", nargs=2, help="ball keys, e.g. naruto sasuke")
    parser.add_argument("-n", "--matches", type=int, default=200)
    parser.add_argument("--seed", type=int, default=0, help="first seed; seeds run sequentially")
    args = parser.parse_args()

    types = [registry.get(k) for k in args.balls]
    results = Counter()
    total_time = 0.0
    for i in range(args.matches):
        match = Match(types, seed=args.seed + i)
        winner = match.run_to_end()
        results[winner.name if winner else "Draw"] += 1
        total_time += match.time

    for name, count in results.most_common():
        print(f"{name:>10}: {count:4d}  ({100 * count / args.matches:.1f}%)")
    print(f"avg match length: {total_time / args.matches:.1f}s")


if __name__ == "__main__":
    main()
