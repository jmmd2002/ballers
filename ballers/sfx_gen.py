"""Procedurally generated default sound effects (original, royalty-free).
Any file you put in sounds/sfx/ with the same name overrides these."""
import wave
from pathlib import Path

import numpy as np

SR = 48000
_rng = np.random.default_rng(7)


def _t(dur):
    return np.arange(int(SR * dur)) / SR


def _noise(dur):
    return _rng.uniform(-1, 1, int(SR * dur))


def _lowpass(x, width):
    return np.convolve(x, np.ones(width) / width, mode="same")


def _sweep(f0, f1, dur, shape=np.sin):
    freq = np.linspace(f0, f1, int(SR * dur))
    return shape(2 * np.pi * np.cumsum(freq) / SR)


def _square(phase_signal):
    return np.sign(phase_signal)


def _fade(x, attack=0.005, release=0.01):
    a, r = int(SR * attack), int(SR * release)
    env = np.ones_like(x)
    if a:
        env[:a] = np.linspace(0, 1, a)
    if r:
        env[-r:] = np.minimum(env[-r:], np.linspace(1, 0, r))
    return x * env


def wall():
    """Soft, muffled knock (low pitch-dropping sine + dull tap)."""
    dur = 0.1
    t = _t(dur)
    # Kept above ~250 Hz so phone speakers still reproduce it.
    knock = (_sweep(420, 260, dur) + 0.3 * _sweep(840, 520, dur)) * np.exp(-t * 40)
    tap = _lowpass(_lowpass(_noise(dur), 60), 60) * np.exp(-t * 150) * 6
    return knock + tap


def hit():
    """Harder ball-on-ball impact: low square + thump + click."""
    t = _t(0.2)
    body = _square(np.sin(2 * np.pi * 196 * t)) * np.exp(-t * 22) * 0.45
    thump = np.sin(2 * np.pi * np.linspace(140, 60, len(t)) * t) * np.exp(-t * 14)
    click = _noise(0.2) * np.exp(-t * 90) * 0.6
    return body + thump + click


def puff():
    t = _t(0.45)
    env = np.minimum(t / 0.02, 1) * np.exp(-t * 9)
    return _lowpass(_noise(0.45), 30) * env * 6


def rasengan_form():
    """Rising, wobbling chakra whirl."""
    dur = 1.0
    t = _t(dur)
    whirl = _sweep(120, 620, dur) * 0.6 + _sweep(240, 1240, dur) * 0.25
    tremolo = 0.55 + 0.45 * np.sin(2 * np.pi * np.linspace(8, 30, len(t)) * t)
    wind = _lowpass(_noise(dur), 12) * 2.5 * np.linspace(0.3, 1, len(t))
    env = np.minimum(t / 0.5, 1) * np.minimum((dur - t) / 0.25, 1)
    return (whirl * tremolo + wind) * env


def rasengan_hit():
    t = _t(0.8)
    boom = np.sin(2 * np.pi * np.cumsum(np.linspace(180, 35, len(t))) / SR) * np.exp(-t * 4)
    blast = _lowpass(_noise(0.8), 8) * np.exp(-t * 6) * 2.5
    ring = _sweep(1200, 300, 0.8) * np.exp(-t * 10) * 0.3
    return boom + blast + ring


def fireball():
    """Roaring whoosh with crackle."""
    dur = 1.3
    t = _t(dur)
    roar = _lowpass(_noise(dur), 20) * 5
    rumble = np.sin(2 * np.pi * 70 * t + 3 * np.sin(2 * np.pi * 5 * t)) * 0.5
    crackle = (_rng.random(len(t)) > 0.9985) * _rng.uniform(-1, 1, len(t))
    crackle = _lowpass(crackle, 3) * 3
    env = np.minimum(t / 0.08, 1) * np.minimum((dur - t) / 0.5, 1)
    return (roar + rumble + crackle) * env


def burn():
    t = _t(0.3)
    return _lowpass(_noise(0.3), 6) * np.exp(-t * 12) * 3


def sharingan():
    """Sharp metallic 'shing'."""
    t = _t(0.7)
    tone = sum(np.sin(2 * np.pi * f * t) * a for f, a in ((1760, 0.5), (2637, 0.35), (3520, 0.2)))
    shimmer = 1 + 0.15 * np.sin(2 * np.pi * 14 * t)
    swish = _noise(0.7) * np.exp(-t * 40) * 0.4
    return tone * shimmer * np.exp(-t * 6) + swish


