import os
import json
import time
from google import genai
from google.genai import types

INPUT_FILE = "output/transcript.json"
OUTPUT_FILE = "output/clip_candidates_v3.json"
CHECKPOINT_FILE = "output/clip_analysis_checkpoint.json"

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set")


# =========================================================
# SETTINGS
# =========================================================

WINDOW_SECONDS = 60
STEP_SECONDS = 45

MODEL = "gemini-3.5-flash-lite"

# 30-second HTTP timeout
HTTP_TIMEOUT_MS = 30000


# =========================================================
# LOAD TRANSCRIPT
# =========================================================

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    transcript = json.load(f)

segments = transcript.get("segments", [])

if not segments:
    raise RuntimeError("Transcript contains no segments.")


# =========================================================
# CREATE ANALYSIS WINDOWS
# =========================================================

max_time = segments[-1]["end"]

windows = []

window_start = 0.0

while window_start < max_time:

    window_end = min(
        window_start + WINDOW_SECONDS,
        max_time
    )

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

        windows.append({
            "start": round(window_segments[0]["start"], 2),
            "end": round(window_segments[-1]["end"], 2),
            "text": text
        })

    window_start += STEP_SECONDS


# =========================================================
# LOAD CHECKPOINT
# =========================================================

completed_windows = {}
all_candidates = []

if os.path.exists(CHECKPOINT_FILE):

    print("Checkpoint found.")
    print("Loading previous progress...")

    with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
        checkpoint = json.load(f)

    completed_windows = checkpoint.get(
        "completed_windows",
        {}
    )

    all_candidates = checkpoint.get(
        "candidates",
        []

    )

    print(
        f"Previously completed: "
        f"{len(completed_windows)} windows"
    )


# =========================================================
# GEMINI CLIENT
# =========================================================

client = genai.Client(
    api_key=API_KEY,
    http_options=types.HttpOptions(
        timeout=HTTP_TIMEOUT_MS
    )
)


# =========================================================
# MAIN ANALYSIS
# =========================================================

print()
print("=" * 60)
print("PRODUCTION CLIP INTELLIGENCE V3")
print("=" * 60)

print(f"Transcript segments: {len(segments)}")
print(f"Analysis windows: {len(windows)}")
print(f"Window size: {WINDOW_SECONDS}s")
print(f"Step size: {STEP_SECONDS}s")
print()


