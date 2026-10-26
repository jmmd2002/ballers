# Ballers

Bouncing-ball battle simulator (anime tournament theme) that renders vertical
1080x1920 videos for YouTube Shorts / Instagram Reels. Python + pygame-ce,
running on a Steam Deck (Linux). The countryball roster has a tournament
bracket (Countryball Cup, `ballers/tournament.py`).

## Commands

Always use the project virtualenv (`.venv`). `main.py` re-launches itself with
it, but `-m` modules don't, so call `.venv/bin/python` explicitly.

```sh
.venv/bin/python main.py                          # menu: pick 2 fighters, then watch live
.venv/bin/python main.py naruto sasuke --seed 7   # straight into a match
.venv/bin/python main.py --list                   # registered fighters
.venv/bin/python -m ballers.sim naruto sasuke -n 300            # headless win rates
.venv/bin/python -m ballers.export naruto sasuke                # best of 50 seeds -> videos/<roster>/*.mp4
.venv/bin/python -m ballers.export naruto sasuke --seed 24      # exact match
.venv/bin/python -m ballers.announcer_gen [--force]          # announcer lines (Piper TTS)
.venv/bin/python -m ballers.tournament                 # cup progress + next playable matches
.venv/bin/python -m ballers.tournament play            # export next cup match video, record winner
.venv/bin/python -m ballers.tournament bracket out.png # full bracket image
```

VS Code's built-in video preview can't decode AAC, so exported mp4s look silent
there. Play them with `ffplay videos/<roster>/<file>.mp4` or the system player instead.

Headless rendering for checking visuals: set `SDL_VIDEODRIVER=dummy`, build a
`MatchScene`/`Renderer`, and `pygame.image.save` the canvas, or pull frames from
an exported mp4 with ffmpeg. There is no test suite; verify with the sim,
event logs (subscribe to `match.bus`), and screenshots.

## Architecture (ballers/)

- `match.py`: `Match` is pure simulation, with no rendering. Fixed timestep
  (`physics_dt` 1/120), seeded RNG (`match.rng`), so **same seed = same match**.
  Export relies on this. Never use the global `random` or wall-clock time in
  simulation code.
- `entity.py`: `Entity` is the base for everything in the arena: HP, damage,
  `DamageType`, resistances (x0.5), weaknesses (x2), immunities (x0), tags,
  team/owner, shape (`circle`/`cone`), `solid`, `dies_on_hit`, `hit_cooldown`,
  `lifetime`, `layer`, `death_effect`, sound keys. `Ball` = solid, constant speed,
  bounces.
- `fighter.py`: `Fighter(Ball)` is a selectable character with an HP bar and
  `ability_types`. Only fighters decide the winner.
- `ability.py`: auto-triggers when cooldown is done, `owner.can_cast`, and
  `can_activate()`. Override `cast()`. `voice` is derived from the name.
