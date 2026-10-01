import os
import json
import time

from google import genai
from google.genai import types
from google.genai import errors


# =========================================================
# FILES
# =========================================================

INPUT_FILE = "output/transcript.json"
OLD_CHECKPOINT = "output/clip_analysis_checkpoint.json"
CHECKPOINT_FILE = "output/clip_analysis_checkpoint_v4.json"
OUTPUT_FILE = "output/clip_candidates_v4.json"


# =========================================================
# CONFIG
# =========================================================

MODEL = "gemini-3.5-flash-lite"

WINDOW_SECONDS = 60
STEP_SECONDS = 45

MAX_RETRIES = 4

RETRY_DELAYS = [3, 8, 16, 30]

HTTP_TIMEOUT_MS = 60000


# =========================================================
# API KEY
# =========================================================

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set")


# =========================================================
# LOAD TRANSCRIPT
# =========================================================

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    transcript = json.load(f)

segments = transcript.get("segments", [])

if not segments:
    raise RuntimeError("Transcript contains no segments.")


# =========================================================
# CREATE WINDOWS
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
            "start": round(
                window_segments[0]["start"],
                2
            ),
            "end": round(
                window_segments[-1]["end"],
                2
            ),
            "text": text
        })

    window_start += STEP_SECONDS


# =========================================================
# LOAD OLD CHECKPOINT
# =========================================================

completed_windows = {}
all_candidates = []

if os.path.exists(OLD_CHECKPOINT):

    print("Found V3 checkpoint.")
    print("Recovering successful windows...")

    with open(
        OLD_CHECKPOINT,
        "r",
        encoding="utf-8"
    ) as f:

        old_checkpoint = json.load(f)


    old_status = old_checkpoint.get(
        "completed_windows",
        {}
    )

    old_candidates = old_checkpoint.get(
        "candidates",
        []
    )


    # Only recover SUCCESS windows.
    for window_id, status in old_status.items():

        if status.get("status") == "success":

            completed_windows[window_id] = status


    all_candidates = old_candidates.copy()


    print(
        f"Recovered successful windows: "
        f"{len(completed_windows)}"
    )

    print(
        f"Recovered candidates: "
        f"{len(all_candidates)}"
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
# PROMPT FUNCTION
# =========================================================

def build_prompt(window):

    return f"""
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
3. Clip timestamps must remain inside this window.
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


# =========================================================
# JSON CLEANER
# =========================================================

def clean_json(raw):

    raw = raw.strip()

    if raw.startswith("```"):

        lines = raw.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        raw = "\n".join(lines).strip()

    return raw


# =========================================================
# GEMINI REQUEST WITH RETRIES
# =========================================================

def analyze_window(window):

    prompt = build_prompt(window)

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            print(
                f"    Gemini attempt "
                f"{attempt}/{MAX_RETRIES}"
            )

            response = client.models.generate_content(
                model=MODEL,
                contents=prompt
            )

            raw = clean_json(response.text)

            result = json.loads(raw)

            return result


        except (
            errors.ServerError,
            errors.APIError,
            json.JSONDecodeError
        ) as error:

            last_error = error

            print(
                f"    Attempt failed: "
                f"{type(error).__name__}: {error}"
            )

            if attempt < MAX_RETRIES:

                delay = RETRY_DELAYS[
                    min(
                        attempt - 1,
                        len(RETRY_DELAYS) - 1
                    )
                ]

                print(
                    f"    Waiting {delay}s "
                    f"before retry..."
                )

                time.sleep(delay)


    raise RuntimeError(
        f"All retry attempts failed: {last_error}"
    )


# =========================================================
# VALIDATE CANDIDATES
# =========================================================

def validate_candidates(
    candidates,
    window,
    window_index
):

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


        if start < window["start"]:
            continue

        if end > window["end"]:
            continue

        if end <= start:
            continue

        if score < 0 or score > 100:
            continue


        clip["start"] = round(start, 2)
        clip["end"] = round(end, 2)

        clip["overall_score"] = round(
            score,
            2
        )

        clip["source_window"] = window_index

        valid.append(clip)


    return valid


# =========================================================
# SAVE CHECKPOINT
# =========================================================

def save_checkpoint():

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


# =========================================================
# MAIN
# =========================================================

print()
print("=" * 60)
print("PRODUCTION CLIP INTELLIGENCE V4")
print("=" * 60)

print(
    f"Transcript segments: "
    f"{len(segments)}"
)

print(
    f"Analysis windows: "
    f"{len(windows)}"
)

print(
    f"Recovered successful windows: "
    f"{len(completed_windows)}"
)

print()


for index, window in enumerate(windows):

    window_id = str(index)


    # -----------------------------------------------------
    # SKIP ONLY SUCCESSFUL WINDOWS
    # -----------------------------------------------------

    if (
        window_id in completed_windows
        and completed_windows[
            window_id
        ].get("status") == "success"
    ):

        print(
            f"[{index + 1}/{len(windows)}] "
            f"SKIP - already successful"
        )

        continue


    print(
        f"[{index + 1}/{len(windows)}] "
        f"Analyzing "
        f"{window['start']:.2f}s -> "
        f"{window['end']:.2f}s"
    )


    # -----------------------------------------------------
    # ANALYZE WITH RETRIES
    # -----------------------------------------------------

    try:

        result = analyze_window(window)

        candidates = result.get(
            "clips",
            []
        )

        valid = validate_candidates(
            candidates,
            window,
            index
        )

        all_candidates.extend(valid)


        completed_windows[
            window_id
        ] = {
            "status": "success",
            "candidate_count": len(valid)
        }


        print(
            f"    Candidates found: "
            f"{len(valid)}"
        )


    except Exception as error:

        # IMPORTANT:
        # Failed windows are NOT marked completed.

        print(
            f"    FINAL FAILURE: "
            f"{type(error).__name__}: {error}"
        )

        completed_windows[
            window_id
        ] = {
            "status": "failed",
            "error": str(error)
        }


    # -----------------------------------------------------
    # SAVE AFTER EVERY WINDOW
    # -----------------------------------------------------

    save_checkpoint()

    print("    Checkpoint saved.")

    time.sleep(0.5)


# =========================================================
# REMOVE OLD DUPLICATES
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
    for status in completed_windows.values()
    if status.get("status") == "success"
)

failed = sum(
    1
    for status in completed_windows.values()
    if status.get("status") == "failed"
)


print()
print("=" * 60)
print("V4 ANALYSIS COMPLETE")
print("=" * 60)

print(
    f"Total windows: "
    f"{len(windows)}"
)

print(
    f"Successful: "
    f"{successful}"
)

print(
    f"Failed: "
    f"{failed}"
)

print(
    f"Candidates: "
    f"{len(all_candidates)}"
)

print()
print(
    f"Output: "
    f"{OUTPUT_FILE}"
)

print(
    f"Checkpoint: "
    f"{CHECKPOINT_FILE}"
)

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
