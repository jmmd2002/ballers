"""Generate expressive announcer parts with Chatterbox. Usage: gen.py OUTDIR TAG EXAGGERATION CFG [REF|-] text..."""
import sys, time, torchaudio
from chatterbox.tts import ChatterboxTTS
out, tag, exag, cfg, ref = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
model = ChatterboxTTS.from_pretrained(device="cpu")
for i, text in enumerate(sys.argv[6:]):
    t = time.time()
    wav = model.generate(text, audio_prompt_path=None if ref == "-" else ref, exaggeration=exag, cfg_weight=cfg)
    torchaudio.save(f"{out}/{tag}_part{i}.wav", wav, model.sr)
    print(f"{tag} part{i} {text!r} {time.time()-t:.0f}s", flush=True)