for index, window in enumerate(windows):

    window_id = str(index)

    # -----------------------------------------------------
    # Skip completed windows
    # -----------------------------------------------------

    if window_id in completed_windows:

        print(
            f"[{index + 1}/{len(windows)}] "
            f"SKIP - already completed"
        )

        continue


    print(
        f"[{index + 1}/{len(windows)}] "
        f"Analyzing "
        f"{window['start']:.2f}s -> "
        f"{window['end']:.2f}s"
    )


    # -----------------------------------------------------
    # Gemini prompt
    # -----------------------------------------------------

    prompt = f"""
You are an expert short-form video editor.

Analyze this section of a long-form podcast or interview.

Find moments that could become strong standalone
YouTube Shorts, Instagram Reels, or TikTok clips.

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
- Statements that make viewers want to keep watching

A strong clip should make sense without requiring the
viewer to watch the entire podcast.

RULES:

1. Do not invent dialogue.
2. Use only information from the supplied transcript.
3. Clip timestamps must remain inside this analysis window.
4. Preferred clip length is 20 to 60 seconds.
5. Shorter clips are allowed only when exceptionally strong.
6. Do not create clips simply because text exists.
7. Return an empty clips array when there is no strong moment.
8. Return ONLY valid JSON.

Score every candidate:

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

Return exactly:

{{
  "clips": [
    {{
      "start": 10.0,
      "end": 45.0,
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
      "hook": "Short description of the opening hook",
      "reason": "Why this moment works as a short-form clip",
      "title": "Suggested short-form title"
    }}
  ]
}}

WINDOW START:
{window["start"]}

WINDOW END:
{window["end"]}

TRANSCRIPT:
{window["text"]}
"""


    # -----------------------------------------------------
    # Call Gemini
    # -----------------------------------------------------

    try:

        response = client.models.generate_content(
            model=MODEL,
            contents=prompt
        )

        raw = response.text.strip()


        # -------------------------------------------------
        # Remove markdown code fences
        # -------------------------------------------------

        if raw.startswith("```"):

            lines = raw.splitlines()

            if lines and lines[0].startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            raw = "\n".join(lines).strip()


        # -------------------------------------------------
        # Parse JSON
        # -------------------------------------------------

        result = json.loads(raw)

        candidates = result.get("clips", [])


        # -------------------------------------------------
        # Validate candidates
        # -------------------------------------------------

        valid = []

        for clip in candidates:

            try:

                start = float(clip["start"])
                end = float(clip["end"])
                score = float(
                    clip["overall_score"]
                )

            except (
                KeyError,
                TypeError,
                ValueError
            ):
                continue


            # Timestamp validation

            if start < window["start"]:
                continue

            if end > window["end"]:
                continue

            if end <= start:
                continue


            # Score validation

            if score < 0 or score > 100:
                continue


            clip["start"] = round(start, 2)
            clip["end"] = round(end, 2)
            clip["overall_score"] = round(
                score,
                2
            )

            clip["source_window"] = index

            valid.append(clip)


        # -------------------------------------------------
        # Add candidates
        # -------------------------------------------------

        all_candidates.extend(valid)

        completed_windows[window_id] = {
            "status": "success",
            "candidate_count": len(valid)
        }


        print(
            f"    Candidates found: "
            f"{len(valid)}"
        )


    except Exception as e:

        print(
            f"    ERROR: {type(e).__name__}: {e}"
        )

        completed_windows[window_id] = {
            "status": "failed",
            "error": str(e)
        }


    # =====================================================
    # SAVE CHECKPOINT AFTER EVERY WINDOW
    # =====================================================

    checkpoint = {
        "source_file": transcript.get(
            "source_file"
        ),
        "completed_windows": completed_windows,
        "candidates": all_candidates
    }

    with open(
        CHECKPOINT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            checkpoint,
            f,
            indent=2,
            ensure_ascii=False
        )


    print("    Checkpoint saved.")

    time.sleep(0.5)


# =========================================================
# SORT CANDIDATES
# =========================================================

all_candidates.sort(
    key=lambda clip: clip["overall_score"],
    reverse=True
)


# =========================================================
# SAVE FINAL OUTPUT
# =========================================================

output = {
    "source_file": transcript.get(
        "source_file"
    ),
    "total_candidates": len(
        all_candidates
    ),
    "clips": all_candidates
}

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        output,
        f,
        indent=2,
        ensure_ascii=False
    )


# =========================================================
# FINAL REPORT
# =========================================================

successful = sum(
    1
    for value in completed_windows.values()
    if value.get("status") == "success"
)

failed = sum(
    1
    for value in completed_windows.values()
    if value.get("status") == "failed"
)


print()
print("=" * 60)
print("V3 ANALYSIS COMPLETE")
print("=" * 60)

print(f"Total windows: {len(windows)}")
print(f"Successful: {successful}")
print(f"Failed: {failed}")
print(f"Candidates: {len(all_candidates)}")

print()
print(f"Final output:")
print(OUTPUT_FILE)

print()
print(f"Checkpoint:")
print(CHECKPOINT_FILE)

print("=" * 60)


# =========================================================
# TOP CANDIDATES
# =========================================================

print()
print("TOP CANDIDATES")
print("-" * 60)

for index, clip in enumerate(
    all_candidates[:10],
    start=1
):

    print()
    print(
        f"#{index} "
        f"{clip['start']:.2f}s -> "
        f"{clip['end']:.2f}s"
    )

    print(
        f"Score: "
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
