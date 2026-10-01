import json
import os
import subprocess
import time

import pysubs2


# =========================================================
# FILES
# =========================================================

TRANSCRIPT_FILE = "output/transcript.json"
MANIFEST_FILE = "output/production_manifest_v6.json"

OUTPUT_DIR = "output/final_clips"


# =========================================================
# CAPTION SETTINGS
# =========================================================

FONT_NAME = "Arial"
FONT_SIZE = 68

PRIMARY_COLOR = "&H00FFFFFF"
OUTLINE_COLOR = "&H00000000"

OUTLINE = 5
SHADOW = 2

MARGIN_LEFT = 80
MARGIN_RIGHT = 80
MARGIN_VERTICAL = 220


# =========================================================
# LOAD TRANSCRIPT
# =========================================================

if not os.path.exists(TRANSCRIPT_FILE):
    raise FileNotFoundError(
        f"Transcript not found: {TRANSCRIPT_FILE}"
    )


with open(
    TRANSCRIPT_FILE,
    "r",
    encoding="utf-8"
) as f:
    transcript = json.load(f)


segments = transcript.get(
    "segments",
    []
)


if not segments:
    raise RuntimeError(
        "No transcript segments found."
    )


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
# FORMAT CAPTION TEXT
# =========================================================

def format_caption(text):

    text = " ".join(
        text.strip().split()
    )

    return text


# =========================================================
# CREATE ASS FILE
# =========================================================

def create_ass(
    clip,
    ass_file
):

    clip_start = float(
        clip["start"]
    )

    clip_end = float(
        clip["end"]
    )


    subtitles = pysubs2.SSAFile()


    # -----------------------------------------------------
    # VIDEO CANVAS
    # -----------------------------------------------------

    subtitles.info[
        "PlayResX"
    ] = "1080"

    subtitles.info[
        "PlayResY"
    ] = "1920"


    # -----------------------------------------------------
    # CAPTION STYLE
    # -----------------------------------------------------

    style = pysubs2.SSAStyle()

    style.fontname = FONT_NAME
    style.fontsize = FONT_SIZE

    style.primarycolor = pysubs2.Color(
        255,
        255,
        255,
        0
    )

    style.outlinecolor = pysubs2.Color(
        0,
        0,
        0,
        0
    )

    style.outline = OUTLINE
    style.shadow = SHADOW

    # Bottom-center
    style.alignment = 2

    style.marginl = MARGIN_LEFT
    style.marginr = MARGIN_RIGHT
    style.marginv = MARGIN_VERTICAL

    style.bold = True


    subtitles.styles[
        "Default"
    ] = style


    # -----------------------------------------------------
    # ADD TRANSCRIPT SEGMENTS
    # -----------------------------------------------------

    caption_count = 0


    for segment in segments:

        segment_start = float(
            segment["start"]
        )

        segment_end = float(
            segment["end"]
        )


        # No overlap with this clip
        if segment_end <= clip_start:
            continue

        if segment_start >= clip_end:
            continue


        # -------------------------------------------------
        # Clip the segment to the current video
        # -------------------------------------------------

        visible_start = max(
            segment_start,
            clip_start
        )

        visible_end = min(
            segment_end,
            clip_end
        )


        if visible_end <= visible_start:
            continue


        text = format_caption(
            segment["text"]
        )


        if not text:
            continue


        # Convert to timestamps relative to clip
        start_ms = int(
            (visible_start - clip_start)
            * 1000
        )

        end_ms = int(
            (visible_end - clip_start)
            * 1000
        )


        # -------------------------------------------------
        # ASS automatic wrapping
        # -------------------------------------------------

        event = pysubs2.SSAEvent(
            start=start_ms,
            end=end_ms,
            text=text,
            style="Default"
        )


        subtitles.events.append(
            event
        )


        caption_count += 1


    subtitles.save(
        ass_file,
        format_="ass"
    )


    return caption_count


# =========================================================
# BURN CAPTIONS
# =========================================================

def burn_captions(
    input_file,
    ass_file,
    output_file
):

    # Use a relative path because the project is being
    # executed from D:\AI-Clipping.
    subtitle_path = ass_file.replace(
        "\\",
        "/"
    )


    filter_value = (
        f"ass={subtitle_path}"
    )


    command = [

        "ffmpeg",

        "-y",

        "-i",
        input_file,
        
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",

        "-vf",
        filter_value,

        "-c:v",
        "libx264",

        "-preset",
        "fast",

        "-crf",
        "20",

        "-pix_fmt",
        "yuv420p",

        "-c:a",
        "aac",

        "-b:a",
        "128k",

        "-movflags",
        "+faststart",

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
print("AUTOMATIC CAPTIONS V9")
print("=" * 60)

print(
    f"Transcript segments: "
    f"{len(segments)}"
)

print(
    f"Clips: "
    f"{len(clips)}"
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
    # INPUT
    # -----------------------------------------------------

    vertical_file = os.path.join(
        OUTPUT_DIR,
        f"{clip_id}_vertical.mp4"
    )


    # -----------------------------------------------------
    # CAPTION FILE
    # -----------------------------------------------------

    ass_file = os.path.join(
        OUTPUT_DIR,
        f"{clip_id}_captions.ass"
    )


    # -----------------------------------------------------
    # FINAL VIDEO
    # -----------------------------------------------------

    final_file = os.path.join(
        OUTPUT_DIR,
        f"{clip_id}_final.mp4"
    )


    print(
        f"[{index}/{len(clips)}] "
        f"{clip_id}"
    )


    if not os.path.exists(
        vertical_file
    ):

        print(
            "    FAILED: vertical video not found"
        )

        clip["caption_status"] = (
            "failed"
        )

        failed += 1

        continue


    try:

        # ---------------------------------------------
        # Generate ASS
        # ---------------------------------------------

        caption_count = create_ass(
            clip,
            ass_file
        )


        print(
            f"    Captions: "
            f"{caption_count}"
        )


        # ---------------------------------------------
        # Burn captions
        # ---------------------------------------------

        burn_captions(
            vertical_file,
            ass_file,
            final_file
        )


        if not os.path.exists(
            final_file
        ):

            raise RuntimeError(
                "Final captioned video "
                "was not created."
            )


        file_size = (
            os.path.getsize(
                final_file
            )
            / (1024 * 1024)
        )


        clip["caption_file"] = (
            ass_file
        )

        clip["final_output"] = (
            final_file
        )

        clip["caption_count"] = (
            caption_count
        )

        clip["caption_status"] = (
            "complete"
        )


        successful += 1


        print(
            f"    OK"
        )

        print(
            f"    Output: "
            f"{final_file}"
        )

        print(
            f"    Size: "
            f"{file_size:.2f} MB"
        )


    except Exception as error:

        clip["caption_status"] = (
            "failed"
        )

        clip["caption_error"] = (
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

manifest["captions"] = {

    "status": (
        "complete"
        if failed == 0
        else "partial"
    ),

    "successful": successful,

    "failed": failed,

    "font": FONT_NAME,

    "font_size": FONT_SIZE
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
print("V9 CAPTION RENDER COMPLETE")
print("=" * 60)

print(
    f"Successful: "
    f"{successful}"
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

print(
    "Final videos:"
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
