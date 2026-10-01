import json
import re
from pathlib import Path


# ============================================================
# V13.3 EDIT DECISION GRAPH
# ============================================================
#
# Architectural fixes:
#
# 1. Transcript words remain atomic.
#    Visual boundaries cannot split a word.
#
# 2. AI emphasis phrases are searched across the COMPLETE
#    clip-level transcript timeline.
#
# 3. Matched emphasis events are assigned to the visual
#    segment containing their midpoint.
#
# 4. Words are assigned to exactly one visual segment.
#
# 5. AI emphasis requests are not blindly tied to the
#    visual segment that Gemini originally mentioned.
#
# 6. V12 visual_segments schema is handled correctly:
#       segment_id
#       start
#       end
#
# 7. Visual segments are clamped to the actual production
#    clip duration.
#
# ============================================================


BASE = Path("output")

TRANSCRIPT_FILE = BASE / "transcript.json"
MANIFEST_FILE = BASE / "production_manifest_v6.json"
AI_PLAN_FILE = BASE / "ai_edit_plan_v11.json"
VISUAL_SEGMENTS_FILE = BASE / "visual_segments_v12.json"
VISUAL_CLASSIFICATION_FILE = BASE / "visual_classification_v12.json"

OUTPUT_FILE = BASE / "edit_decision_v13_3.json"


# ============================================================
# BASIC HELPERS
# ============================================================

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def midpoint(start, end):
    return (float(start) + float(end)) / 2.0


def normalize_word(text):
    """
    Normalize one transcript word for matching.

    Examples:
        Russia     -> russia
        again.     -> again
        65%        -> 65
    """
    text = str(text).lower().strip()
    text = re.sub(r"[^\w]+", "", text, flags=re.UNICODE)
    return text


def normalize_phrase(text):
    """
    Convert an emphasis phrase into normalized tokens.
    """
    return [
        token
        for token in (
            normalize_word(x)
            for x in str(text).split()
        )
        if token
    ]


# ============================================================
# VISUAL SEGMENT HELPERS
# ============================================================

def find_visual_segment(visual_segments, timestamp):
    """
    Find the visual segment containing timestamp.

    Half-open intervals are used:

        start <= timestamp < end

    This prevents the exact 5.00 boundary from belonging
    to both Segment 1 and Segment 2.
    """

    t = float(timestamp)

    for segment in visual_segments:

        start = float(segment["start"])
        end = float(segment["end"])

        if start <= t < end:
            return segment

    # Allow exact final endpoint.
    if visual_segments:

        last = visual_segments[-1]

        if abs(
            float(last["end"]) - t
        ) < 1e-6:
            return last

    return None


def load_visual_segments(data, clip_duration):
    """
    Load V12 visual_segments correctly.

    V12 structure:

        {
            "video": ...,
            "fps": ...,
            "samples": [...],
            "visual_segments": [...]
        }

    Each visual segment uses:

        segment_id
        start
        end
        duration
    """

    if not isinstance(data, dict):
        raise ValueError(
            "visual_segments_v12.json must be a JSON object."
        )

    raw_segments = data.get(
        "visual_segments",
        [],
    )

    if not isinstance(raw_segments, list):
        raise ValueError(
            "'visual_segments' is not a list."
        )

    result = []

    for raw in raw_segments:

        if "segment_id" not in raw:
            raise ValueError(
                "Visual segment is missing 'segment_id'."
            )

        start = float(raw["start"])
        end = float(raw["end"])

        # Clamp to actual production clip duration.
        start = max(
            0.0,
            min(start, clip_duration),
        )

        end = max(
            0.0,
            min(end, clip_duration),
        )

        if end <= start:
            continue

        result.append(
            {
                "segment_id": int(
                    raw["segment_id"]
                ),
                "start": start,
                "end": end,
                "duration": end - start,
            }
        )

    result.sort(
        key=lambda x: x["start"]
    )

    return result


# ============================================================
# VISUAL CLASSIFICATION
# ============================================================

