"""lines.py OUTDIR REF EXAG CFG TAKES key=text ... - several takes per line, one model load."""
import sys, time, torchaudio
from chatterbox.tts import ChatterboxTTS
out, ref, exag, cfg, takes = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), int(sys.argv[5])
model = ChatterboxTTS.from_pretrained(device="cpu")
for spec in sys.argv[6:]:
    key, text = spec.split("=", 1)
    for t in range(takes):
        start = time.time()
        wav = model.generate(text, audio_prompt_path=ref, exaggeration=exag, cfg_weight=cfg)
        torchaudio.save(f"{out}/{key}_t{t}.wav", wav, model.sr)
        print(f"{key}_t{t} {time.time()-start:.0f}s", flush=True)
