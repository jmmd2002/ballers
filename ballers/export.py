"""Render a match to a vertical MP4 for Shorts/Reels.

  python -m ballers.export naruto sasuke                 # pick the best of 50 seeds
  python -m ballers.export naruto sasuke --seed 42       # a specific match
  python -m ballers.export naruto sasuke --best-of 200 --max-length 45   # cap the length

Rendering is offline (not real-time), so output is smooth regardless of PC speed.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from . import audio, gfx, registry  # noqa: E402
from .config import CANVAS_HEIGHT, CANVAS_WIDTH  # noqa: E402
from .match import Match  # noqa: E402
from .render import TEXT, Renderer  # noqa: E402

VIDEO_SIZE = (1080, 1920)
VIDEO_FPS = 60
# Intro: with the announcer, a frozen arena with "WHO WINS?" lasts until his
# "fight!" so the match starts on the word. Without, the video opens straight
# on "FIGHT!" (INTRO_TIME = 0).
INTRO_TIME = 0.0
FIGHT_FLASH = 1.2     # "FIGHT!" overlay as the match starts
OUTRO_TIME = 3.0      # minimum hold on the winner screen (longer if the winner line needs it)
CTA_KEY = "announcer/cta"     # "Who should fight next? Subscribe, and leave a comment..."
CTA_MIN_TIME = 3.0            # end card length (longer if the CTA line needs it)
CTA_TITLE = "WHO SHOULD FIGHT NEXT?"
CTA_BODY = "Subscribe & comment your fighter ideas!"


def video_dir(fighter_types) -> Path:
    """videos/<roster>/ (anime, politics, countries); mixed matchups go to videos/mixed/."""
    categories = {cls.category for cls in fighter_types}
    return Path("videos") / (categories.pop() if len(categories) == 1 else "mixed")


def score_match(match: Match, max_length: float | None = None) -> float | None:
    """Higher is better: the closest finish wins (the winner on the least HP).
    Rejects draws, and matches over max_length when a cap is given. Length is
    otherwise not a factor, so matches aren't forced to be short."""
    if match.winner is None or (max_length is not None and match.time > max_length):
        return None
    return 1 - match.winner.hp / match.winner.max_hp


def pick_seed(fighter_types, tries: int, max_length: float | None, first_seed: int) -> int:
    best_seed, best_score = None, None
    for seed in range(first_seed, first_seed + tries):
        match = Match(fighter_types, seed=seed)
        if max_length is None:
            match.run_to_end()
        else:
            match.run_to_end(max_time=max_length + 1)
        score = score_match(match, max_length)
        if score is not None and (best_score is None or score > best_score):
            best_seed, best_score = seed, score
    if best_seed is None:
        limit = f" under {max_length:.0f}s" if max_length is not None else ""
        sys.exit(f"No decisive match{limit} in {tries} seeds; try a higher --best-of"
                 + (" or --max-length." if max_length is not None else "."))
    return best_seed


def banner(surface, renderer, text, t, color=TEXT):
    """Big centered text over the arena; t in 0..1 drives the pop-in and fade."""
    size = int(60 + 40 * min(t * 4, 1))
    alpha = int(255 * min(1.0, (1 - t) * 3))
    gfx.draw_text(surface, text, size, color, bold=True, outline=5, alpha=alpha,
                  center=renderer.arena_rect.center)


CARD_DIM = 0.3        # seconds for the winner screen to dim
CARD_ZOOM = 0.45      # seconds for the card to zoom in
_card_cache: dict[int, pygame.Surface] = {}