def load_visual_classification(data):

    by_id = {}

    if isinstance(data, list):

        items = data

    elif isinstance(data, dict):

        items = data.get(
            "segments",
            data.get(
                "visual_segments",
                [],
            ),
        )

    else:

        items = []

    if not isinstance(items, list):
        return by_id

    for item in items:

        if "segment_id" not in item:
            continue

        by_id[
            str(item["segment_id"])
        ] = item

    return by_id


# ============================================================
# AI PLAN
# ============================================================

def get_ai_segments(ai_plan):

    segments = ai_plan.get(
        "segments",
        [],
    )

    if not isinstance(segments, list):
        raise ValueError(
            "AI edit plan 'segments' is not a list."
        )

    return segments


def get_ai_segment_for_time(
    ai_segments,
    timestamp,
):

    t = float(timestamp)

    for segment in ai_segments:

        start = float(
            segment.get("start", 0.0)
        )

        end = float(
            segment.get("end", 0.0)
        )

        if start <= t < end:
            return segment

    if ai_segments:

        last = ai_segments[-1]

        if abs(
            float(last.get("end", 0.0)) - t
        ) < 1e-6:
            return last

    return None


def extract_emphasis_requests(ai_segments):

    requests = []

    for ai_segment in ai_segments:

        ai_start = float(
            ai_segment.get(
                "start",
                0.0,
            )
        )

        ai_end = float(
            ai_segment.get(
                "end",
                0.0,
            )
        )

        captions = ai_segment.get(
            "caption",
            {},
        )

        if not isinstance(
            captions,
            dict,
        ):
            continue

        emphasis_words = captions.get(
            "emphasis_words",
            [],
        )

        if not isinstance(
            emphasis_words,
            list,
        ):
            continue

        for item in emphasis_words:

            if isinstance(
                item,
                str,
            ):

                text = item
                level = "strong"

            elif isinstance(
                item,
                dict,
            ):

                text = item.get(
                    "text",
                    "",
                )

                level = item.get(
                    "level",
                    "strong",
                )

            else:

                continue

            text = str(text).strip()

            if not text:
                continue

            requests.append(
                {
                    "text": text,
                    "level": level,
                    "ai_segment_start": ai_start,
                    "ai_segment_end": ai_end,
                }
            )

    return requests


# ============================================================
# TRANSCRIPT
# ============================================================

def build_clip_words(
    transcript,
    source_start,
    source_end,
):

    clip_duration = (
        source_end - source_start
    )

    words = []

    for transcript_segment in transcript.get(
        "segments",
        [],
    ):

        for word in transcript_segment.get(
            "words",
            [],
        ):

            global_start = float(
                word["start"]
            )

            global_end = float(
                word["end"]
            )

            local_start = (
                global_start
                - source_start
            )

            local_end = (
                global_end
                - source_start
            )

            # Completely before clip.
            if local_end <= 0:
                continue

            # Completely after clip.
            if local_start >= clip_duration:
                continue

            # Clamp only at actual clip boundaries.
            local_start = max(
                0.0,
                local_start,
            )

            local_end = min(
                clip_duration,
                local_end,
            )

            if local_end <= local_start:
                continue

            words.append(
                {
                    "word": word["word"],
                    "start": local_start,
                    "end": local_end,
                }
            )

    words.sort(
        key=lambda x: (
            float(x["start"]),
            float(x["end"]),
        )
    )

    return words


# ============================================================
# ATOMIC WORD ASSIGNMENT
# ============================================================

def assign_atomic_words(
    global_words,
    visual_segments,
):

    segment_words = {
        str(segment["segment_id"]): []
        for segment in visual_segments
    }

    unassigned = []

    for word in global_words:

        start = float(
            word["start"]
        )

        end = float(
            word["end"]
        )

        # CRITICAL:
        # Assign based on word midpoint.
        #
        # The word itself remains intact.
        word_mid = midpoint(
            start,
            end,
        )

        segment = find_visual_segment(
            visual_segments,
            word_mid,
        )

        if segment is None:

            unassigned.append(
                {
                    "word": word["word"],
                    "start": start,
                    "end": end,
                }
            )

            continue

        segment_id = str(
            segment["segment_id"]
        )

        segment_words[
            segment_id
        ].append(
            {
                "word": word["word"],
                "start": start,
                "end": end,
            }
        )

    return (
        segment_words,
        unassigned,
    )


