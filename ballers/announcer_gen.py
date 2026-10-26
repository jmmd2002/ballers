"""Generate the arena announcer's lines with Piper TTS (original voice, safe to
monetize), slightly deepened and compressed for a punchy fight-game sound.

  python -m ballers.announcer_gen            # create missing lines
  python -m ballers.announcer_gen --force    # regenerate all

Lines: draw, "<Name> wins!" for every fighter, and per-matchup intros
("<A> versus <B>, fight!") which are generated on demand by matchup_line().
"""
import argparse
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

from . import registry
from .audio import SOUND_DIR

ANNOUNCER_DIR = SOUND_DIR / "announcer"
MODEL_DIR = ANNOUNCER_DIR / ".model"
VOICE = "en_US-ryan-high"
BASE_LINES = {"draw": "It's a draw!"}
# A bare "Fight!" comes out garbled with this voice, so it ends the matchup line
# in one breath and the comma pause before it is stretched afterwards.
FIGHT_PAUSE = 0.35

# Slightly deeper voice, a touch of low end, then compression. No reverb/echo.
ANNOUNCER_FX = ("asetrate={rate},aresample=48000,"
                "bass=g=3:f=120,"
                "acompressor=threshold=-22dB:ratio=4:attack=3:release=100:makeup=5,"
                "alimiter=limit=0.9:level=false")
PITCH = 0.93


def spoken_name(fighter) -> str:
    return fighter.announcer_name or fighter.name


def matchup_line(fighter_types) -> tuple[str, str]:
    """(key, text) for the intro line of a matchup."""
    key = "_vs_".join(f.key for f in fighter_types)
    return key, " versus ".join(spoken_name(f) for f in fighter_types) + ", fight!"


def _stretch_last_pause(audio: np.ndarray, rate: int, pause: float) -> np.ndarray:
    """Widen the longest quiet gap (>= 0.08 s) before a strong word to `pause` seconds,
    i.e. the comma pause. Gaps followed only by a weak sound (e.g. the release of a
    final "t") are skipped. Silence goes in near the gap's start so a soft opening
    consonant (the "f" of "fight") stays attached to its word."""
    win = int(rate * 0.02)
    levels = np.array([np.sqrt(np.mean(audio[i:i + win].astype(np.float64) ** 2))
                       for i in range(0, len(audio) - win, win)])
    db = 20 * np.log10(levels + 1e-9)
    top = db.max()
    quiet = db < top - 22
    runs, start = [], None
    for i, q in enumerate(quiet):
        if q and start is None:
            start = i
        elif not q and start is not None:
            if i - start >= 4 and db[i:i + 15].max() >= top - 6:
                runs.append((start, i))
            start = None
    if not runs:
        return audio
    gap_start, gap_end = max(runs, key=lambda r: r[1] - r[0])
    cut = min(gap_start + 2, gap_end) * win
    extra = max(0, int(pause * rate) - (gap_end - gap_start) * win)
    return np.concatenate([audio[:cut], np.zeros(extra, dtype=audio.dtype), audio[cut:]])


def all_lines() -> dict[str, str]:
    lines = dict(BASE_LINES)
    for fighter in registry.all_fighters():
        lines[f"{fighter.key}_wins"] = f"{spoken_name(fighter)} wins!"
    return lines


def _load_voice():
    from piper import PiperVoice
    model = MODEL_DIR / f"{VOICE}.onnx"
    if not model.exists():
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run(["python", "-m", "piper.download_voices", VOICE, "--download-dir", str(MODEL_DIR)],
                       check=True)
    return PiperVoice.load(str(model))


def generate(force: bool = False, extra: dict[str, str] | None = None) -> list[str]:
    """Create missing lines (all of them with force). `extra` adds lines such as matchups."""
    lines = {**all_lines(), **(extra or {})}
    todo = {k: v for k, v in lines.items() if force or not (ANNOUNCER_DIR / f"{k}.wav").exists()}
    if not todo:
        return []
    from piper import SynthesisConfig
    voice = _load_voice()
    # Lower noise = clearer, more consistent pronunciation between runs.
    config = SynthesisConfig(length_scale=1.1, noise_scale=0.4, noise_w_scale=0.5)
    ANNOUNCER_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for key, text in todo.items():
            raw = Path(tmp) / f"{key}.wav"
            chunks = list(voice.synthesize(text, syn_config=config))
            sample_rate = chunks[0].sample_rate
            audio = np.concatenate([c.audio_int16_array for c in chunks])
            if text.endswith("fight!"):
                audio = _stretch_last_pause(audio, sample_rate, FIGHT_PAUSE)
            with wave.open(str(raw), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio.astype("<i2").tobytes())
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw),
                            "-af", ANNOUNCER_FX.format(rate=int(sample_rate * PITCH)), "-ac", "1",
                            str(ANNOUNCER_DIR / f"{key}.wav")], check=True)
    return list(todo)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="regenerate existing lines")
    made = generate(parser.parse_args().force)
    print(f"Generated: {', '.join(made)}" if made else "All announcer lines already exist.")


if __name__ == "__main__":
    main()
