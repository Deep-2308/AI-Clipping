import os
import json
from google import genai

INPUT_FILE = "output/transcript.json"
OUTPUT_FILE = "output/clip_candidates.json"

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set")

# Load transcript
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    transcript = json.load(f)

# Convert transcript into readable text
transcript_text = "\n".join(
    f"[{segment['start']:.2f}s - {segment['end']:.2f}s] {segment['text']}"
    for segment in transcript["segments"]
)

client = genai.Client(api_key=API_KEY)

prompt = f"""
You are an expert short-form video editor.

Analyze the following transcript and identify the most interesting
moments that could become YouTube Shorts, Instagram Reels, or TikTok clips.

Look for:
- Strong hooks
- Surprising statements
- Emotional moments
- Useful insights
- Curiosity
- Storytelling
- Contrarian ideas
- Funny or memorable moments
- Statements that can stand alone without additional context

Rules:
1. Return only JSON.
2. Each clip should normally be between 15 and 60 seconds.
3. Do not invent dialogue.
4. Use only timestamps that exist in the transcript.
5. The clip must contain a coherent section of the conversation.
6. Score each clip from 0 to 100.
7. If there are no good clips, return an empty clips array.

Return exactly this structure:

{{
  "clips": [
    {{
      "start": 0.0,
      "end": 30.0,
      "score": 85,
      "hook": "Short hook describing the opening",
      "reason": "Why this moment could work as a short-form clip",
      "title": "Suggested short title"
    }}
  ]
}}

Transcript:

{transcript_text}
"""

print("Sending transcript to Gemini...")
print(f"Transcript segments: {len(transcript['segments'])}")

response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents=prompt
)

raw_response = response.text.strip()

# Remove markdown code fences if Gemini adds them
if raw_response.startswith("```"):
    lines = raw_response.splitlines()

    if lines[0].startswith("```"):
        lines = lines[1:]

    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    raw_response = "\n".join(lines).strip()

# Validate JSON
try:
    result = json.loads(raw_response)
except json.JSONDecodeError as e:
    print("\nGemini returned invalid JSON:")
    print(raw_response)
    raise RuntimeError(f"Could not parse Gemini response as JSON: {e}")

# Basic validation
if "clips" not in result:
    raise RuntimeError("Gemini response does not contain a 'clips' array")

# Save result
os.makedirs("output", exist_ok=True)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print()
print("=" * 60)
print("CLIP ANALYSIS COMPLETE")
print("=" * 60)
print(f"Candidate clips: {len(result['clips'])}")
print(f"Saved to: {OUTPUT_FILE}")
print("=" * 60)

for i, clip in enumerate(result["clips"], 1):
    print()
    print(f"Clip #{i}")
    print(f"Time: {clip['start']}s -> {clip['end']}s")
    print(f"Score: {clip['score']}")
    print(f"Hook: {clip['hook']}")
    print(f"Title: {clip['title']}")