# ============================================================
# GLOBAL PHRASE SEARCH
# ============================================================

def find_phrase_matches(
    words,
    phrase_tokens,
):

    if not phrase_tokens:
        return []

    matches = []

    phrase_length = len(
        phrase_tokens
    )

    for i in range(
        len(words)
        - phrase_length
        + 1
    ):

        candidate = [
            normalize_word(
                words[
                    i + j
                ]["word"]
            )
            for j in range(
                phrase_length
            )
        ]

        if candidate != phrase_tokens:
            continue

        matched_words = words[
            i:
            i + phrase_length
        ]

        start = float(
            matched_words[0]["start"]
        )

        end = float(
            matched_words[-1]["end"]
        )

        matches.append(
            {
                "start": start,
                "end": end,
                "matched_words": matched_words,
            }
        )

    return matches


def choose_best_match(
    matches,
    ai_segment,
):

    if not matches:
        return None

    ai_start = float(
        ai_segment[
            "ai_segment_start"
        ]
    )

    ai_end = float(
        ai_segment[
            "ai_segment_end"
        ]
    )

    ai_mid = midpoint(
        ai_start,
        ai_end,
    )

    def distance(match):

        match_mid = midpoint(
            match["start"],
            match["end"],
        )

        # Prefer occurrence inside
        # Gemini's intended region.
        if (
            ai_start
            <= match_mid
            <= ai_end
        ):
            return 0.0

        return abs(
            match_mid - ai_mid
        )

    return min(
        matches,
        key=distance,
    )


# ============================================================
# MAIN
# ============================================================

print("=" * 64)
print("V13.3 EDIT DECISION GRAPH")
print("=" * 64)

print("\nLoading input files...")

transcript = load_json(
    TRANSCRIPT_FILE
)

manifest = load_json(
    MANIFEST_FILE
)

ai_plan = load_json(
    AI_PLAN_FILE
)

visual_segments_data = load_json(
    VISUAL_SEGMENTS_FILE
)

visual_classification_data = load_json(
    VISUAL_CLASSIFICATION_FILE
)


# ============================================================
# CLIP RANGE
# ============================================================

manifest_entries = manifest.get(
    "clips",
    [],
)

if not manifest_entries:
    raise ValueError(
        "production_manifest_v6.json contains no clips."
    )

# Current production pipeline operates
# on clip #1.
clip = manifest_entries[0]

source_start = float(
    clip["start"]
)

source_end = float(
    clip["end"]
)

clip_duration = (
    source_end - source_start
)

print(
    f"Clip source range: "
    f"{source_start:.2f}s → "
    f"{source_end:.2f}s"
)

print(
    f"Clip duration: "
    f"{clip_duration:.2f}s"
)


# ============================================================
# TRANSCRIPT
# ============================================================

global_transcript_words = (
    build_clip_words(
        transcript,
        source_start,
        source_end,
    )
)

print(
    f"Transcript words in clip: "
    f"{len(global_transcript_words)}"
)


# ============================================================
# VISUAL SEGMENTS
# ============================================================

visual_segments = load_visual_segments(
    visual_segments_data,
    clip_duration,
)

if not visual_segments:
    raise ValueError(
        "No visual segments found."
    )

print(
    f"Visual segments: "
    f"{len(visual_segments)}"
)


# ============================================================
# VISUAL CLASSIFICATION
# ============================================================

classification_by_id = (
    load_visual_classification(
        visual_classification_data
    )
)


# ============================================================
# AI PLAN
# ============================================================

ai_segments = get_ai_segments(
    ai_plan
)

