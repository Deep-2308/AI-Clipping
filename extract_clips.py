import json
import os
import subprocess

INPUT_VIDEO = "input/test.mp4"
CANDIDATES_FILE = "output/clip_candidates.json"
OUTPUT_DIR = "output/clips"

os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(CANDIDATES_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

clips = data.get("clips", [])

if not clips:
    print("No clip candidates found.")
    raise SystemExit(0)

print(f"Found {len(clips)} clip candidate(s).")

for index, clip in enumerate(clips, start=1):
    start = float(clip["start"])
    end = float(clip["end"])

    if end <= start:
        print(f"Skipping Clip #{index}: invalid timestamps.")
        continue

    duration = end - start

    output_file = os.path.join(
        OUTPUT_DIR,
        f"clip_{index:02d}.mp4"
    )

    print()
    print(f"Extracting Clip #{index}")
    print(f"Start: {start:.2f}s")
    print(f"End:   {end:.2f}s")
    print(f"Length: {duration:.2f}s")

    command = [
        "ffmpeg",
        "-y",
        "-ss", str(start),
        "-i", INPUT_VIDEO,
        "-t", str(duration),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-preset", "fast",
        "-crf", "20",
        output_file
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:
        print("FFmpeg failed:")
        print(result.stderr)
        continue

    print(f"Saved: {output_file}")

print()
print("=" * 60)
print("CLIP EXTRACTION COMPLETE")
print("=" * 60)
