import json
from pathlib import Path


TRANSCRIPT_FILE = Path("output/transcript.json")
MANIFEST_FILE = Path("output/production_manifest_v6.json")
AI_PLAN_FILE = Path("output/ai_edit_plan_v11.json")
VISUAL_SEGMENTS_FILE = Path("output/visual_segments_v12.json")
VISUAL_CLASSIFICATION_FILE = Path("output/visual_classification_v12.json")

OUTPUT_FILE = Path("output/edit_decision_v13_1.json")

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
def get_clip_source_range(manifest, clip_id):
    for clip in manifest["clips"]:
        if clip["id"] == clip_id:
            return float(clip["start"]), float(clip["end"])

    raise ValueError(
        f"Clip '{clip_id}' not found in production manifest."
    )


def convert_transcript_to_clip_local(
    transcript_segments,
    source_start,
    source_end
):
    local_segments = []

    for segment in transcript_segments:
        global_start = float(segment["start"])
        global_end = float(segment["end"])

        # Ignore transcript content completely outside this clip.
        if global_end <= source_start:
            continue

        if global_start >= source_end:
            continue

        # Clamp to the actual clip boundaries.
        clipped_start = max(global_start, source_start)
        clipped_end = min(global_end, source_end)

        local_segments.append({
            "start": clipped_start - source_start,
            "end": clipped_end - source_start,
            "text": segment["text"]
        })

    return local_segments


def overlap(start_a, end_a, start_b, end_b):
    return max(0.0, min(end_a, end_b) - max(start_a, start_b))


def find_visual_classification(time, classifications):
    for segment in classifications:
        if segment["start"] <= time < segment["end"]:
            return segment

    if classifications:
        return classifications[-1]

    return None


def find_nearest_visual_sample(time, samples):
    if not samples:
        return None

    return min(
        samples,
        key=lambda sample: abs(sample["time"] - time)
    )


def find_transcript_segments(start, end, transcript_segments):
    matches = []

    for segment in transcript_segments:
        if overlap(
            start,
            end,
            segment["start"],
            segment["end"]
        ) > 0:
            matches.append(segment)

    return matches


def find_ai_segment(time, ai_segments):
    for segment in ai_segments:
        if segment["start"] <= time < segment["end"]:
            return segment

    if ai_segments:
        return ai_segments[-1]

    return None


def build_crop_decision(visual, sample, ai_segment):
    classification = visual["classification"]

    visual_type = classification.get(
        "visual_type",
        "unknown"
    )

    treatment = classification.get(
        "recommended_treatment",
        "unknown"
    )

    framing = classification.get(
        "framing",
        "unknown"
    )

    if visual_type == "b_roll":
        return {
            "mode": "preserve_composition",
            "reason": "B-roll should retain its original visual composition."
        }

    if visual_type == "speaker":
        bbox = None

        if sample and sample.get("people"):
            people = sample["people"]

            if people:
                best_person = max(
                    people,
                    key=lambda person: person.get(
                        "confidence",
                        0
                    )
                )

                bbox = best_person.get("bbox")

        return {
            "mode": "subject_tracking_crop",
            "target": "primary_person",
            "framing": framing,
            "treatment": treatment,
            "bbox": bbox,
            "reason": "Use the detected primary person to construct the vertical crop."
        }

    return {
        "mode": "preserve_composition",
        "reason": "Unknown visual type; avoid aggressive automatic cropping."
    }


def build_motion_decision(ai_segment, visual):
    framing = ai_segment.get("framing", {})

    motion = framing.get(
        "motion",
        "static"
    )

    zoom_start = framing.get(
        "zoom_start",
        1.0
    )

    zoom_end = framing.get(
        "zoom_end",
        1.0
    )

    visual_type = visual["classification"].get(
        "visual_type",
        "unknown"
    )

    # Do not force motion onto B-roll unless the AI plan
    # explicitly requests it.
    if visual_type == "b_roll":
        return {
            "type": motion,
            "zoom_start": zoom_start,
            "zoom_end": zoom_end
        }

    return {
        "type": motion,
        "zoom_start": zoom_start,
        "zoom_end": zoom_end
    }


