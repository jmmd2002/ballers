import sys, os, subprocess, numpy as np
def f0(path):
    raw = subprocess.run(["ffmpeg","-v","error","-i",path,"-f","f32le","-ac","1","-ar","16000","-"],capture_output=True).stdout
    a = np.frombuffer(raw,"<f4"); w = 1024; out = []
    for i in range(0, len(a)-w, 256):
        x = a[i:i+w]
        if np.sqrt(np.mean(x**2)) < 0.02: continue
        ac = np.correlate(x, x, "full")[w-1:]; lo, hi = 16000//300, 16000//60
        lag = lo + np.argmax(ac[lo:hi])
        if ac[lag] > 0.3*ac[0]: out.append(16000/lag)
    return np.median(out) if out else 0
for p in sys.argv[1:]:
    d = len(subprocess.run(["ffmpeg","-v","error","-i",p,"-f","f32le","-ac","1","-ar","16000","-"],capture_output=True).stdout)/4/16000
    print(f"{os.path.basename(p):22s} {d:.1f}s pitch {f0(p):4.0f} Hz")
