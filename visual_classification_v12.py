import json
import base64
from pathlib import Path

import cv2
from google import genai
from google.genai import types


VIDEO = "output/final_clips/clip_01_raw.mp4"
SEGMENTS = "output/visual_segments_v12.json"
OUTPUT = "output/visual_classification_v12.json"

MODEL = "gemini-3.5-flash-lite"


def extract_frame(video_path, timestamp):
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_number = int(timestamp * fps)

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

    success, frame = cap.read()
    cap.release()

    if not success:
        raise RuntimeError(f"Could not extract frame at {timestamp}s")

    ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

    if not ok:
        raise RuntimeError("Could not encode frame")

    return encoded.tobytes()


def classify_segment(client, segment, image_bytes):
    prompt = f"""
You are a professional short-form documentary video editor.

Analyze this representative frame from visual segment {segment["segment_id"]}.

Segment timing:
{segment["start"]:.2f}s to {segment["end"]:.2f}s

Classify the visual content for an automated 9:16 video editor.

Return ONLY valid JSON with exactly these fields:

{{
  "visual_type": "speaker|b_roll|map|graphic|multiple_people|unknown",
  "people_present": true,
  "people_count_estimate": 0,
  "framing": "wide|medium|close_up|unknown",
  "subject_position": "left|center|right|unknown",
  "visual_importance": "low|medium|high",
  "recommended_treatment": "speaker_crop|full_frame|slow_push_in|controlled_pan|preserve_composition|unknown",
  "reason": "short explanation"
}}

Important:
- Do not invent objects that are not visible.
- If a person is visible, determine whether the frame primarily focuses on that person.
- If the frame contains documentary footage such as ships, landscapes, maps, or other contextual footage, classify it as b_roll unless it is clearly a map or graphic.
- Do not recommend aggressive zooming if the important subject would be cropped.
"""

    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/jpeg",
            ),
            prompt,
        ],
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )

    text = response.text.strip()

    print(f"  Gemini raw response: {text[:500]}")

    parsed = json.loads(text)

    if isinstance(parsed, dict):
        return parsed

    if isinstance(parsed, list):
        if len(parsed) >= 1 and isinstance(parsed[0], dict):
            return parsed[0]

    return {
    "visual_type": "unknown",
    "people_present": False,
    "people_count_estimate": 0,
    "framing": "unknown",
    "subject_position": "unknown",
    "visual_importance": "low",
    "recommended_treatment": "unknown",
    "reason": "Unexpected Gemini response structure."
}

def main():
    print("Loading visual segments...")

    with open(SEGMENTS, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data["visual_segments"]

    print(f"Segments to classify: {len(segments)}")

    client = genai.Client()

    classifications = []

    for segment in segments:
        midpoint = (
            segment["start"] + segment["end"]
        ) / 2

        print(
            f"Segment {segment['segment_id']:02d}: "
            f"{segment['start']:.2f}s -> "
            f"{segment['end']:.2f}s "
            f"(frame @ {midpoint:.2f}s)"
        )

        image_bytes = extract_frame(
            VIDEO,
            midpoint,
        )

        classification = classify_segment(
    client,
    segment,
    image_bytes,
)

        classifications.append({
    "segment_id": segment["segment_id"],
    "start": segment["start"],
    "end": segment["end"],
    "duration": segment["duration"],
    "classification": classification,
})

        print(
            f"  Type: "
            f"{classification['visual_type']}"
)

    result = {
        "video": VIDEO,
        "model": MODEL,
        "segment_count": len(classifications),
        "segments": classifications,
    }

    Path(OUTPUT).parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        OUTPUT,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            result,
            f,
            indent=2,
        )

    print()
    print("Visual classification complete.")
    print(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    main()
