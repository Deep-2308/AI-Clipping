import json
import os
import pysubs2

INPUT_FILE = "output/transcript.json"
OUTPUT_FILE = "output/captions.ass"

# Load transcript
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    transcript = json.load(f)

subs = pysubs2.SSAFile()

# Video resolution
subs.info["PlayResX"] = "1080"
subs.info["PlayResY"] = "1920"

# Caption style
style = pysubs2.SSAStyle()

style.fontname = "Arial"
style.fontsize = 70

# White text
style.primarycolor = pysubs2.Color(255, 255, 255)

# Black outline
style.outlinecolor = pysubs2.Color(0, 0, 0)

style.outline = 4
style.shadow = 1

# Bottom-center
style.alignment = pysubs2.Alignment.BOTTOM_CENTER

# Margins
style.marginl = 80
style.marginr = 80
style.marginv = 180

subs.styles["Default"] = style

# Add transcript segments
for segment in transcript["segments"]:
    start_ms = int(segment["start"] * 1000)
    end_ms = int(segment["end"] * 1000)

    text = segment["text"].strip()

    if not text:
        continue

    event = pysubs2.SSAEvent(
        start=start_ms,
        end=end_ms,
        text=text,
        style="Default"
    )

    subs.events.append(event)

# Create output directory
os.makedirs("output", exist_ok=True)

# Save ASS file
subs.save(OUTPUT_FILE)

print()
print("=" * 60)
print("CAPTIONS GENERATED")
print("=" * 60)
print(f"Caption events: {len(subs.events)}")
print(f"Saved: {OUTPUT_FILE}")
print("=" * 60)
