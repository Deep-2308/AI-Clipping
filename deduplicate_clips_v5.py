import json
import os


# =========================================================
# FILES
# =========================================================

INPUT_FILE = "output/clip_candidates_v4.json"
OUTPUT_FILE = "output/clip_candidates_v5.json"


# =========================================================
# SETTINGS
# =========================================================

# If two clips overlap by this percentage or more,
# they are considered duplicates.
OVERLAP_THRESHOLD = 0.50

# Maximum number of final clips.
MAX_CLIPS = 10


# =========================================================
# LOAD CANDIDATES
# =========================================================

if not os.path.exists(INPUT_FILE):
    raise FileNotFoundError(
        f"Input file not found: {INPUT_FILE}"
    )


with open(
    INPUT_FILE,
    "r",
    encoding="utf-8"
) as f:

    data = json.load(f)


candidates = data.get("clips", [])


if not candidates:
    raise RuntimeError(
        "No clip candidates found."
    )


print()
print("=" * 60)
print("CLIP DEDUPLICATION V5")
print("=" * 60)

print(
    f"Input candidates: {len(candidates)}"
)


# =========================================================
# OVERLAP CALCULATION
# =========================================================

def calculate_overlap(clip_a, clip_b):

    a_start = float(clip_a["start"])
    a_end = float(clip_a["end"])

    b_start = float(clip_b["start"])
    b_end = float(clip_b["end"])


    intersection_start = max(
        a_start,
        b_start
    )

    intersection_end = min(
        a_end,
        b_end
    )


    intersection = max(
        0,
        intersection_end - intersection_start
    )


    if intersection <= 0:
        return 0.0


    duration_a = a_end - a_start
    duration_b = b_end - b_start


    if duration_a <= 0 or duration_b <= 0:
        return 0.0


    # Compare overlap against the smaller clip.
    smaller_duration = min(
        duration_a,
        duration_b
    )


    return intersection / smaller_duration


# =========================================================
# SORT BY SCORE
# =========================================================

candidates.sort(
    key=lambda clip: float(
        clip.get("overall_score", 0)
    ),
    reverse=True
)


# =========================================================
# DEDUPLICATE
# =========================================================

selected = []

removed = []


for candidate in candidates:

    is_duplicate = False

    for existing in selected:

        overlap = calculate_overlap(
            candidate,
            existing
        )


        if overlap >= OVERLAP_THRESHOLD:

            is_duplicate = True

            removed.append({
                "clip": candidate,
                "duplicate_of": existing,
                "overlap": round(
                    overlap * 100,
                    2
                )
            })

            break


    if not is_duplicate:

        selected.append(candidate)


    if len(selected) >= MAX_CLIPS:

        break


# =========================================================
# ADD RANK
# =========================================================

for index, clip in enumerate(
    selected,
    start=1
):

    clip["final_rank"] = index


# =========================================================
# SAVE OUTPUT
# =========================================================

output = {
    "source_file": data.get(
        "source_file"
    ),

    "input_candidates": len(
        candidates
    ),

    "removed_duplicates": len(
        removed
    ),

    "final_candidates": len(
        selected
    ),

    "overlap_threshold": (
        OVERLAP_THRESHOLD
    ),

    "clips": selected
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
# REPORT
# =========================================================

print()
print(
    f"Removed duplicates: "
    f"{len(removed)}"
)

print(
    f"Final unique clips: "
    f"{len(selected)}"
)


print()
print("=" * 60)
print("FINAL CLIPS")
print("=" * 60)


for clip in selected:

    print()

    print(
        f"#{clip['final_rank']} "
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


# =========================================================
# REMOVED DUPLICATES
# =========================================================

if removed:

    print()
    print("=" * 60)
    print("REMOVED OVERLAPPING CLIPS")
    print("=" * 60)


    for item in removed:

        clip = item["clip"]
        original = item["duplicate_of"]

        print()

        print(
            f"Removed: "
            f"{clip['start']:.2f}s -> "
            f"{clip['end']:.2f}s"
        )

        print(
            f"Kept: "
            f"{original['start']:.2f}s -> "
            f"{original['end']:.2f}s"
        )

        print(
            f"Overlap: "
            f"{item['overlap']}%"
        )


print()
print(
    f"Output saved to: "
    f"{OUTPUT_FILE}"
)

print("=" * 60)
