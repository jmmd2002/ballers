#!/bin/sh
# assemble.sh TAG -> sounds/announcer_samples/<TAG>.mp3
# Trims each part, masters it (compression, low end, light saturation, no echo)
# and joins the parts with dramatic pauses.
set -e
cd "$(dirname "$0")/../.."
OUT=.tools/voice/out
TAG=$1
MASTER="silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,highpass=f=70,bass=g=5:f=110,acompressor=threshold=-26dB:ratio=6:attack=2:release=120:makeup=7,asoftclip=type=tanh:threshold=0.8,alimiter=limit=0.92:level=false"
for i in 0 1 2; do
  ffmpeg -v error -y -i "$OUT/${TAG}_part$i.wav" -af "$MASTER" -ar 48000 -ac 1 "$OUT/${TAG}_m$i.wav"
done
ffmpeg -v error -y -f lavfi -t 0.45 -i anullsrc=r=48000:cl=mono "$OUT/pause_a.wav"
ffmpeg -v error -y -f lavfi -t 0.55 -i anullsrc=r=48000:cl=mono "$OUT/pause_b.wav"
ffmpeg -v error -y -i "$OUT/${TAG}_m0.wav" -i "$OUT/pause_a.wav" -i "$OUT/${TAG}_m1.wav" -i "$OUT/pause_b.wav" -i "$OUT/${TAG}_m2.wav" \
  -filter_complex "[0][1][2][3][4]concat=n=5:v=0:a=1" "sounds/announcer_samples/$TAG.mp3"
echo "sounds/announcer_samples/$TAG.mp3"