def _card_image(width: int) -> pygame.Surface:
    """The whole end card (title + body) rendered once at full size, so it
    zooms in as one piece instead of re-wrapping while it grows."""
    if width not in _card_cache:
        lines = [(line, 56, (255, 210, 90), 4, 28) for line in gfx.wrap(CTA_TITLE, 56, width - 40, bold=True)]
        lines += [(line, 34, TEXT, 3, 14) for line in gfx.wrap(CTA_BODY, 34, width - 60, bold=True)]
        imgs = [(gfx.render_text(text, size, color, bold=True, outline=outline), gap)
                for text, size, color, outline, gap in lines]
        title_count = len(lines) - len(gfx.wrap(CTA_BODY, 34, width - 60, bold=True))
        pad = 26
        height = sum(img.get_height() + gap for img, gap in imgs) + 20 + pad * 2
        card = pygame.Surface((width, height), pygame.SRCALPHA)
        panel = card.get_rect()
        pygame.draw.rect(card, (14, 14, 22, 240), panel, border_radius=18)
        pygame.draw.rect(card, (255, 210, 90), panel, width=3, border_radius=18)
        y = pad
        for i, (img, gap) in enumerate(imgs):
            if i == title_count:
                y += 20   # space between title and body
            card.blit(img, img.get_rect(midtop=(width // 2, y)))
            y += img.get_height() + gap
        _card_cache[width] = card
    return _card_cache[width]


def end_card(surface, renderer, elapsed: float):
    """Call-to-action: the winner screen dims and the card zooms in on top."""
    veil = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    veil.fill((8, 8, 14, int(215 * min(elapsed / CARD_DIM, 1))))
    surface.blit(veil, (0, 0))
    p = min(elapsed / CARD_ZOOM, 1)
    scale = 0.15 + 0.85 * (1 + 2.2 * (p - 1) ** 3 + 1.2 * (p - 1) ** 2)   # ease-out with a small overshoot
    card = _card_image(renderer.arena_rect.width)
    size = (max(1, int(card.get_width() * scale)), max(1, int(card.get_height() * scale)))
    img = pygame.transform.smoothscale(card, size)
    img.set_alpha(int(255 * min(p * 4, 1)))
    surface.blit(img, img.get_rect(center=renderer.arena_rect.center))


def export(fighter_types, seed: int, out_path: Path, announcer: bool = False,
           outro_time: float = OUTRO_TIME, epilogue=None) -> Match:
    """epilogue(match, last_frame, cue) replaces the end card: a generator of
    VIDEO_SIZE frames played after the winner screen (e.g. the tournament
    bracket). cue(key, volume=None) schedules a sound on the frame about to be yielded."""
    pygame.init()
    canvas = pygame.Surface((CANVAS_WIDTH, CANVAS_HEIGHT))
    frame = pygame.Surface(VIDEO_SIZE)
    match = Match(fighter_types, seed=seed)
    renderer = Renderer(match)
    audio.ensure_default_sfx()
    if announcer:
        intro_key = audio.ensure_matchup_line(fighter_types)
        intro_time = max(1.0, audio.last_word_onset(intro_key))
    else:
        intro_time = INTRO_TIME
    recorder = audio.Recorder(match, time_offset=intro_time)
    if announcer:
        recorder.cues.append((0.0, intro_key, audio.VOICE_VOLUME))
    audio.SoundCues(match, recorder, announcer=announcer)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    video_tmp = out_path.with_name(out_path.stem + ".video.mp4")
    audio_tmp = out_path.with_name(out_path.stem + ".audio.wav")
    ffmpeg = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{VIDEO_SIZE[0]}x{VIDEO_SIZE[1]}",
         "-r", str(VIDEO_FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         str(video_tmp)],
        stdin=subprocess.PIPE)

    def emit(overlay=None):
        renderer.draw(canvas)
        if overlay:
            overlay(canvas)
        pygame.transform.smoothscale(canvas, VIDEO_SIZE, frame)
        ffmpeg.stdin.write(pygame.image.tobytes(frame, "RGB"))

    frame_dt = 1 / VIDEO_FPS
    steps_per_frame = max(1, round(frame_dt / match.config.physics_dt))
    frames = 0

    intro_frames = int(intro_time * VIDEO_FPS)
    for i in range(intro_frames):
        emit(lambda c, t=i / intro_frames: banner(c, renderer, "WHO WINS?", t, (255, 210, 90)))
        frames += 1

    elapsed = 0.0
    while not match.over:
        for _ in range(steps_per_frame):
            match.step()
        renderer.update(frame_dt)
        elapsed += frame_dt
        if elapsed < FIGHT_FLASH:
            emit(lambda c, t=elapsed / FIGHT_FLASH: banner(c, renderer, "FIGHT!", t, (255, 90, 60)))
        else:
            emit()
        frames += 1
        if frames % (VIDEO_FPS * 5) == 0:
            print(f"  {match.time:5.1f}s simulated", end="\r", flush=True)

    winner_line = f"announcer/{match.winner.key}_wins" if match.winner else "announcer/draw"
    outro = outro_time
    if announcer:
        outro = max(outro, audio.WINNER_DELAY + audio.duration(winner_line) + 0.8)
    for _ in range(int(outro * VIDEO_FPS)):
        renderer.update(frame_dt)
        emit()
        frames += 1

    if epilogue is not None:
        def cue(key, volume=None):
            recorder.cues.append((frames / VIDEO_FPS, key,
                                  audio.VOLUME.get(key, audio.DEFAULT_SFX_VOLUME) if volume is None else volume))
        for img in epilogue(match, frame.copy(), cue):
            ffmpeg.stdin.write(pygame.image.tobytes(img, "RGB"))
            frames += 1
    else:
        cta_time = CTA_MIN_TIME
        if announcer and audio.find(CTA_KEY):
            recorder.cues.append((frames / VIDEO_FPS, CTA_KEY, audio.VOICE_VOLUME))
            cta_time = max(cta_time, audio.duration(CTA_KEY) + 0.6)
        cta_frames = int(cta_time * VIDEO_FPS)
        for i in range(cta_frames):
            renderer.update(frame_dt)
            emit(lambda c, t=i / VIDEO_FPS: end_card(c, renderer, t))
            frames += 1

    ffmpeg.stdin.close()
    if ffmpeg.wait() != 0:
        sys.exit("ffmpeg failed")

    duration = frames / VIDEO_FPS
    used = audio.mix(recorder.cues, duration, audio_tmp)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video_tmp), "-i", str(audio_tmp),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                    "-movflags", "+faststart", str(out_path)], check=True)
    video_tmp.unlink()
    audio_tmp.unlink()

    missing = sorted({key for _, key, _ in recorder.cues if audio.find(key) is None})
    winner = match.winner.name if match.winner else "Draw"
    print(f"Saved {out_path}  ({duration:.1f}s, seed {seed}, winner: {winner}, {used} sounds)")
    if missing:
        print("No file for: " + ", ".join(missing) + f"  (add them under {audio.SOUND_DIR})")
    return match


