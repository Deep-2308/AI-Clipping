import os
import subprocess

INPUT_FILE = "output/clips/clip_01.mp4"
OUTPUT_FILE = "output/clips/clip_01_vertical.mp4"

os.makedirs("output/clips", exist_ok=True)

print("Rendering vertical 9:16 video...")
print(f"Input:  {INPUT_FILE}")
print(f"Output: {OUTPUT_FILE}")

command = [
    "ffmpeg",
    "-y",
    "-i", INPUT_FILE,

    # Center-crop 16:9 → 9:16
    "-vf",
    "crop=ih*9/16:ih,scale=1080:1920",

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
print("VERTICAL RENDER COMPLETE")
print("=" * 60)
print(f"Saved: {OUTPUT_FILE}")
print("=" * 60)
