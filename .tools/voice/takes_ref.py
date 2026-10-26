"""takes_ref.py OUTDIR TEXT REF:NAME ... -- exag:cfg:n"""
import sys, time, torchaudio
from chatterbox.tts import ChatterboxTTS
out, text = sys.argv[1], sys.argv[2]
sep = sys.argv.index("--")
refs, specs = sys.argv[3:sep], sys.argv[sep + 1:]
model = ChatterboxTTS.from_pretrained(device="cpu")
for ref in refs:
    path, name = ref.split(":")
    for spec in specs:
        exag, cfg, n = spec.split(":")
        for take in range(int(n)):
            t = time.time()
            wav = model.generate(text, audio_prompt_path=path, exaggeration=float(exag), cfg_weight=float(cfg))
            tag = f"{name}_e{exag}_c{cfg}_t{take}"
            torchaudio.save(f"{out}/{tag}.wav", wav, model.sr)
            print(f"{tag} {wav.shape[1]/model.sr:.1f}s gen {time.time()-t:.0f}s", flush=True)
