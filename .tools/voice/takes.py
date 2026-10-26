"""Generate several takes of one line with Chatterbox. Usage: takes.py OUTDIR PREFIX TEXT exag:cfg[:n] ..."""
import sys, time, torchaudio
from chatterbox.tts import ChatterboxTTS
out, prefix, text = sys.argv[1], sys.argv[2], sys.argv[3]
model = ChatterboxTTS.from_pretrained(device="cpu")
for spec in sys.argv[4:]:
    parts = spec.split(":")
    exag, cfg, n = float(parts[0]), float(parts[1]), int(parts[2]) if len(parts) > 2 else 1
    for take in range(n):
        t = time.time()
        wav = model.generate(text, exaggeration=exag, cfg_weight=cfg)
        name = f"{prefix}_e{exag}_c{cfg}_t{take}"
        torchaudio.save(f"{out}/{name}.wav", wav, model.sr)
        print(f"{name} {wav.shape[1]/model.sr:.1f}s gen {time.time()-t:.0f}s", flush=True)
