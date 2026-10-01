import json
import re
from pathlib import Path


TRANSCRIPT_FILE = Path("output/transcript.json")
MANIFEST_FILE = Path("output/production_manifest_v6.json")
AI_PLAN_FILE = Path("output/ai_edit_plan_v11.json")
VISUAL_SEGMENTS_FILE = Path("output/visual_segments_v12.json")
VISUAL_CLASSIFICATION_FILE = Path("output/visual_classification_v12.json")

OUTPUT_FILE = Path("output/edit_decision_v13_2.json")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def overlap(start_a, end_a, start_b, end_b):
    return max(
        0.0,
        min(end_a, end_b) - max(start_a, start_b)
    )


def get_clip_source_range(manifest, clip_id):
    for clip in manifest["clips"]:
        if clip["id"] == clip_id:
            return (
                float(clip["start"]),
                float(clip["end"])
            )

    raise ValueError(
        f"Clip '{clip_id}' not found in production manifest."
    )


def convert_transcript_to_clip_local(
    transcript_segments,
    source_start,
    source_end
):
    """
    Convert global Whisper timestamps into clip-local timestamps.

    Only words/segments that actually overlap the selected clip
    are retained.
    """

    local_segments = []

    for segment in transcript_segments:

        global_start = float(segment["start"])
        global_end = float(segment["end"])

        if global_end <= source_start:
            continue

        if global_start >= source_end:
            continue

        clipped_start = max(
            global_start,
            source_start
        )

        clipped_end = min(
            global_end,
            source_end
        )

        local_words = []

        for word in segment.get("words", []):

            word_global_start = float(
                word["start"]
            )

            word_global_end = float(
                word["end"]
            )

            if word_global_end <= source_start:
                continue

            if word_global_start >= source_end:
                continue

            word_start = max(
                word_global_start,
                source_start
            ) - source_start

            word_end = min(
                word_global_end,
                source_end
            ) - source_start

            local_words.append({
                "word": word["word"],
                "start": round(
                    max(0.0, word_start),
                    3
                ),
                "end": round(
                    min(
                        source_end - source_start,
                        word_end
                    ),
                    3
                )
            })

        local_segments.append({
            "start": round(
                clipped_start - source_start,
                3
            ),
            "end": round(
                clipped_end - source_start,
                3
            ),
            "text": segment["text"],
            "words": local_words
        })

    return local_segments


def find_visual_classification(
    time,
    classifications
):
    for segment in classifications:

        if (
            segment["start"]
            <= time
            < segment["end"]
        ):
            return segment

    if classifications:
        return classifications[-1]

    return None


def find_nearest_visual_sample(
    time,
    samples
):
    if not samples:
        return None

    return min(
        samples,
        key=lambda sample:
        abs(sample["time"] - time)
    )


def find_transcript_words(
    start,
    end,
    transcript_segments
):
    """
    Return only words whose timestamps overlap
    the visual segment.
    """

    words = []

    for segment in transcript_segments:

        for word in segment.get(
            "words",
            []
        ):

            if overlap(
                start,
                end,
                word["start"],
                word["end"]
            ) > 0:

                words.append({
                    "word": word["word"],
                    "start": max(
                        start,
                        word["start"]
                    ),
                    "end": min(
                        end,
                        word["end"]
                    )
                })

    return words


def find_transcript_segments(
    start,
    end,
    transcript_segments
):
    """
    Keep segment-level information for context,
    but clip its time range to the visual segment.
    """

    matches = []

    for segment in transcript_segments:

        if overlap(
            start,
            end,
            segment["start"],
            segment["end"]
        ) <= 0:
            continue

        matches.append({
            "start": max(
                start,
                segment["start"]
            ),
            "end": min(
                end,
                segment["end"]
            ),
            "text": segment["text"]
        })

    return matches


def find_ai_segment(
    time,
    ai_segments
):
    for segment in ai_segments:

        if (
            segment["start"]
            <= time
            < segment["end"]
        ):
            return segment

    if ai_segments:
        return ai_segments[-1]

    return None


def normalize_word(text):
    """
    Normalize a word for phrase matching.

    Removes punctuation and converts to lowercase.
    """

    return re.sub(
        r"[^a-z0-9%]+",
        "",
        text.lower()
    )