def ko():
    t = _t(1.2)
    boom = np.sin(2 * np.pi * np.cumsum(np.linspace(110, 30, len(t))) / SR) * np.exp(-t * 3)
    rumble = _lowpass(_noise(1.2), 40) * np.exp(-t * 3.5) * 8
    return boom + rumble


def slash():
    """Quick blade swipe: filtered noise swish ending in a thin metallic ring."""
    dur = 0.28
    t = _t(dur)
    swish = (_noise(dur) - _lowpass(_noise(dur), 4)) * np.exp(-((t - 0.04) / 0.03) ** 2) * 1.2
    ring = sum(np.sin(2 * np.pi * f * t) * a for f, a in ((2900, 0.3), (4300, 0.18)))
    return swish + ring * np.minimum(t / 0.03, 1) * np.exp(-t * 18)


def zipline():
    """ODM gear: gas hiss plus a cable whirring up in pitch."""
    dur = 0.55
    t = _t(dur)
    hiss = (_noise(dur) - _lowpass(_noise(dur), 3)) * np.exp(-t * 5) * 0.7
    whir = _square(_sweep(300, 900, dur)) * 0.12 * np.exp(-t * 4)
    clank = _square(np.sin(2 * np.pi * 520 * t)) * np.exp(-t * 60) * 0.4
    return hiss + whir + clank


def rock_throw():
    """Heavy whoosh of something big flying."""
    dur = 0.6
    t = _t(dur)
    whoosh = _lowpass(_noise(dur), 25) * 6 * np.sin(np.pi * t / dur) ** 2
    grunt = np.sin(2 * np.pi * np.cumsum(np.linspace(150, 90, len(t))) / SR) * np.exp(-t * 8) * 0.5
    return whoosh + grunt


def rock_break():
    """Crunching stone: low thud and a spray of gritty clicks."""
    dur = 0.5
    t = _t(dur)
    thud = np.sin(2 * np.pi * np.cumsum(np.linspace(160, 50, len(t))) / SR) * np.exp(-t * 12)
    grit = (_rng.random(len(t)) > 0.996) * _rng.uniform(-1, 1, len(t))
    grit = _lowpass(grit, 4) * 4 * np.exp(-t * 7)
    crack = _lowpass(_noise(dur), 3) * np.exp(-t * 35) * 1.5
    return thud + grit + crack


def grab():
    """Big meaty grip: low swipe into a squeezing thump."""
    dur = 0.5
    t = _t(dur)
    swipe = _lowpass(_noise(dur), 30) * 5 * np.exp(-((t - 0.1) / 0.07) ** 2)
    thump = np.sin(2 * np.pi * np.cumsum(np.linspace(110, 55, len(t))) / SR) * np.exp(-np.maximum(t - 0.15, 0) * 9)
    thump *= t > 0.15
    return swipe + thump


def sandstorm():
    """Desert wind: gusting, hollow noise with a low howl that bends in pitch."""
    dur = 3.0
    t = _t(dur)
    gusts = 0.6 + 0.4 * np.sin(2 * np.pi * 0.9 * t) * np.sin(2 * np.pi * 0.37 * t + 1)
    body = _lowpass(_noise(dur), 18) * 5
    hiss = (_noise(dur) - _lowpass(_noise(dur), 4)) * 0.25
    howl_freq = 330 + 60 * np.sin(2 * np.pi * 0.6 * t) + 25 * np.sin(2 * np.pi * 1.7 * t)
    howl = np.sin(2 * np.pi * np.cumsum(howl_freq) / SR) * 0.25
    env = np.minimum(t / 0.4, 1) * np.minimum((dur - t) / 0.8, 1)
    return (body + hiss + howl) * gusts * env


def pillar_rise():
    """Stone column grinding up out of the ground, ending in a settling thud."""
    dur = 0.7
    t = _t(dur)
    rise = np.minimum(t / 0.45, 1)
    grind = _lowpass(_noise(dur), 10) * 3 * (0.6 + 0.4 * np.sin(2 * np.pi * 23 * t)) * (1 - rise * 0.7)
    rumble = np.sin(2 * np.pi * np.cumsum(np.linspace(90, 180, len(t))) / SR) * 0.4 * (1 - rise * 0.8)
    grit = (_rng.random(len(t)) > 0.997) * _rng.uniform(-1, 1, len(t))
    grit = _lowpass(grit, 4) * 3 * (t < 0.45)
    hit_at = t - 0.45
    thud = np.sin(2 * np.pi * np.cumsum(np.linspace(260, 120, len(t))) / SR) * np.exp(-np.maximum(hit_at, 0) * 18)
    thud *= hit_at > 0
    return grind + rumble + grit + thud


