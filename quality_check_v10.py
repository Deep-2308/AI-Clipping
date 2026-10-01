import json
import os
import subprocess
import time


# =========================================================
# FILES
# =========================================================

MANIFEST_FILE = "output/production_manifest_v6.json"


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


clips = manifest.get("clips", [])


if not clips:
    raise RuntimeError(
        "No clips found in manifest."
    )


# =========================================================
# FFPROBE
# =========================================================

def probe_video(file_path):

    command = [
        "ffprobe",

        "-v",
        "error",

        "-show_entries",
        "stream=index,codec_type,codec_name,width,height,"
        "r_frame_rate,duration:format=duration",

        "-of",
        "json",

        file_path
    ]


    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True
    )


    return json.loads(
        result.stdout
    )


# =========================================================
# PARSE FPS
# =========================================================

def parse_fps(value):

    try:

        if "/" in value:

            numerator, denominator = (
                value.split("/")
            )

            return (
                float(numerator)
                / float(denominator)
            )

        return float(value)

    except Exception:

        return 0.0


# =========================================================
# VALIDATE VIDEO
# =========================================================

def validate_clip(
    clip,
    index
):

    clip_id = clip["id"]

    expected_start = float(
        clip["start"]
    )

    expected_end = float(
        clip["end"]
    )

    expected_duration = (
        expected_end
        - expected_start
    )


    final_file = clip.get(
        "final_output"
    )


    result = {

        "id": clip_id,

        "file": final_file,

        "passed": False,

        "checks": {},

        "errors": []
    }


    # -----------------------------------------------------
    # File existence
    # -----------------------------------------------------

    if not final_file:

        result["errors"].append(
            "No final output path in manifest."
        )

        return result


    if not os.path.exists(
        final_file
    ):

        result["errors"].append(
            "Final video file does not exist."
        )

        return result


    result["checks"][
        "file_exists"
    ] = True


    # -----------------------------------------------------
    # File size
    # -----------------------------------------------------

    file_size = os.path.getsize(
        final_file
    )


    result["file_size_mb"] = round(
        file_size / (1024 * 1024),
        2
    )


    if file_size <= 10000:

        result["errors"].append(
            "File size is suspiciously small."
        )

    else:

        result["checks"][
            "file_size"
        ] = True


    # -----------------------------------------------------
    # FFprobe
    # -----------------------------------------------------

    try:

        probe = probe_video(
            final_file
        )

    except Exception as error:

        result["errors"].append(
            f"FFprobe failed: {error}"
        )

        return result


    streams = probe.get(
        "streams",
        []
    )


    # -----------------------------------------------------
    # Video stream
    # -----------------------------------------------------

    video_streams = [
        stream
        for stream in streams
        if stream.get("codec_type")
        == "video"
    ]


    if not video_streams:

        result["errors"].append(
            "No video stream found."
        )

    else:

        video = video_streams[0]

        width = int(
            video.get("width", 0)
        )

        height = int(
            video.get("height", 0)
        )

        fps = parse_fps(
            video.get(
                "r_frame_rate",
                "0/1"
            )
        )

        codec = video.get(
            "codec_name",
            ""
        )


        result["width"] = width
        result["height"] = height
        result["fps"] = round(
            fps,
            2
        )
        result["video_codec"] = codec


        # Resolution
        if (
            width == 1080
            and height == 1920
        ):

            result["checks"][
                "resolution"
            ] = True

        else:

            result["errors"].append(
                f"Wrong resolution: "
                f"{width}x{height}"
            )


        # FPS
        if fps > 0:

            result["checks"][
                "fps"
            ] = True

        else:

            result["errors"].append(
                "Invalid FPS."
            )


        # Codec
        if codec == "h264":

            result["checks"][
                "video_codec"
            ] = True

        else:

            result["errors"].append(
                f"Unexpected video codec: "
                f"{codec}"
            )


    # -----------------------------------------------------
    # Audio stream
    # -----------------------------------------------------

    audio_streams = [
        stream
        for stream in streams
        if stream.get("codec_type")
        == "audio"
    ]


    if audio_streams:

        result["audio"] = True

        result["checks"][
            "audio"
        ] = True

    else:

        result["audio"] = False

        result["errors"].append(
            "No audio stream found."
        )


    # -----------------------------------------------------
    # Duration
    # -----------------------------------------------------

    format_info = probe.get(
        "format",
        {}
    )


    actual_duration = float(
        format_info.get(
            "duration",
            0
        )
    )


    result["actual_duration"] = round(
        actual_duration,
        2
    )


    result["expected_duration"] = round(
        expected_duration,
        2
    )


    duration_difference = abs(
        actual_duration
        - expected_duration
    )


    result["duration_difference"] = round(
        duration_difference,
        2
    )


    # Allow up to 0.5 sec difference.
    if duration_difference <= 0.5:

        result["checks"][
            "duration"
        ] = True

    else:

        result["errors"].append(
            f"Duration mismatch: "
            f"expected "
            f"{expected_duration:.2f}s, "
            f"actual "
            f"{actual_duration:.2f}s"
        )


    # -----------------------------------------------------
    # Final result
    # -----------------------------------------------------

    result["passed"] = (
        len(result["errors"]) == 0
    )


    return result


# =========================================================
# MAIN
# =========================================================

print()
print("=" * 60)
print("AUTOMATED QUALITY CONTROL V10")
print("=" * 60)

print(
    f"Videos to check: "
    f"{len(clips)}"
)

print()


start_time = time.time()

results = []

passed = 0
failed = 0


for index, clip in enumerate(
    clips,
    start=1
):

    print(
        f"[{index}/{len(clips)}] "
        f"Checking {clip['id']}..."
    )


    result = validate_clip(
        clip,
        index
    )


    results.append(
        result
    )


    if result["passed"]:

        passed += 1

        clip["qc_status"] = (
            "passed"
        )

        print(
            "    PASS"
        )


    else:

        failed += 1

        clip["qc_status"] = (
            "failed"
        )

        print(
            "    FAILED"
        )

        for error in result[
            "errors"
        ]:

            print(
                f"    - {error}"
            )


    print()


# =========================================================
# UPDATE MANIFEST
# =========================================================

manifest["quality_control"] = {

    "status": (
        "passed"
        if failed == 0
        else "failed"
    ),

    "total": len(clips),

    "passed": passed,

    "failed": failed,

    "results": results
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
print("V10 QUALITY CONTROL COMPLETE")
print("=" * 60)

print(
    f"Total: "
    f"{len(clips)}"
)

print(
    f"Passed: "
    f"{passed}"
)

print(
    f"Failed: "
    f"{failed}"
)

print(
    f"Processing time: "
    f"{elapsed:.2f}s"
)

print()


if failed == 0:

    print(
        "STATUS: ALL VIDEOS PASSED QC"
    )

else:

    print(
        "STATUS: SOME VIDEOS FAILED QC"
    )


print()

print(
    f"Manifest updated: "
    f"{MANIFEST_FILE}"
)

print("=" * 60)
