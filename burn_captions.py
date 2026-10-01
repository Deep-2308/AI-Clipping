import os
import subprocess

INPUT_FILE = "output/clips/clip_01_vertical.mp4"
SUBTITLE_FILE = "output/captions.ass"
OUTPUT_FILE = "output/clips/clip_01_captioned.mp4"

print("Burning captions into vertical video...")
print(f"Video:     {INPUT_FILE}")
print(f"Captions:  {SUBTITLE_FILE}")
print(f"Output:    {OUTPUT_FILE}")

command = [
    "ffmpeg",
    "-y",
    "-i", INPUT_FILE,
    "-vf", f"ass={SUBTITLE_FILE}",
    "-c:v", "libx264",
    "-preset", "fast",
    "-crf", "20",
    "-c:a", "aac",
    "-b:a", "128k",
    OUTPUT_FILE
]

result = subprocess.run(
    command,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

if result.returncode != 0:
    print("\nFFmpeg failed:")
    print(result.stderr)
    raise SystemExit(1)

print()
print("=" * 60)
print("CAPTIONS BURNED SUCCESSFULLY")
print("=" * 60)
print(f"Saved: {OUTPUT_FILE}")
print("=" * 60)