def find_emphasis_phrase(
    phrase,
    words,
    search_start=None,
    search_end=None
):
    """
    Locate an AI emphasis phrase inside the
    word-level transcript.

    Returns exact timing when found.
    """

    phrase_words = [
        normalize_word(word)
        for word in phrase.split()
    ]

    phrase_words = [
        word
        for word in phrase_words
        if word
    ]

    if not phrase_words:
        return None

    candidate_words = words

    if search_start is not None:
        candidate_words = [
            word
            for word in candidate_words
            if word["end"] > search_start
        ]

    if search_end is not None:
        candidate_words = [
            word
            for word in candidate_words
            if word["start"] < search_end
        ]

    normalized_words = [
        normalize_word(
            word["word"]
        )
        for word in candidate_words
    ]

    phrase_length = len(
        phrase_words
    )

    for i in range(
        len(normalized_words)
        - phrase_length
        + 1
    ):

        window = normalized_words[
            i:i + phrase_length
        ]

        if window == phrase_words:

            matched_words = candidate_words[
                i:i + phrase_length
            ]

            return {
                "text": phrase,
                "level": None,
                "start": matched_words[0]["start"],
                "end": matched_words[-1]["end"],
                "matched_words": [
                    {
                        "word": word["word"],
                        "start": word["start"],
                        "end": word["end"]
                    }
                    for word in matched_words
                ]
            }

    return None


def build_crop_decision(
    visual,
    sample,
    ai_segment
):
    classification = visual[
        "classification"
    ]

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

    people_count = classification.get(
        "people_count_estimate",
        0
    )

    # Group/multiple-person footage should
    # preserve composition.
    if (
        visual_type == "multiple_people"
        or people_count > 1
    ):
        return {
            "mode": "preserve_composition",
            "reason": (
                "Multiple people detected; "
                "preserve group composition "
                "instead of locking onto one person."
            )
        }

    if visual_type == "b_roll":

        return {
            "mode": "preserve_composition",
            "reason": (
                "B-roll should retain its "
                "original visual composition."
            )
        }

    if visual_type == "speaker":

        bbox = None

        if (
            sample
            and sample.get("people")
        ):

            people = sample["people"]

            if people:

                best_person = max(
                    people,
                    key=lambda person:
                    person.get(
                        "confidence",
                        0
                    )
                )

                bbox = best_person.get(
                    "bbox"
                )

        return {
            "mode": "subject_tracking_crop",
            "target": "primary_person",
            "framing": framing,
            "treatment": treatment,
            "bbox": bbox,
            "reason": (
                "Use detected speaker "
                "location to construct "
                "the vertical crop."
            )
        }

    return {
        "mode": "preserve_composition",
        "reason": (
            "Unknown visual type; "
            "avoid aggressive automatic cropping."
        )
    }


def build_motion_decision(
    ai_segment,
    visual
):
    framing = ai_segment.get(
        "framing",
        {}
    )

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

    visual_type = visual[
        "classification"
    ].get(
        "visual_type",
        "unknown"
    )

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


def build_caption_decision(
    ai_segment,
    transcript_segments,
    transcript_words,
    segment_start,
    segment_end
):
    caption = ai_segment.get(
        "caption",
        {}
    )

    emphasis_words = caption.get(
        "emphasis_words",
        []
    )

    emphasis_events = []

    for emphasis in emphasis_words:

        phrase = emphasis.get(
            "text",
            ""
        )

        level = emphasis.get(
            "level",
            "strong"
        )

        match = find_emphasis_phrase(
            phrase,
            transcript_words,
            search_start=segment_start,
            search_end=segment_end
        )

        if match:

            match["level"] = level

            emphasis_events.append(
                match
            )

    return {
        "style": caption.get(
            "style",
            "dynamic"
        ),

        "emphasis_words": (
            emphasis_words
        ),

        "emphasis_events": (
            emphasis_events
        ),

        "source_transcript": [
            {
                "start": segment[
                    "start"
                ],
                "end": segment[
                    "end"
                ],
                "text": segment[
                    "text"
                ]
            }
            for segment
            in transcript_segments
        ],

        "words": transcript_words
    }


