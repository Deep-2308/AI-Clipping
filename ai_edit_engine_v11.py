import json
import os
import time

from google import genai
from google.genai import types


# ============================================================
# CONFIG
# ============================================================

MODEL = "gemini-3.5-flash-lite"

TRANSCRIPT_FILE = "output/transcript.json"
MANIFEST_FILE = "output/production_manifest_v6.json"

OUTPUT_FILE = "output/ai_edit_plan_v11.json"

CLIP_ID = "clip_01"


# ============================================================
# GEMINI
# ============================================================

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY is not set.")

client = genai.Client(api_key=api_key)


# ============================================================
# LOAD DATA
# ============================================================

with open(TRANSCRIPT_FILE, "r", encoding="utf-8") as f:
    transcript = json.load(f)

with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
    manifest = json.load(f)


segments = transcript.get("segments", [])
clips = manifest.get("clips", [])

clip = next(
    (c for c in clips if c.get("id") == CLIP_ID),
    None
)

if not clip:
    raise RuntimeError(f"{CLIP_ID} not found in manifest.")


clip_start = float(clip["start"])
clip_end = float(clip["end"])


# ============================================================
# CLIP TRANSCRIPT
# ============================================================

clip_segments = []

for segment in segments:
    start = float(segment["start"])
    end = float(segment["end"])

    if end <= clip_start:
        continue

    if start >= clip_end:
        continue

    visible_start = max(start, clip_start) - clip_start
    visible_end = min(end, clip_end) - clip_start

    text = " ".join(segment["text"].strip().split())

    if not text:
        continue

    clip_segments.append({
        "start": round(visible_start, 3),
        "end": round(visible_end, 3),
        "text": text
    })


clip_duration = round(clip_end - clip_start, 3)


# ============================================================
# PROMPT
# ============================================================

prompt = f"""
You are a professional short-form video editor and AI editing director.

Your job is to create an EDIT DECISION PLAN for a vertical short-form
video intended for YouTube Shorts, Instagram Reels and TikTok.

This is NOT a request to summarize the video.

You must decide HOW the video should be edited based on what is being said.

The final renderer will execute your decisions automatically.

============================================================
CLIP
============================================================

Clip ID:
{CLIP_ID}

Duration:
{clip_duration} seconds

============================================================
TRANSCRIPT
============================================================

{json.dumps(clip_segments, ensure_ascii=False, indent=2)}

============================================================
EDITING PHILOSOPHY
============================================================

The output must feel professionally edited.

Do NOT apply effects constantly.

Every editing decision must have a reason.

Use normal framing when nothing important is happening.

Use stronger editing when the speaker delivers:

- a hook
- an important claim
- a surprising fact
- an emotional statement
- a contrast
- a number
- a powerful phrase
- a conclusion
- a payoff

Avoid random zooms and random effects.

============================================================
FRAMING
============================================================

The source video is horizontal.

The renderer will convert it into a 9:16 composition.

Decide the appropriate framing for each section.

Possible framing values:

"wide"
"medium"
"tight"
"very_tight"

Also decide whether a punch-in should occur.

Zoom values:

1.00 = no zoom
1.05 = subtle
1.10 = noticeable
1.15 = strong
1.20 = very strong

Avoid excessive zoom.

============================================================
CAMERA MOTION
============================================================

The renderer supports simulated camera movement.

Possible values:

"static"
"push_in"
"pull_out"
"pan_left"
"pan_right"

Only use movement when it improves emphasis or pacing.

============================================================
CAPTIONS
============================================================

Captions will eventually be rendered word-by-word.

Identify words that deserve visual emphasis.

For example:

"The problem is that **nobody sees this coming**."

The important phrase should be highlighted.

For every important word or phrase, provide:

- exact text
- start time
- end time
- emphasis level

Emphasis levels:

"normal"
"strong"
"critical"

Do NOT emphasize every word.

============================================================
EDIT EVENTS
============================================================

Create editing events across the timeline.

Possible event types:

"normal"
"hook"
"emphasis"
"punch_in"
"payoff"
"transition"

Each event must contain:

start
end
type
reason

============================================================
PACING
============================================================

Identify moments where the pacing should become faster or slower.

Possible pacing:

"slow"
"normal"
"fast"

============================================================
VISUAL EMPHASIS
============================================================

For important moments, specify a visual treatment.

Possible values:

"none"
"subtle"
"strong"

The renderer may later use this for:

- scale changes
- motion
- caption animation
- glow
- flash
- blur
- emphasis effects

Do not overuse effects.

============================================================
OUTPUT REQUIREMENTS
============================================================

Return ONLY valid JSON.

No markdown.

No explanation outside JSON.

Use exactly this structure:

{{
  "clip_id": "{CLIP_ID}",
  "duration": {clip_duration},

  "overall_style": {{
    "editing_intensity": "low|medium|high",
    "caption_style": "clean_dynamic",
    "visual_style": "modern_short_form",
    "reason": "..."
  }},

  "segments": [
    {{
      "start": 0.0,
      "end": 3.0,
      "type": "hook",
      "reason": "...",

      "framing": {{
        "shot": "medium",
        "zoom_start": 1.0,
        "zoom_end": 1.1,
        "motion": "push_in"
      }},

      "pacing": "fast",

      "visual_emphasis": "strong",

      "caption": {{
        "style": "dynamic",
        "emphasis_words": [
          {{
            "text": "...",
            "level": "critical"
          }}
        ]
      }}
    }}
  ],

  "caption_emphasis": [
    {{
      "text": "...",
      "start": 0.0,
      "end": 1.0,
      "level": "strong",
      "reason": "..."
    }}
  ],

  "transitions": [
    {{
      "time": 0.0,
      "type": "none|smooth_zoom|hard_cut|fade",
      "reason": "..."
    }}
  ]
}}

IMPORTANT:

Every segment must stay within the clip duration.

Do not invent words that are not present in the transcript.

Use the transcript timestamps to make realistic timing decisions.

Do not create dozens of unnecessary events.

The edit should feel intentional and human-edited.
"""


