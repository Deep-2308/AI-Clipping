from pathlib import Path
import json

import cv2
from scenedetect import open_video, SceneManager
from scenedetect.detectors import AdaptiveDetector


VIDEO = "output/final_clips/clip_01_raw.mp4"
OUTPUT = "output/scene_analysis_v12.json"

# Lower threshold = more sensitive to visual changes.
# Start here, then tune based on the actual result.
THRESHOLD = 40.0


def main():
    print("Loading video...")

    video = open_video(VIDEO)

    fps = video.frame_rate
    duration = video.duration.seconds

    print(f"FPS: {fps:.2f}")
    print(f"Duration: {duration:.2f}s")
    print("Detecting visual shot changes...")

    scene_manager = SceneManager()

    scene_manager.add_detector(
    AdaptiveDetector(
        adaptive_threshold=3.0,
        min_scene_len=15,
    )
)

    scene_manager.detect_scenes(video)

    scenes = scene_manager.get_scene_list()

    output_scenes = []

    for index, (start, end) in enumerate(scenes, start=1):
        start_time = start.seconds
        end_time = end.seconds

        output_scenes.append({
            "scene_id": index,
            "start": round(start_time, 3),
            "end": round(end_time, 3),
            "duration": round(end_time - start_time, 3),
        })

    result = {
        "video": VIDEO,
        "fps": float(fps),
        "duration": duration,
        "threshold": THRESHOLD,
        "scene_count": len(output_scenes),
        "scenes": output_scenes,
    }

    Path(OUTPUT).parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print()
    print("Scene detection complete.")
    print(f"Scenes detected: {len(output_scenes)}")
    print(f"Saved: {OUTPUT}")
    print()

    for scene in output_scenes:
        print(
            f"Scene {scene['scene_id']:02d}: "
            f"{scene['start']:7.2f}s -> "
            f"{scene['end']:7.2f}s "
            f"({scene['duration']:5.2f}s)"
        )


if __name__ == "__main__":
    main()
