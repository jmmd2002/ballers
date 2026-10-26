"""Ballers entry point.

  python main.py                      # open the fighter selection menu
  python main.py naruto sasuke      # jump straight into a match
  python main.py naruto sasuke --seed 42
  python main.py --list               # show available balls
"""
import argparse
import os
import sys
from pathlib import Path

# Re-launch with the project's virtualenv if started with another interpreter.
_VENV_PYTHON = Path(__file__).resolve().parent / ".venv" / "bin" / "python"
if _VENV_PYTHON.exists() and Path(sys.prefix).resolve() != _VENV_PYTHON.parent.parent.resolve():
    os.execv(_VENV_PYTHON, [str(_VENV_PYTHON), *sys.argv])

from ballers import registry  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Bouncing-ball battle simulator")
    parser.add_argument("balls", nargs="*", help="two ball keys to skip the menu")
    parser.add_argument("--seed", type=int, help="match seed (same seed = same match)")
    parser.add_argument("--list", action="store_true", help="list available balls and exit")
    args = parser.parse_args()

    if args.list:
        for cls in registry.all_fighters():
            print(f"{cls.key:<12} {cls.description}")
        return
    if args.balls and len(args.balls) != 2:
        parser.error("give exactly two ball keys, or none to open the menu")

    from ballers.app import App
    from ballers.scenes import MatchScene, MenuScene

    app = App()
    if args.balls:
        scene = MatchScene(app, [registry.get(k) for k in args.balls], seed=args.seed)
    else:
        scene = MenuScene(app)
    app.run(scene)


if __name__ == "__main__":
    main()
