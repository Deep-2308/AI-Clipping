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


source_video = manifest["source_video"]
clips = manifest["clips"]


if not os.path.exists(source_video):
    raise FileNotFoundError(
        f"Source video not found: {source_video}"
    )


os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
)


# =========================================================
# CHECK FFMPEG
# =========================================================

try:

    subprocess.run(
        ["ffmpeg", "-version"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True
    )

except Exception:

    raise RuntimeError(
        "FFmpeg was not found in PATH."
    )


# =========================================================
# EXTRACT FUNCTION
# =========================================================

def extract_clip(
    source,
    start,
    end,
    output
):

    duration = end - start

    command = [
        "ffmpeg",
        "-y",

        "-ss",
        str(start),

        "-i",
        source,

        "-t",
        str(duration),

        "-map",
        "0:v:0",

        "-map",
        "0:a:0?",

        "-c:v",
        "libx264",

        "-preset",
        "fast",

        "-crf",
        "20",

        "-c:a",
        "aac",

        "-b:a",
        "128k",

        "-movflags",
        "+faststart",

        output
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
print("AI CLIP EXTRACTION V7")
print("=" * 60)

print(
    f"Source: {source_video}"
)

print(
    f"Total clips: {len(clips)}"
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

    start = float(
        clip["start"]
    )

    end = float(
        clip["end"]
    )

    duration = end - start


    output_file = os.path.join(
        OUTPUT_DIR,
        f"{clip_id}_raw.mp4"
    )


    print(
        f"[{index}/{len(clips)}] "
        f"{clip_id}"
    )

    print(
        f"    {start:.2f}s -> "
        f"{end:.2f}s "
        f"({duration:.2f}s)"
    )


    try:

        extract_clip(
            source_video,
            start,
            end,
            output_file
        )


        if not os.path.exists(
            output_file
        ):

            raise RuntimeError(
                "FFmpeg completed but output "
                "file was not created."
            )


        file_size = (
            os.path.getsize(
                output_file
            ) / (1024 * 1024)
        )


        clip["raw_output"] = (
            output_file
        )

        clip["status"] = (
            "extracted"
        )


        successful += 1


        print(
            f"    OK: "
            f"{output_file}"
        )

        print(
            f"    Size: "
            f"{file_size:.2f} MB"
        )


    except Exception as error:

        clip["status"] = "failed"

        clip["error"] = str(error)

        failed += 1


        print(
            f"    FAILED: {error}"
        )


    print()


# =========================================================
# UPDATE MANIFEST
# =========================================================

manifest["extraction"] = {

    "status": (
        "complete"
        if failed == 0
        else "partial"
    ),

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
print("V7 EXTRACTION COMPLETE")
print("=" * 60)

print(
    f"Successful: {successful}"
)

print(
    f"Failed: {failed}"
)

print(
    f"Processing time: "
    f"{elapsed:.2f}s"
)

print()

print(
    f"Output directory: "
    f"{OUTPUT_DIR}"
)

print(
    f"Manifest updated: "
    f"{MANIFEST_FILE}"
)

print("=" * 60)