def build_edit_graph():

    print(
        "Loading V13.2 input files..."
    )

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

    clip_id = ai_plan[
        "clip_id"
    ]

    source_start, source_end = (
        get_clip_source_range(
            manifest,
            clip_id
        )
    )

    print(
        f"Clip source range: "
        f"{source_start:.2f}s → "
        f"{source_end:.2f}s"
    )

    transcript_segments = (
        convert_transcript_to_clip_local(
            transcript["segments"],
            source_start,
            source_end
        )
    )

    total_words = sum(
        len(
            segment.get(
                "words",
                []
            )
        )
        for segment
        in transcript_segments
    )

    print(
        f"Transcript segments: "
        f"{len(transcript_segments)}"
    )

    print(
        f"Transcript words: "
        f"{total_words}"
    )

    ai_segments = ai_plan[
        "segments"
    ]

    visual_samples = (
        visual_segments["samples"]
    )

    classifications = (
        visual_classification[
            "segments"
        ]
    )

    edit_segments = []

    for visual in classifications:

        start = float(
            visual["start"]
        )

        end = float(
            visual["end"]
        )

        midpoint = (
            start + end
        ) / 2.0

        ai_segment = find_ai_segment(
            midpoint,
            ai_segments
        )

        sample = (
            find_nearest_visual_sample(
                midpoint,
                visual_samples
            )
        )

        transcript_matches = (
            find_transcript_segments(
                start,
                end,
                transcript_segments
            )
        )

        transcript_words = (
            find_transcript_words(
                start,
                end,
                transcript_segments
            )
        )

        if ai_segment is None:

            ai_segment = {
                "type": "normal",
                "reason": (
                    "No AI editing "
                    "segment found."
                ),
                "pacing": "normal",
                "visual_emphasis": "none",
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
            transcript_matches,
            transcript_words,
            start,
            end
        )

        edit_segments.append({

            "segment_id": visual[
                "segment_id"
            ],

            "start": start,

            "end": end,

            "duration": round(
                end - start,
                3
            ),

            "semantic": {

                "edit_type":
                    ai_segment.get(
                        "type",
                        "normal"
                    ),

                "reason":
                    ai_segment.get(
                        "reason",
                        ""
                    ),

                "pacing":
                    ai_segment.get(
                        "pacing",
                        "normal"
                    ),

                "visual_emphasis":
                    ai_segment.get(
                        "visual_emphasis",
                        "none"
                    )
            },

            "visual": {

                "type":
                    visual[
                        "classification"
                    ].get(
                        "visual_type",
                        "unknown"
                    ),

                "framing":
                    visual[
                        "classification"
                    ].get(
                        "framing",
                        "unknown"
                    ),

                "importance":
                    visual[
                        "classification"
                    ].get(
                        "visual_importance",
                        "medium"
                    )
            },

            "crop": crop,

            "motion": motion,

            "captions": captions,

            "source_visual_sample": {

                "time":
                    sample["time"]
                    if sample
                    else None,

                "people_count":
                    (
                        sample.get(
                            "people_count",
                            0
                        )
                        if sample
                        else 0
                    )
            }
        })

    total_emphasis_events = sum(
        len(
            segment[
                "captions"
            ][
                "emphasis_events"
            ]
        )
        for segment
        in edit_segments
    )

    total_emphasis_requested = sum(
        len(
            segment[
                "captions"
            ][
                "emphasis_words"
            ]
        )
        for segment
        in edit_segments
    )

    result = {

        "version": "v13.2",

        "clip_id":
            ai_plan["clip_id"],

        "duration":
            ai_plan["duration"],

        "source_range": {

            "global_start":
                source_start,

            "global_end":
                source_end,

            "duration":
                round(
                    source_end
                    - source_start,
                    3
                )
        },

        "output_format": {

            "width": 1080,

            "height": 1920,

            "aspect_ratio": "9:16"
        },

        "editing_principles": [

            "Prefer meaningful edits over constant effects.",

            "Use exact word timestamps for timed caption emphasis.",

            "Track the primary subject when speaker footage is detected.",

            "Preserve B-roll composition unless motion is explicitly justified.",

            "Preserve group composition when multiple people are visible.",

            "Use AI zoom decisions as intent, not as unconditional commands.",

            "Use visual evidence before applying aggressive crops.",

            "Avoid unnecessary transitions."
        ],

        "alignment": {

            "word_timestamps": True,

            "transcript_segments":
                len(
                    transcript_segments
                ),

            "transcript_words":
                total_words,

            "emphasis_requested":
                total_emphasis_requested,

            "emphasis_matched":
                total_emphasis_events
        },

        "segments":
            edit_segments
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
    print(
        "V13.2 Edit Decision Graph complete."
    )

    print(
        f"Visual segments: "
        f"{len(edit_segments)}"
    )

    print(
        f"Transcript words: "
        f"{total_words}"
    )

    print(
        f"Emphasis matched: "
        f"{total_emphasis_events}/"
        f"{total_emphasis_requested}"
    )

    print(
        f"Saved: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    build_edit_graph()