def build_caption_decision(ai_segment, transcript_segments):
    caption = ai_segment.get(
        "caption",
        {}
    )

    emphasis_words = caption.get(
        "emphasis_words",
        []
    )

    return {
        "style": caption.get(
            "style",
            "dynamic"
        ),
        "emphasis_words": emphasis_words,
        "source_transcript": [
            {
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"]
            }
            for segment in transcript_segments
        ]
    }


def build_edit_graph():
    print("Loading V13.1 input files...")

    transcript = load_json(
        TRANSCRIPT_FILE
    )

    ai_plan = load_json(
        AI_PLAN_FILE
    )

    manifest = load_json(
        MANIFEST_FILE
    )

    visual_segments = load_json(
        VISUAL_SEGMENTS_FILE
    )

    visual_classification = load_json(
        VISUAL_CLASSIFICATION_FILE
    )

    clip_id = ai_plan["clip_id"]

    source_start, source_end = get_clip_source_range(
        manifest,
        clip_id
    )

    print(
        f"Clip source range: "
        f"{source_start:.2f}s → {source_end:.2f}s"
    )

    transcript_segments = convert_transcript_to_clip_local(
        transcript["segments"],
        source_start,
        source_end
    )

    print(
        f"Transcript segments in clip: "
        f"{len(transcript_segments)}"
    )

    ai_segments = ai_plan["segments"]

    visual_samples = visual_segments["samples"]

    classifications = visual_classification["segments"]

    edit_segments = []

    for visual in classifications:
        start = visual["start"]
        end = visual["end"]

        midpoint = (start + end) / 2.0

        ai_segment = find_ai_segment(
            midpoint,
            ai_segments
        )

        sample = find_nearest_visual_sample(
            midpoint,
            visual_samples
        )

        transcript_matches = find_transcript_segments(
            start,
            end,
            transcript_segments
        )

        if ai_segment is None:
            ai_segment = {
                "type": "normal",
                "reason": "No AI editing segment found.",
                "framing": {
                    "shot": "medium",
                    "zoom_start": 1.0,
                    "zoom_end": 1.0,
                    "motion": "static"
                },
                "caption": {
                    "style": "dynamic",
                    "emphasis_words": []
                }
            }

        crop = build_crop_decision(
            visual,
            sample,
            ai_segment
        )

        motion = build_motion_decision(
            ai_segment,
            visual
        )

        captions = build_caption_decision(
            ai_segment,
            transcript_matches
        )

        edit_segments.append({
            "segment_id": visual["segment_id"],
            "start": start,
            "end": end,
            "duration": end - start,

            "semantic": {
                "edit_type": ai_segment.get(
                    "type",
                    "normal"
                ),
                "reason": ai_segment.get(
                    "reason",
                    ""
                ),
                "pacing": ai_segment.get(
                    "pacing",
                    "normal"
                ),
                "visual_emphasis": ai_segment.get(
                    "visual_emphasis",
                    "none"
                )
            },

            "visual": {
                "type": visual["classification"].get(
                    "visual_type",
                    "unknown"
                ),
                "framing": visual["classification"].get(
                    "framing",
                    "unknown"
                ),
                "importance": visual["classification"].get(
                    "visual_importance",
                    "medium"
                )
            },

            "crop": crop,

            "motion": motion,

            "captions": captions,

            "source_visual_sample": {
                "time": sample["time"] if sample else None,
                "people_count": (
                    sample.get("people_count", 0)
                    if sample
                    else 0
                )
            }
        })

    result = {
        "version": "v13.1",
        "clip_id": ai_plan["clip_id"],
        "duration": ai_plan["duration"],

        "output_format": {
            "width": 1080,
            "height": 1920,
            "aspect_ratio": "9:16"
        },

        "editing_principles": [
            "Prefer meaningful edits over constant effects.",
            "Track the primary subject when speaker footage is detected.",
            "Preserve B-roll composition unless motion is explicitly justified.",
            "Use AI zoom decisions as intent, not as unconditional commands.",
            "Use visual evidence before applying aggressive crops.",
            "Avoid unnecessary transitions."
        ],

        "segments": edit_segments
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            result,
            f,
            indent=2,
            ensure_ascii=False
        )

    print()
    print("V13 Edit Decision Graph complete.")
    print(f"Segments: {len(edit_segments)}")
    print(f"Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    build_edit_graph()