print(
    f"AI edit-plan segments: "
    f"{len(ai_segments)}"
)

emphasis_requests = (
    extract_emphasis_requests(
        ai_segments
    )
)

print(
    f"AI emphasis requests: "
    f"{len(emphasis_requests)}"
)


# ============================================================
# ATOMIC WORDS
# ============================================================

print(
    "\nAssigning atomic transcript words..."
)

segment_words, unassigned_words = (
    assign_atomic_words(
        global_transcript_words,
        visual_segments,
    )
)

assigned_count = sum(
    len(words)
    for words in segment_words.values()
)

print(
    f"Assigned words: "
    f"{assigned_count}"
)

print(
    f"Unassigned words: "
    f"{len(unassigned_words)}"
)


# ============================================================
# GLOBAL EMPHASIS MATCHING
# ============================================================

print(
    "\nMatching emphasis globally..."
)

matched_events = []

unmatched_requests = []

for request_index, request in enumerate(
    emphasis_requests,
    start=1,
):

    phrase = request["text"]

    tokens = normalize_phrase(
        phrase
    )

    matches = find_phrase_matches(
        global_transcript_words,
        tokens,
    )

    if not matches:

        unmatched_requests.append(
            {
                "request_id": request_index,
                **request,
                "reason": (
                    "Phrase was not found "
                    "in the clip-level "
                    "transcript."
                ),
            }
        )

        continue

    best = choose_best_match(
        matches,
        request,
    )

    event_mid = midpoint(
        best["start"],
        best["end"],
    )

    visual_segment = (
        find_visual_segment(
            visual_segments,
            event_mid,
        )
    )

    if visual_segment is None:

        unmatched_requests.append(
            {
                "request_id": request_index,
                **request,
                "reason": (
                    "Phrase matched the "
                    "transcript, but no "
                    "visual segment contains "
                    "its midpoint."
                ),
                "matched_start": best[
                    "start"
                ],
                "matched_end": best[
                    "end"
                ],
            }
        )

        continue

    event = {
        "request_id": request_index,
        "text": phrase,
        "level": request["level"],
        "start": best["start"],
        "end": best["end"],

        "matched_words": [
            {
                "word": w["word"],
                "start": w["start"],
                "end": w["end"],
            }
            for w in best[
                "matched_words"
            ]
        ],

        "visual_segment_id": int(
            visual_segment[
                "segment_id"
            ]
        ),

        "ai_segment_start": request[
            "ai_segment_start"
        ],

        "ai_segment_end": request[
            "ai_segment_end"
        ],

        "match_count": len(matches),
    }

    matched_events.append(
        event
    )


# ============================================================
# GROUP EVENTS BY VISUAL SEGMENT
# ============================================================

events_by_segment = {
    str(segment["segment_id"]): []
    for segment in visual_segments
}

for event in matched_events:

    segment_id = str(
        event[
            "visual_segment_id"
        ]
    )

    events_by_segment.setdefault(
        segment_id,
        [],
    ).append(event)


# ============================================================
# BUILD FINAL EDIT GRAPH
# ============================================================

final_segments = []