# ============================================================
# GENERATE
# ============================================================

print()
print("=" * 60)
print("AI EDIT ENGINE V11")
print("=" * 60)
print()
print(f"Model: {MODEL}")
print(f"Clip: {CLIP_ID}")
print(f"Duration: {clip_duration}s")
print(f"Transcript segments: {len(clip_segments)}")
print()
print("Generating professional edit plan...")
print()


response = client.models.generate_content(
    model=MODEL,
    contents=prompt,
    config=types.GenerateContentConfig(
        temperature=0.4,
        response_mime_type="application/json",
        http_options=types.HttpOptions(
            timeout=60000
        )
    )
)


# ============================================================
# PARSE
# ============================================================

raw_text = response.text.strip()

try:
    edit_plan = json.loads(raw_text)
except json.JSONDecodeError as error:
    print("Gemini returned invalid JSON.")
    print()
    print(raw_text)
    raise error


# ============================================================
# BASIC VALIDATION
# ============================================================

if edit_plan.get("clip_id") != CLIP_ID:
    raise RuntimeError("Incorrect clip_id returned by AI.")

if "segments" not in edit_plan:
    raise RuntimeError("Missing segments in edit plan.")

for segment in edit_plan["segments"]:

    start = float(segment["start"])
    end = float(segment["end"])

    if start < 0:
        raise RuntimeError(f"Invalid segment start: {start}")

    if end > clip_duration + 0.1:
        raise RuntimeError(
            f"Segment exceeds clip duration: {end}"
        )

    if end <= start:
        raise RuntimeError(
            f"Invalid segment timing: {start} -> {end}"
        )


# ============================================================
# SAVE
# ============================================================

os.makedirs(
    os.path.dirname(OUTPUT_FILE),
    exist_ok=True
)

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        edit_plan,
        f,
        indent=2,
        ensure_ascii=False
    )


# ============================================================
# REPORT
# ============================================================

print("=" * 60)
print("AI EDIT PLAN GENERATED")
print("=" * 60)

print()
print(f"Clip: {CLIP_ID}")
print(
    f"Edit segments: "
    f"{len(edit_plan['segments'])}"
)

print(
    f"Caption emphasis: "
    f"{len(edit_plan.get('caption_emphasis', []))}"
)

print(
    f"Transitions: "
    f"{len(edit_plan.get('transitions', []))}"
)

print()
print("Output:")
print(OUTPUT_FILE)
print()
print("=" * 60)
