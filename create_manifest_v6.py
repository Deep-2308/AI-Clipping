import json
import os


# =========================================================
# FILES
# =========================================================

INPUT_FILE = "output/clip_candidates_v5.json"
OUTPUT_FILE = "output/production_manifest_v6.json"


# =========================================================
# SETTINGS
# =========================================================

SOURCE_VIDEO = "input/real_test.mp4"

OUTPUT_DIR = "output/final_clips"


# =========================================================
# LOAD V5
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


clips = data.get("clips", [])


if not clips:
    raise RuntimeError(
        "No clips found in V5 output."
    )


# =========================================================
# CREATE OUTPUT DIRECTORY
# =========================================================

os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
)


# =========================================================
# BUILD MANIFEST
# =========================================================

production_clips = []


for index, clip in enumerate(
    clips,
    start=1
):

    start = round(
        float(clip["start"]),
        2
    )

    end = round(
        float(clip["end"]),
        2
    )

    duration = round(
        end - start,
        2
    )


    clip_id = f"clip_{index:02d}"


    production_clips.append({

        "id": clip_id,

        "rank": index,

        "start": start,

        "end": end,

        "duration": duration,

        "score": clip.get(
            "overall_score",
            0
        ),

        "title": clip.get(
            "title",
            f"Short Clip {index}"
        ),

        "hook": clip.get(
            "hook",
            ""
        ),

        "reason": clip.get(
            "reason",
            ""
        ),

        "source_window": clip.get(
            "source_window"
        ),

        "source_video": SOURCE_VIDEO,

        "raw_output": (
            f"{OUTPUT_DIR}/"
            f"{clip_id}_raw.mp4"
        ),

        "vertical_output": (
            f"{OUTPUT_DIR}/"
            f"{clip_id}_vertical.mp4"
        ),

        "captioned_output": (
            f"{OUTPUT_DIR}/"
            f"{clip_id}_final.mp4"
        ),

        "status": "planned"
    })


# =========================================================
# MANIFEST
# =========================================================

manifest = {

    "project": "AI Clipping Pipeline",

    "version": "v6",

    "source_video": SOURCE_VIDEO,

    "source_file_exists": os.path.exists(
        SOURCE_VIDEO
    ),

    "total_clips": len(
        production_clips
    ),

    "output_directory": OUTPUT_DIR,

    "render_settings": {

        "aspect_ratio": "9:16",

        "width": 1080,

        "height": 1920,

        "video_codec": "libx264",

        "audio_codec": "aac",

        "video_crf": 20,

        "audio_bitrate": "128k"
    },

    "clips": production_clips
}


# =========================================================
# SAVE
# =========================================================

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        manifest,
        f,
        indent=2,
        ensure_ascii=False
    )


# =========================================================
# REPORT
# =========================================================

print()
print("=" * 60)
print("PRODUCTION MANIFEST V6")
print("=" * 60)

print(
    f"Source video: "
    f"{SOURCE_VIDEO}"
)

print(
    f"Source exists: "
    f"{os.path.exists(SOURCE_VIDEO)}"
)

print(
    f"Total clips: "
    f"{len(production_clips)}"
)

print()


for clip in production_clips:

    print(
        f"#{clip['rank']} "
        f"{clip['id']} | "
        f"{clip['start']:.2f}s -> "
        f"{clip['end']:.2f}s | "
        f"{clip['duration']:.2f}s | "
        f"Score {clip['score']}"
    )

    print(
        f"   {clip['title']}"
    )


print()
print(
    f"Manifest saved: "
    f"{OUTPUT_FILE}"
)

print("=" * 60)