for visual_segment in visual_segments:

    segment_id = str(
        visual_segment[
            "segment_id"
        ]
    )

    start = float(
        visual_segment["start"]
    )

    end = float(
        visual_segment["end"]
    )

    classification = (
        classification_by_id.get(
            segment_id,
            {},
        )
    )

    visual_type = classification.get(
        "visual_type",
        "unknown",
    )

    people_count = classification.get(
        "people_count_estimate",
        classification.get(
            "people_count",
            0,
        ),
    )

    try:
        people_count = int(
            people_count
        )
    except (
        TypeError,
        ValueError,
    ):
        people_count = 0

    treatment = classification.get(
        "recommended_treatment",
        "preserve_composition",
    )

    # --------------------------------------------------------
    # AI segment
    # --------------------------------------------------------

    visual_mid = midpoint(
        start,
        end,
    )

    ai_segment = (
        get_ai_segment_for_time(
            ai_segments,
            visual_mid,
        )
    )

    if ai_segment is None:
        ai_segment = {}

    # --------------------------------------------------------
    # Crop decision
    # --------------------------------------------------------

    if (
        visual_type
        == "multiple_people"
        or people_count > 1
    ):

        crop_mode = (
            "preserve_composition"
        )

    elif treatment == "speaker_crop":

        crop_mode = "speaker_crop"

    else:

        crop_mode = (
            "preserve_composition"
        )

    # --------------------------------------------------------
    # Motion
    # --------------------------------------------------------

    motion = ai_segment.get(
        "motion",
        {},
    )

    if not isinstance(
        motion,
        dict,
    ):
        motion = {}

    # --------------------------------------------------------
    # Emphasis events
    # --------------------------------------------------------

    emphasis_events = (
        events_by_segment.get(
            segment_id,
            [],
        )
    )

    # --------------------------------------------------------
    # Atomic words
    # --------------------------------------------------------

    words = segment_words.get(
        segment_id,
        [],
    )

    # --------------------------------------------------------
    # Final segment
    # --------------------------------------------------------

    final_segments.append(
        {
            "segment_id": int(
                visual_segment[
                    "segment_id"
                ]
            ),

            "start": start,

            "end": end,

            "duration": (
                end - start
            ),

            "visual": {
                "visual_type": visual_type,

                "people_present": (
                    classification.get(
                        "people_present"
                    )
                ),

                "people_count_estimate": (
                    people_count
                ),

                "framing": (
                    classification.get(
                        "framing"
                    )
                ),

                "subject_position": (
                    classification.get(
                        "subject_position"
                    )
                ),

                "visual_importance": (
                    classification.get(
                        "visual_importance"
                    )
                ),

                "recommended_treatment": (
                    treatment
                ),
            },

            "edit": {
                "crop_mode": crop_mode,

                "motion": motion,

                "ai_segment_start": (
                    ai_segment.get(
                        "start"
                    )
                ),

                "ai_segment_end": (
                    ai_segment.get(
                        "end"
                    )
                ),

                "ai_reason": (
                    ai_segment.get(
                        "reason"
                    )
                ),
            },

            "captions": {

                "words": words,

                "emphasis_events": (
                    emphasis_events
                ),

                "emphasis_words": [
                    {
                        "text": event[
                            "text"
                        ],
                        "level": event[
                            "level"
                        ],
                    }
                    for event
                    in emphasis_events
                ],
            },

            "alignment": {

                "atomic_word_count": (
                    len(words)
                ),

                "emphasis_event_count": (
                    len(
                        emphasis_events
                    )
                ),
            },
        }
    )


# ============================================================
# VALIDATION
# ============================================================

all_assigned_words = []

for segment in final_segments:

    all_assigned_words.extend(
        segment[
            "captions"
        ][
            "words"
        ]
    )


# ------------------------------------------------------------
# Duplicate word assignment check
# ------------------------------------------------------------

word_keys = [
    (
        word["word"],
        round(
            float(
                word["start"]
            ),
            6,
        ),
        round(
            float(
                word["end"]
            ),
            6,
        ),
    )
    for word in all_assigned_words
]

seen = set()

duplicate_word_keys = []

for key in word_keys:

    if key in seen:

        duplicate_word_keys.append(
            key
        )

    else:

        seen.add(key)


# ------------------------------------------------------------
# Chronological check
# ------------------------------------------------------------

chronological = all(
    all_assigned_words[i]["start"]
    <=
    all_assigned_words[i + 1]["start"]

    for i in range(
        len(
            all_assigned_words
        ) - 1
    )
)


# ------------------------------------------------------------
# Coverage check
# ------------------------------------------------------------

coverage_ok = (
    assigned_count
    + len(unassigned_words)
    == len(
        global_transcript_words
    )
)


# ============================================================
# ALIGNMENT SUMMARY
# ============================================================

