import os
import json
from google import genai

INPUT_FILE = "output/transcript.json"
OUTPUT_FILE = "output/clip_candidates_v2.json"

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set")


# ---------------------------------------------------------
# Load transcript
# ---------------------------------------------------------

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    transcript = json.load(f)

segments = transcript["segments"]

if not segments:
    raise RuntimeError("Transcript contains no segments.")


# ---------------------------------------------------------
# Build conversational windows
# ---------------------------------------------------------

WINDOW_SECONDS = 45
STEP_SECONDS = 20

windows = []

start_time = segments[0]["start"]
max_time = segments[-1]["end"]

window_start = start_time

while window_start < max_time:

    window_end = window_start + WINDOW_SECONDS

    window_segments = [
        segment
        for segment in segments
        if segment["end"] > window_start
        and segment["start"] < window_end
    ]

    if window_segments:

        text = " ".join(
            segment["text"].strip()
            for segment in window_segments
        )

        actual_start = window_segments[0]["start"]
        actual_end = window_segments[-1]["end"]

        windows.append({
            "start": round(actual_start, 2),
            "end": round(actual_end, 2),
            "text": text
        })

    window_start += STEP_SECONDS


print("=" * 60)
print("PRODUCTION CLIP INTELLIGENCE ENGINE")
print("=" * 60)

print(f"Transcript segments: {len(segments)}")
print(f"Analysis windows: {len(windows)}")


# ---------------------------------------------------------
# Prepare Gemini
# ---------------------------------------------------------

client = genai.Client(api_key=API_KEY)


# ---------------------------------------------------------
# Analyze windows
# ---------------------------------------------------------

all_candidates = []

for index, window in enumerate(windows, start=1):

    print()
    print(
        f"Analyzing window {index}/{len(windows)} "
        f"({window['start']:.2f}s -> {window['end']:.2f}s)"
    )

    prompt = f"""
You are an expert short-form video editor.

Analyze this section of a long-form podcast/interview.

Your job is to determine whether this section contains a
potentially strong standalone short-form clip.

Look for:

- Strong hooks
- Curiosity
- Surprising statements
- Emotional moments
- Useful insights
- Stories
- Contrarian ideas
- Humor
- Memorable statements
- Strong opinions
- Clear explanations
- Moments that make viewers want to continue watching

A strong clip should make sense to someone who did NOT watch
the entire podcast.

IMPORTANT:

1. Do not invent dialogue.
2. Only use information contained in the transcript.
3. The clip timestamps must remain inside the supplied window.
4. Preferred clip length is 20 to 60 seconds.
5. A clip shorter than 20 seconds is acceptable only if the
   statement is exceptionally strong.
6. Do not create a clip merely because the transcript exists.
7. If the section is boring, incomplete, or lacks standalone
   value, return an empty clips array.

Score each candidate using:

hook: 0-100
curiosity: 0-100
emotion: 0-100
story: 0-100
usefulness: 0-100
standalone_value: 0-100
shareability: 0-100
visual_potential: 0-100

Calculate:

overall_score =
hook * 0.20 +
curiosity * 0.15 +
emotion * 0.10 +
story * 0.10 +
usefulness * 0.15 +
standalone_value * 0.15 +
shareability * 0.10 +
visual_potential * 0.05

Return ONLY valid JSON.

Required format:

{{
  "clips": [
    {{
      "start": 0.0,
      "end": 30.0,
      "scores": {{
        "hook": 85,
        "curiosity": 80,
        "emotion": 70,
        "story": 60,
        "usefulness": 90,
        "standalone_value": 85,
        "shareability": 80,
        "visual_potential": 70
      }},
      "overall_score": 80,
      "hook": "A short description of the opening hook",
      "reason": "Why this section could work as a short",
      "title": "Suggested short-form title"
    }}
  ]
}}

WINDOW:

Start: {window["start"]}

End: {window["end"]}

Transcript:

{window["text"]}
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt
    )

    raw = response.text.strip()

    # Remove markdown code fences
    if raw.startswith("```"):
        lines = raw.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        raw = "\n".join(lines).strip()

    try:
        result = json.loads(raw)

    except json.JSONDecodeError:
        print("WARNING: Gemini returned invalid JSON for this window.")
        continue

    candidates = result.get("clips", [])

    for candidate in candidates:

        candidate["source_window_start"] = window["start"]
        candidate["source_window_end"] = window["end"]

        all_candidates.append(candidate)


# ---------------------------------------------------------
# Remove invalid candidates
# ---------------------------------------------------------

valid_candidates = []

for clip in all_candidates:

    try:
        start = float(clip["start"])
        end = float(clip["end"])
        score = float(clip["overall_score"])

    except (KeyError, TypeError, ValueError):
        continue

    if end <= start:
        continue

    if start < 0:
        continue

    if score < 0 or score > 100:
        continue

    clip["start"] = round(start, 2)
    clip["end"] = round(end, 2)
    clip["overall_score"] = round(score, 2)

    valid_candidates.append(clip)


# ---------------------------------------------------------
# Sort by score
# ---------------------------------------------------------

valid_candidates.sort(
    key=lambda clip: clip["overall_score"],
    reverse=True
)


# ---------------------------------------------------------
# Save results
# ---------------------------------------------------------

output = {
    "source_file": transcript.get("source_file"),
    "total_candidates": len(valid_candidates),
    "clips": valid_candidates
}

os.makedirs("output", exist_ok=True)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------
# Display results
# ---------------------------------------------------------

print()
print("=" * 60)
print("CLIP INTELLIGENCE COMPLETE")
print("=" * 60)

print(f"Candidates found: {len(valid_candidates)}")
print(f"Saved: {OUTPUT_FILE}")

for index, clip in enumerate(valid_candidates, start=1):

    print()
    print(f"#{index}")
    print(
        f"{clip['start']:.2f}s -> "
        f"{clip['end']:.2f}s"
    )

    print(
        f"Overall score: "
        f"{clip['overall_score']}"
    )

    print(
        f"Title: "
        f"{clip.get('title', '')}"
    )

    print(
        f"Hook: "
        f"{clip.get('hook', '')}"
    )

print()
print("=" * 60)