def toss():
    """Light, quick whoosh of a small thrown fruit."""
    dur = 0.3
    t = _t(dur)
    band = _lowpass(_noise(dur), 6) - _lowpass(_noise(dur), 40)
    return band * 4 * np.sin(np.pi * t / dur) ** 3


def splat():
    """Juicy pomegranate burst: wet pop plus scattering seed ticks."""
    dur = 0.45
    t = _t(dur)
    pop = np.sin(2 * np.pi * np.cumsum(np.linspace(520, 160, len(t))) / SR) * np.exp(-t * 30)
    squelch = _lowpass(_noise(dur), 14) * 4 * np.exp(-t * 18) * (1 + 0.5 * np.sin(2 * np.pi * 45 * t))
    ticks = (_rng.random(len(t)) > 0.9975) * _rng.uniform(-1, 1, len(t)) * (t > 0.04)
    ticks = (ticks - _lowpass(ticks, 3)) * 3 * np.exp(-t * 6)
    return pop + squelch + ticks


def duduk():
    """Short duduk phrase: a warm, nasal double-reed tone with vibrato and breath,
    moving through the augmented second typical of Armenian folk melodies."""
    notes = ((293.66, 0.28), (311.13, 0.22), (369.99, 0.5), (349.23, 0.18), (311.13, 0.62))  # D Eb F# F Eb
    harmonics = ((1, 1.0), (2, 0.55), (3, 0.45), (4, 0.2), (5, 0.18), (6, 0.08), (7, 0.06))
    freq = np.concatenate([np.full(int(SR * d), f) for f, d in notes])
    freq = _lowpass(np.pad(freq, 600, mode="edge"), 1200)[600:-600]   # glide between notes
    t = np.arange(len(freq)) / SR
    vibrato = 1 + 0.008 * np.sin(2 * np.pi * 5.2 * t) * np.minimum(t / 0.4, 1)
    phase = 2 * np.pi * np.cumsum(freq * vibrato) / SR
    tone = sum(np.sin(k * phase) * a for k, a in harmonics)
    breath = (_noise(len(t) / SR) - _lowpass(_noise(len(t) / SR), 5)) * 0.08
    # Each note swells softly (reed instruments don't attack hard).
    swell = np.concatenate([0.75 + 0.25 * np.sin(np.pi * np.linspace(0, 1, int(SR * d))) for _, d in notes])
    swell = np.pad(swell, (0, len(t) - len(swell)), mode="edge")
    env = np.minimum(t / 0.08, 1) * np.minimum((t[-1] - t) / 0.3, 1)
    return (tone + breath) * swell * env


def swoosh():
    """Camera move on the tournament bracket: a soft rising-then-falling air sweep."""
    dur = 0.9
    t = _t(dur)
    air = (_lowpass(_noise(dur), 5) - _lowpass(_noise(dur), 30)) * 5
    tone = _sweep(300, 700, dur) * 0.15
    return (air + tone) * np.sin(np.pi * t / dur) ** 2


def advance():
    """Winner lands on the next bracket slot: a bright two-note chime."""
    dur = 0.9
    t = _t(dur)
    out = np.zeros_like(t)
    for start, f in ((0.0, 784.0), (0.11, 1175.0)):
        local = np.maximum(t - start, 0)
        bell = sum(np.sin(2 * np.pi * f * k * local) * a for k, a in ((1, 1.0), (2, 0.35), (3, 0.15)))
        out += bell * np.exp(-local * 5) * (t >= start)
    return out


GENERATORS = {f.__name__: f for f in
              (wall, hit, puff, rasengan_form, rasengan_hit, fireball, burn, sharingan, ko,
               slash, zipline, rock_throw, rock_break, grab,
               sandstorm, pillar_rise, toss, splat, duduk, swoosh, advance)}


def write_wav(path: Path, mono: np.ndarray, peak: float = 0.9):
    mono = _fade(mono.astype(np.float64))
    top = np.abs(mono).max()
    if top > 0:
        mono = mono / top * peak
    pcm = (np.clip(mono, -1, 1) * 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def generate_missing(sfx_dir: Path, exts=(".wav", ".ogg", ".mp3", ".flac")):
    for name, gen in GENERATORS.items():
        if not any((sfx_dir / f"{name}{ext}").exists() for ext in exts):
            write_wav(sfx_dir / f"{name}.wav", gen())


if __name__ == "__main__":
    from .audio import SFX_DIR
    for name, gen in GENERATORS.items():
        write_wav(SFX_DIR / f"{name}.wav", gen())
    print(f"Wrote {len(GENERATORS)} sounds to {SFX_DIR}")
