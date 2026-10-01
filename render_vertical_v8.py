import json
import os
import subprocess
import time


# =========================================================
# FILES
# =========================================================

MANIFEST_FILE = "output/production_manifest_v6.json"

OUTPUT_DIR = "output/final_clips"


# =========================================================
# SETTINGS
# =========================================================

WIDTH = 1080
HEIGHT = 1920

CRF = 20
PRESET = "fast"

AUDIO_BITRATE = "128k"


# =========================================================
# LOAD MANIFEST
# =========================================================

if not os.path.exists(MANIFEST_FILE):

    raise FileNotFoundError(
        f"Manifest not found: {MANIFEST_FILE}"
    )


with open(
    MANIFEST_FILE,
    "r",
    encoding="utf-8"
) as f:

    manifest = json.load(f)


clips = manifest.get(
    "clips",
    []
)


if not clips:

    raise RuntimeError(
        "No clips found in manifest."
    )


# =========================================================
# OUTPUT DIRECTORY
# =========================================================

os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
)


# =========================================================
# RENDER FUNCTION
# =========================================================

def render_vertical(
    input_file,
    output_file
):

    # -----------------------------------------------------
    # The filter does three things:
    #
    # 1. Creates a 1080x1920 blurred background.
    # 2. Scales the original video to fit inside 1080x1920.
    # 3. Places the original video in the center.
    #
    # This avoids cutting off important content.
    # -----------------------------------------------------

    filter_complex = (
        "[0:v]"
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "boxblur=30:10,"
        "setsar=1"
        "[bg];"

        "[0:v]"
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "setsar=1"
        "[fg];"

        "[bg][fg]"
        "overlay="
        "(W-w)/2:"
        "(H-h)/2"
    )


    command = [

        "ffmpeg",

        "-y",

        "-i",
        input_file,

        "-filter_complex",
        filter_complex,

        "-map",
        "0:v:0",

        "-map",
        "0:a:0?",

        "-c:v",
        "libx264",

        "-preset",
        PRESET,

        "-crf",
        str(CRF),

        "-pix_fmt",
        "yuv420p",

        "-c:a",
        "aac",

        "-b:a",
        AUDIO_BITRATE,

        "-movflags",
        "+faststart",

        "-r",
        "30",

        output_file
    ]


    subprocess.run(
        command,
        check=True
    )


# =========================================================
# MAIN
# =========================================================

print()
print("=" * 60)
print("VERTICAL VIDEO RENDERER V8")
print("=" * 60)

print(
    f"Target resolution: "
    f"{WIDTH}x{HEIGHT}"
)

print(
    f"Clips: {len(clips)}"
)

print()


successful = 0
failed = 0

start_time = time.time()


for index, clip in enumerate(
    clips,
    start=1
):

    clip_id = clip["id"]


    # -----------------------------------------------------
    # RAW INPUT
    # -----------------------------------------------------

    raw_file = os.path.join(
        OUTPUT_DIR,
        f"{clip_id}_raw.mp4"
    )


    # -----------------------------------------------------
    # OUTPUT
    # -----------------------------------------------------

    vertical_file = os.path.join(
        OUTPUT_DIR,
        f"{clip_id}_vertical.mp4"
    )


    print(
        f"[{index}/{len(clips)}] "
        f"{clip_id}"
    )


    print(
        f"    Input: "
        f"{raw_file}"
    )


    print(
        f"    Output: "
        f"{vertical_file}"
    )


    if not os.path.exists(
        raw_file
    ):

        print(
            "    FAILED: raw clip not found"
        )

        clip["vertical_status"] = (
            "failed"
        )

        failed += 1

        continue


    try:

        render_vertical(
            raw_file,
            vertical_file
        )


        if not os.path.exists(
            vertical_file
        ):

            raise RuntimeError(
                "FFmpeg finished but "
                "vertical output was not created."
            )


        file_size = (
            os.path.getsize(
                vertical_file
            )
            / (1024 * 1024)
        )


        clip["vertical_output"] = (
            vertical_file
        )

        clip["vertical_status"] = (
            "rendered"
        )


        successful += 1


        print(
            f"    OK"
        )

        print(
            f"    Size: "
            f"{file_size:.2f} MB"
        )


    except Exception as error:

        clip["vertical_status"] = (
            "failed"
        )

        clip["vertical_error"] = (
            str(error)
        )


        failed += 1


        print(
            f"    FAILED: {error}"
        )


    print()


# =========================================================
# UPDATE MANIFEST
# =========================================================

manifest["vertical_render"] = {

    "status": (
        "complete"
        if failed == 0
        else "partial"
    ),

    "width": WIDTH,

    "height": HEIGHT,

    "successful": successful,

    "failed": failed
}


with open(
    MANIFEST_FILE,
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
# FINAL REPORT
# =========================================================

elapsed = time.time() - start_time


print("=" * 60)
print("V8 VERTICAL RENDER COMPLETE")
print("=" * 60)

print(
    f"Successful: {successful}"
)

print(
    f"Failed: {failed}"
)

print(
    f"Resolution: "
    f"{WIDTH}x{HEIGHT}"
)

print(
    f"Processing time: "
    f"{elapsed:.2f}s"
)

print()

print(
    "Output directory:"
)

print(
    OUTPUT_DIR
)

print()

print(
    "Manifest updated:"
)

print(
    MANIFEST_FILE
)

print("=" * 60)