- `status.py`: status conditions on any entity (`entity.add_status/
  remove_status/get_status/has_status`). A `Status` has a duration (`None` =
  until `end()`), `source`, flags `immobile` / `blocks_casting`, `speed_mult`,
  HUD `label` (shown on the fighter's status line), apply `sound`, and hooks
  `on_apply/on_update/on_expire/draw`. Built-ins: `Channeling`, `Stunned`,
  `DamageOverTime`, `Grasped`. Immobile entities have infinite mass in collisions.
- Damage over time: `match.deal_damage(..., continuous=True)` every step. The
  renderer sums it into one popup per 0.4 s and audio throttles its hit sound.
- `physics.py`: wall/ball collisions, circle-vs-cone overlap.
- Contact rule (in `Match._contact`): when entities of different teams start
  touching, both deal `damage` of their `damage_type` simultaneously, then
  `dies_on_hit` entities are destroyed. `Entity.can_damage(match, target)` can
  veto a hit. Most ability interactions come from this rule plus
  HP/immunities, not special cases.
- `match.nearest_enemy(entity, cls, reach)` targets enemy *bodies* (solid
  entities: fighters, clones), never projectiles like rocks.
- `events.py`: `EventBus`. The match emits events; `render.py` (visual
  effects, HUD) and `audio.py` (sound cues) subscribe. Keep the simulation
  ignorant of rendering and audio.
- `registry.py`: auto-imports every module not starting with `_` in the
  roster packages (`PACKAGES`: `balls/` anime, `politics/`, `countries/`).
  **Add a fighter = add one file there with an `@register` class.** Each
  fighter's `category` picks its menu tab (TAB key / click). Shared helpers go
  in `_`-prefixed modules (e.g. `balls/_shinobi.py`).
- `render.py`: draws on a fixed 540x960 canvas (`config.py`); the window and
  the exporter scale it. Entities draw themselves via `draw(surface, origin)`.
- `export.py`: offline frame-by-frame render piped to ffmpeg (libx264),
  "WHO WINS?" intro, outro hold, sound mixed from recorded cues, then muxed.
  `--best-of` picks the closest finish (winner on the least HP); match length is
  not a factor unless `--max-length` caps it (no cap by default; user does not
  want videos forced short). Never re-render or delete existing videos unasked.
- `audio.py` / `sfx_gen.py`: sound cues -> `LivePlayer` (pygame.mixer) or
  `Recorder` + `mix()` (numpy). Files: `sounds/sfx/<name>.*` (defaults are
  generated if missing) and `sounds/voices/<fighter_key>/<ability_voice>.*`
  (user-supplied; missing files are skipped silently).
- Announcer files in `sounds/announcer/`: `<a>_vs_<b>.wav` (intro),
  `<fighter>_wins.wav`, `draw.wav`, `cta.wav` (end card line).
  **The approved voice is Chatterbox** (expressive TTS), not Piper. The user
  rejected Piper as not epic, any echo/reverb as weird, and high-pitched voices.
  Workflow (tools live in `.tools/`, ~3 GB, CPU-only, ~40-60 s per line):
  - `TMPDIR=.tools/tmp HF_HOME=.tools/hf .tools/chatterbox/bin/python .tools/voice/lines.py OUT .tools/voice/ref_am_onyx.wav 0.9 0.4 3 "key=text"`
    (reference = synthetic Kokoro "onyx" voice, exaggeration 0.9, cfg 0.4).
  - Short lines garble or go high-pitched; use full phrases: "Naruto versus
    Sasuke! Who wins? FIGHT!", "And the winner is... Naruto!". Always make
    several takes, then pick by Whisper transcript (`.tools/whisper` venv,
    faster-whisper; decode with ffmpeg to a numpy array, its PyAV is broken;
    keep models in `.tools/hf`, /tmp is a small tmpfs) and median
    pitch (`.tools/voice/pitch.py`, deeper ~100-125 Hz is preferred).
  - `.venv/bin/python .tools/voice/finish.py IN.wav sounds/announcer/KEY.wav [pauses...]`
    stretches the longest gaps into pauses and applies the master (compression,
    bass, soft clip, no reverb). Check the pause landed in the right place.
  - `announcer_gen.py` (Piper) still exists as a fallback and only fills in
    missing files; it never overwrites the Chatterbox lines.
- **Exports have no announcer by default** (user's choice); pass `--announcer`
  to include it. Without it there is no intro: the video opens on "FIGHT!" with
  the match already moving -> 3 s winner screen -> 3 s silent end card
  "WHO SHOULD FIGHT NEXT?". With it: the intro lasts until the detected onset of "fight"
  (`audio.last_word_onset`), the winner line plays 0.5 s after the KO (outro
  stretches to fit), and the `cta` line plays over the end card. Voice and
  announcer cues duck the SFX; a fighter's new voice line cuts off their
  previous one (`audio.speaker`), live and in exports. The live game still plays the announcer and
  freezes until "fight!".

## Conventions and user preferences

- The match screen must stay clean for video: no seed, controls, timer, or
  numbers on balls. Only title, HP bars, status line, arena, and the
  ability cooldown panel (bars only, no seconds) under the arena.
- After changing numbers, re-balance with `ballers.sim` (aim for ~50/50 and
  ~30-45 s matches) and report the win rates.
- Current fighters: Naruto (Shadow Clone Jutsu; Rasengan, held on the side
  facing the nearest enemy fighter) and Sasuke (Sharingan: dispels clones and
  copies one ready Rasengan; Fireball Jutsu: waits until an enemy ball,
  clones included, is in range, then roots him and fires a cone at it).
  Levi (100 HP; his blade replaces the bump: 10 slashing on contact. ODM Gear:
  cable to the nearest enemy, reels in, 20 slashing, springs back. Flurry of
  Slashes: 20 slashing/s to every enemy entity within reach, built up per
  target and landed as 1-damage cuts (each gets a slash mark), lasts until 1 s
  with nothing around) and Beast Titan (500 HP, big and slow. Rock Throw: 3
  boulders in a cone that shatter on walls/enemies into shards ricocheting
  off what they hit. Grab: arm grips the nearest enemy body, which can't
  move/cast; the 10/s squeeze lands as one hit every 2 s (`DamageOverTime`
  `interval`), lost if the hand is cut first. Cutting the hand frees them). The user set Levi's
  and the Titan's HP and ability damage numbers (boulders 20 dmg, shards 10,
  all rocks 1 HP so Flurry cuts them at once). Levi vs Titan doesn't need to
  be 50/50 (user's call; ~14/85 now), but export a seed Levi wins (seed 29). They are tuned for each other and crush the shinobi in cross-matchups.
  Ball impact damage is 5 for every ball including clones (Levi's blade is the
  exception).
- Countryballs live in `ballers/countries/` (own roster, `registry.PACKAGES`),
  drawn as flag-in-a-circle with white eyes (`countries/_countryball.py`).
  Abilities come from culture/geography, never wars or conflicts. All 203
  countries (193 UN members + Palestine, Vatican, Taiwan, Kosovo, Western
  Sahara, Northern Cyprus, Somaliland, Abkhazia, South Ossetia, Transnistria)
  are in `countries/_roster.py`, with flags drawn in code in `countries/_flags.py`
  (user chose code-drawn over downloaded images; emblems are simplified). A new
  country fighter's `key` must match its roster key; the flag comes for free.
  The roster also has 12 meme entries (`MEMES`: Glaggle Land, Ohio, Sealand,
  Bir Tawil, Flat Earth, Area 51, Bermuda Triangle, Roman Empire, Tralalero
  Land, Tringapore, Liberland, Null Island). The user wants famous internet
  memes, not obscure/boring places (no Antarctica) and only one US state (Ohio);
  propose new ones before adding. Glaggle = the classic yellow smiley emoji;
  `_flags.OWN_FACE` flags (glaggle, alien) skip the countryball eyes.
  Hate-symbol memes (Kekistan, Reichtangle) and franchise IP are left out.
- Countryball Cup (`tournament.py` model/CLI, `bracket.py` drawing): 256-slot
  single elimination (215 entries, 41 first-round byes), seeded draw saved with
  all results in `tournaments/countries.json` (don't regenerate it: results
  depend on it). Countries added to the roster later are slotted into byes on
  load (`Tournament.add_entrants`), never next to an already-played match.
  Libya vs Armenia is the fixed opening match. One Short per match; a match is
  playable once both countries have fighters. Video (user's choice): straight
  into FIGHT! (no bracket intro) -> match -> short winner hold -> cut to the
  zoomed bracket, winner's flag rides the line to the next slot -> zoom out to
  the full bracket -> "WHO WINS NEXT?" card. Hooked in via `export(epilogue=...)`.
  Libya (Ghibli Sandstorm: aura that slows and grinds enemies, shape "area"
  so it never triggers the contact rule; Pillars of Leptis Magna: two
  immovable columns as cover) vs Armenia (Pomegranate Burst: bursts into 6
  seeds; Duduk Song: cone that stuns and blows sandstorms away). ~50/50, ~42 s.
- Politicians live in `ballers/politics/` (satire roster). Faces are real
  photos cut into circles (`politics/_common.py`, `Politician.face_crop`),
  from Wikimedia Commons in `assets/faces/` (see SOURCES.txt: credit Agência
  Senado / Palácio do Planalto in video descriptions). Never clone or imitate
  their real voices with TTS; real clips of them (myinstants, see
  sounds/voices/SOURCES.txt) are what the user wants. Some politics SFX in
  sounds/sfx/ are downloaded too, not generated. Flávio Bolsonaro (Motociata: homing charge, hits once for
  20, then tired; Arminha: 3-bullet burst, 4 each) vs Lula (Discurso: stands and talks,
  then deals 20, puts nearby enemies to sleep (7 s cooldown) and knocks Flávio off the bike; Picanha e
  Cervejinha: stops to heal 10/s, broken by hits >= 8; Volta por Cima: passive,
  once per match back from < 20% HP with +22 and 1.5 s immunity, a red "L" zooms out on the "L" of "Faz o L!"; Picanha waits for that line to end). Both 100 HP (user's choice).
  ~50/44 (6% draws), ~41 s.
- Export end card: the winner screen dims and the "WHO SHOULD FIGHT NEXT?"
  card (pre-rendered once, on its own panel) zooms in as one image. Don't
  re-wrap text per frame; it looks like it's being typed out.
- Voice clips in sounds/voices/ were downloaded from myinstants at the user's
  request for non-monetized videos (see sounds/voices/SOURCES.txt). They are
  copyrighted anime audio (Naruto and Attack on Titan); remind the user before anything monetized.
  Generated SFX in sounds/sfx/ are original.