def main():
    parser = argparse.ArgumentParser(description="Export a match as a 1080x1920 MP4.")
    parser.add_argument("fighters", nargs=2, help="fighter keys, e.g. naruto sasuke")
    parser.add_argument("--seed", type=int, help="render this exact match")
    parser.add_argument("--best-of", type=int, default=50,
                        help="when no seed is given, simulate this many and keep the most exciting")
    parser.add_argument("--first-seed", type=int, default=0, help="where --best-of starts searching")
    parser.add_argument("--max-length", type=float, default=None,
                        help="optional cap on match length in seconds when picking (default: no cap)")
    parser.add_argument("--announcer", action="store_true",
                        help="include the announcer voice (intro, winner, end card)")
    parser.add_argument("-o", "--out", type=Path, help="output file (default: videos/<roster>/<a>_vs_<b>_seed<N>.mp4)")
    args = parser.parse_args()

    types = [registry.get(k) for k in args.fighters]
    seed = args.seed
    if seed is None:
        print(f"Searching {args.best_of} matches for the best one...")
        seed = pick_seed(types, args.best_of, args.max_length, args.first_seed)
    out = args.out or video_dir(types) / f"{args.fighters[0]}_vs_{args.fighters[1]}_seed{seed}.mp4"
    print(f"Rendering seed {seed} -> {out}")
    export(types, seed, out, announcer=args.announcer)


if __name__ == "__main__":
    main()