alignment = {

    "word_timestamps": True,

    "transcript_segments": len(
        transcript.get(
            "segments",
            [],
        )
    ),

    "transcript_words": len(
        global_transcript_words
    ),

    "atomic_words_assigned": (
        assigned_count
    ),

    "atomic_words_unassigned": (
        len(
            unassigned_words
        )
    ),

    "emphasis_requested": len(
        emphasis_requests
    ),

    "emphasis_matched": len(
        matched_events
    ),

    "emphasis_unmatched": len(
        unmatched_requests
    ),

    "duplicate_word_assignments": len(
        duplicate_word_keys
    ),

    "words_chronological": (
        chronological
    ),

    "word_coverage_valid": (
        coverage_ok
    ),
}


# ============================================================
# OUTPUT
# ============================================================

output = {

    "version": "V13.3",

    "clip": {

        "id": clip.get(
            "id"
        ),

        "source_start": (
            source_start
        ),

        "source_end": (
            source_end
        ),

        "duration": (
            clip_duration
        ),
    },

    "alignment": alignment,

    "segments": final_segments,

    "emphasis": {

        "requested": (
            emphasis_requests
        ),

        "matched": (
            matched_events
        ),

        "unmatched": (
            unmatched_requests
        ),
    },

    "validation": {

        "duplicate_word_assignments": (
            duplicate_word_keys
        ),

        "unassigned_words": (
            unassigned_words
        ),
    },
}


with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8",
) as f:

    json.dump(
        output,
        f,
        indent=2,
        ensure_ascii=False,
    )


# ============================================================
# REPORT
# ============================================================

print(
    "\n" + "=" * 64
)

print(
    "V13.3 COMPLETE"
)

print(
    "=" * 64
)

print(
    f"Visual segments:       "
    f"{len(final_segments)}"
)

print(
    f"Atomic words assigned:  "
    f"{assigned_count}"
)

print(
    f"Unassigned words:       "
    f"{len(unassigned_words)}"
)

print(
    f"Emphasis requested:     "
    f"{len(emphasis_requests)}"
)

print(
    f"Emphasis matched:       "
    f"{len(matched_events)}"
)

print(
    f"Emphasis unmatched:     "
    f"{len(unmatched_requests)}"
)

print(
    f"Duplicate word assigns: "
    f"{len(duplicate_word_keys)}"
)

print(
    f"Chronological words:     "
    f"{chronological}"
)

print(
    f"Word coverage valid:     "
    f"{coverage_ok}"
)

print(
    f"\nSaved: {OUTPUT_FILE}"
)


# ============================================================
# EMPHASIS REPORT
# ============================================================

print(
    "\nEMPHASIS EVENTS:"
)

for event in matched_events:

    print(
        f"  "
        f"[{event['start']:.2f}-"
        f"{event['end']:.2f}] "
        f"{event['text']!r} "
        f"→ visual segment "
        f"{event['visual_segment_id']}"
    )


if unmatched_requests:

    print(
        "\nUNMATCHED REQUESTS:"
    )

    for item in unmatched_requests:

        print(
            f"  "
            f"{item['text']!r} "
            f"→ "
            f"{item['reason']}"
        )


# ============================================================
# BOUNDARY DIAGNOSTIC
# ============================================================

print(
    "\nBOUNDARY DIAGNOSTIC:"
)

for i in range(
    len(final_segments) - 1
):

    current = final_segments[i]

    nxt = final_segments[i + 1]

    current_words = (
        current[
            "captions"
        ][
            "words"
        ]
    )

    next_words = (
        nxt[
            "captions"
        ][
            "words"
        ]
    )

    if (
        not current_words
        or not next_words
    ):
        continue

    last_word = current_words[-1]

    first_word = next_words[0]

    print(
        f"  "
        f"Seg "
        f"{current['segment_id']} "
        f"→ "
        f"Seg "
        f"{nxt['segment_id']}: "
        f"{last_word['word']!r} | "
        f"{first_word['word']!r}"
    )
