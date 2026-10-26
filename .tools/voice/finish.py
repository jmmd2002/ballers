"""finish.py IN.wav OUT.mp3 [pauses] - widen the N longest gaps between phrases to
dramatic pauses and apply the punchy announcer master. Prints pause positions."""
import subprocess
import sys

import numpy as np

MASTER = ("silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
          "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
          "highpass=f=70,bass=g=5:f=110,"
          "acompressor=threshold=-26dB:ratio=6:attack=2:release=120:makeup=7,"
          "asoftclip=type=tanh:threshold=0.8,alimiter=limit=0.92:level=false")
SR = 48000


def load(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, "<f4").copy()


def gaps(audio, win=int(SR * 0.02), rel_db=-28, min_frames=3):
    levels = np.array([np.sqrt(np.mean(audio[i:i + win] ** 2)) for i in range(0, len(audio) - win, win)])
    db = 20 * np.log10(levels + 1e-9)
    quiet = db < db.max() + rel_db
    runs, start = [], None
    for i, q in enumerate(quiet):
        if q and start is None:
            start = i
        elif not q and start is not None:
            # Only gaps followed by a strong phrase (not a trailing consonant release).
            if i - start >= min_frames and start > 0 and db[i:i + 15].max() >= db.max() - 8:
                runs.append((start * win, i * win))
            start = None
    return runs


def main():
    src, dst = sys.argv[1], sys.argv[2]
    pauses = [float(p) for p in (sys.argv[3:] or ["0.5", "0.55"])]
    audio = load(src)
    found = sorted(sorted(gaps(audio), key=lambda r: r[1] - r[0], reverse=True)[:len(pauses)])
    pieces, prev = [], 0
    for (g0, g1), pause in zip(found, pauses):
        cut = min(g0 + int(0.04 * SR), g1)   # keep soft word onsets attached to their word
        pieces += [audio[prev:cut], np.zeros(max(0, int(pause * SR) - (g1 - g0)), dtype=audio.dtype)]
        prev = cut
    pieces.append(audio[prev:])
    out = np.concatenate(pieces)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                    "-af", MASTER, dst], input=out.astype("<f4").tobytes(), check=True)
    print(f"{dst}: {len(found)} gaps stretched at " + ", ".join(f"{g0 / SR:.2f}s" for g0, _ in found))


if __name__ == "__main__":
    main()
