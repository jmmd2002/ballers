"""Sound: turns match events into named cues, then either plays them live
(pygame.mixer) or records them for offline mixing into exported videos.

Sound files live in sounds/ (any of .wav .ogg .mp3 .flac .m4a):
  sounds/sfx/<name>.*                  effects; missing defaults are generated
  sounds/voices/<fighter>/<ability>.*  voice lines, e.g. voices/naruto/rasengan.mp3
  sounds/announcer/<line>.*            announcer (ballers/announcer_gen.py)
Missing files are silently skipped.
"""
from __future__ import annotations

import subprocess
import threading
import wave
from pathlib import Path
from typing import Callable

import numpy as np

from .entity import Ball
from .events import (AbilityUsed, Contact, Damage, EntityRemoved, EntitySpawned, FighterDefeated,
                     MatchOver, StatusApplied, WallHit)
from .match import Match

SOUND_DIR = Path(__file__).resolve().parent.parent / "sounds"
SFX_DIR = SOUND_DIR / "sfx"
VOICE_DIR = SOUND_DIR / "voices"
EXTS = (".wav", ".ogg", ".mp3", ".flac", ".m4a")
SAMPLE_RATE = 48000

VOLUME = {"sfx/wall": 0.15, "sfx/hit": 0.35, "sfx/puff": 0.3, "sfx/burn": 0.3, "sfx/slash": 0.3,
          "sfx/sandstorm": 0.3, "sfx/toss": 0.3, "sfx/splat": 0.35, "sfx/duduk": 0.55,
          "sfx/arminha_shot": 0.3, "sfx/snore": 0.5, "sfx/cheer": 0.35}
DEFAULT_SFX_VOLUME = 0.4
VOICE_VOLUME = 1.0
VOICE_DUCK = 0.4  # sound effects drop to this level while a voice line plays (exports)
VOICE_PREFIXES = ("voices/", "announcer/")
WINNER_DELAY = 0.5   # seconds between the KO and the announcer's "<name> wins!"
MIN_GAP = 0.05   # seconds; the same cue firing faster than this is merged
CUT_FADE = 0.08  # fade-out when a fighter's voice line is cut off by their next one
DOT_GAP = 0.15   # hit sounds from damage over time repeat at most this often


def ensure_default_sfx():
    from .sfx_gen import generate_missing
    generate_missing(SFX_DIR, EXTS)


def ensure_announcer(extra: dict[str, str] | None = None):
    """Generate missing announcer lines (e.g. for a new fighter) if Piper is installed."""
    try:
        from .announcer_gen import generate
    except ImportError:
        return
    generate(extra=extra)


def ensure_matchup_line(fighter_types) -> str:
    """Make sure the "<A> versus <B>, fight!" intro exists; returns its sound key."""
    from .announcer_gen import matchup_line
    key, text = matchup_line(fighter_types)
    ensure_announcer({key: text})
    return f"announcer/{key}"


def find(key: str) -> Path | None:
    for ext in EXTS:
        path = SOUND_DIR / f"{key}{ext}"
        if path.exists():
            return path
    return None


class SoundCues:
    """Subscribes to a match and calls sink(key, volume) for each sound to play."""

    def __init__(self, match: Match, sink: Callable[[str, float], None], announcer: bool = True):
        self.match = match
        self.sink = sink
        self._last: dict[str, float] = {}
        bus = match.bus
        bus.subscribe(WallHit, lambda e: isinstance(e.entity, Ball) and self.cue("sfx/wall"))
        bus.subscribe(Contact, lambda e: e.a.solid and e.b.solid and self.cue("sfx/hit"))
        bus.subscribe(AbilityUsed, self._on_ability)
        bus.subscribe(EntitySpawned, lambda e: self.cue_sfx(e.entity.spawn_sound))
        bus.subscribe(EntityRemoved, lambda e: self.cue_sfx(e.entity.death_sound))
        bus.subscribe(Damage, lambda e: e.source and self.cue_sfx(
            e.source.hit_sound, gap=DOT_GAP if e.continuous else MIN_GAP))
        bus.subscribe(StatusApplied, lambda e: self.cue_sfx(e.status.sound))
        bus.subscribe(FighterDefeated, lambda e: self.cue("sfx/ko"))
        if announcer:
            bus.subscribe(MatchOver, self._on_over)

    def _on_over(self, e: MatchOver):
        line = f"{e.winner.key}_wins" if e.winner else "draw"
        self.cue(f"announcer/{line}", VOICE_VOLUME, delay=WINNER_DELAY)

    def _on_ability(self, e: AbilityUsed):
        if e.ability is None:
            return
        fighter_key = getattr(e.caster, "key", None)
        if fighter_key:
            self.cue(f"voices/{fighter_key}/{e.ability.voice}", VOICE_VOLUME)
        self.cue_sfx(e.ability.sfx)

    def cue_sfx(self, name: str | None, gap: float = MIN_GAP):
        if name:
            self.cue(f"sfx/{name}", gap=gap)

    def cue(self, key: str, volume: float | None = None, delay: float = 0.0, gap: float = MIN_GAP):
        now = self.match.time
        if now - self._last.get(key, -1.0) < gap:
            return
        self._last[key] = now
        self.sink(key, VOLUME.get(key, DEFAULT_SFX_VOLUME) if volume is None else volume, delay)


class LivePlayer:
    """Sink that plays cues immediately through pygame.mixer."""

    def __init__(self):
        import pygame
        self._pygame = pygame
        self._cache: dict[str, object] = {}
        self._talking: dict[str, object] = {}   # speaker -> channel of their current line
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=SAMPLE_RATE)
            pygame.mixer.set_num_channels(32)
            ensure_default_sfx()
            ensure_announcer()
            self.enabled = True
        except pygame.error:
            self.enabled = False

    def __call__(self, key: str, volume: float, delay: float = 0.0):
        if not self.enabled:
            return
        if delay > 0:
            threading.Timer(delay, self, (key, volume)).start()
            return
        if key not in self._cache:
            path = find(key)
            self._cache[key] = self._pygame.mixer.Sound(str(path)) if path else None
        sound = self._cache[key]
        if sound is not None:
            who = speaker(key)
            if who in self._talking:
                self._talking.pop(who).fadeout(int(CUT_FADE * 1000))
            channel = sound.play()
            if channel:
                channel.set_volume(volume)
                if who:
                    self._talking[who] = channel


class Recorder:
    """Sink that records (time, key, volume) for offline mixing."""

    def __init__(self, match: Match, time_offset: float = 0.0):
        self.match = match
        self.time_offset = time_offset
        self.cues: list[tuple[float, str, float]] = []

    def __call__(self, key: str, volume: float, delay: float = 0.0):
        self.cues.append((self.match.time + self.time_offset + delay, key, volume))


def _decode(path: Path) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"],
        check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype="<f4")


def duration(key: str) -> float:
    path = find(key)
    return len(_decode(path)) / SAMPLE_RATE if path else 0.0


def last_word_onset(key: str, gap: float = 0.12) -> float:
    """Seconds into a clip where its last word starts (after the last pause of at
    least `gap` seconds). Used to land the FIGHT! banner on the spoken "Fight!"."""
    path = find(key)
    if path is None:
        return 0.0
    clip = _decode(path)
    win = int(0.01 * SAMPLE_RATE)
    levels = np.array([np.sqrt(np.mean(clip[i:i + win] ** 2)) for i in range(0, len(clip) - win, win)])
    # Announcer pauses are near-silent, so a strict threshold ignores the short dip
    # before a word-final consonant (the "t" of "fight") while catching real pauses.
    loud = 20 * np.log10(levels + 1e-9) > 20 * np.log10(levels.max() + 1e-9) - 30
    onset, quiet = 0, 0
    for i, is_loud in enumerate(loud):
        if is_loud:
            if quiet * 0.01 >= gap:
                onset = i
            quiet = 0
        else:
            quiet += 1
    return onset * 0.01


def speaker(key: str) -> str | None:
    """Fighter whose voice a cue is ("voices/lula/discurso" -> "lula"), else None."""
    parts = key.split("/")
    return parts[1] if parts[0] == "voices" and len(parts) > 2 else None


def mix(cues: list[tuple[float, str, float]], duration: float, out_path: Path) -> int:
    """Render cues into a stereo 16-bit WAV. Returns the number of cues with a sound file.
    A fighter's new voice line cuts off their previous one (nobody says two lines at once)."""
    n = int(duration * SAMPLE_RATE) + 1
    voices, sfx = np.zeros(n), np.zeros(n)
    duck = np.ones(n)
    cache: dict[str, np.ndarray | None] = {}
    used = 0
    cues = sorted(cues, key=lambda c: c[0])
    next_line: dict[int, float] = {}   # cue index -> when the same speaker talks again
    last: dict[str, int] = {}
    for i, (t, key, _) in enumerate(cues):
        who = speaker(key)
        if who and find(key):
            if who in last:
                next_line[last[who]] = t
            last[who] = i
    fade = int(CUT_FADE * SAMPLE_RATE)
    for i, (t, key, volume) in enumerate(cues):
        if key not in cache:
            path = find(key)
            cache[key] = _decode(path) if path else None
        clip = cache[key]
        start = int(t * SAMPLE_RATE)
        if clip is None or start >= n:
            continue
        if i in next_line:
            cut = int(next_line[i] * SAMPLE_RATE) - start
            if cut < len(clip):
                clip = clip[:max(cut, 0)].copy()
                tail = min(fade, len(clip))
                clip[len(clip) - tail:] *= np.linspace(1, 0, tail)
        end = min(n, start + len(clip))
        is_voice = key.startswith(VOICE_PREFIXES)
        (voices if is_voice else sfx)[start:end] += clip[:end - start] * volume
        if is_voice:
            duck[start:end] = VOICE_DUCK
        used += 1
    ramp = int(0.05 * SAMPLE_RATE)   # smooth the ducking in and out
    duck = np.convolve(duck, np.ones(ramp) / ramp, mode="same")
    buf = np.tanh(voices + sfx * duck)   # soft limiter so stacked sounds never hard-clip
    pcm = (np.repeat(buf[:, None], 2, axis=1) * 32767).astype("<i2")
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())
    return used
