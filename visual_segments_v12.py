import cv2
import json
from pathlib import Path
from ultralytics import YOLO


VIDEO = "output/final_clips/clip_01_raw.mp4"
OUTPUT = "output/visual_segments_v12.json"
MODEL = "yolo11n.pt"

SAMPLE_INTERVAL = 1.0
CONFIDENCE_THRESHOLD = 0.50


def frame_difference(frame_a, frame_b):
    """Calculate normalized visual difference between two frames."""
    a = cv2.resize(frame_a, (320, 180))
    b = cv2.resize(frame_b, (320, 180))

    gray_a = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)

    diff = cv2.absdiff(gray_a, gray_b)

    return float(diff.mean()) / 255.0


def classify_frame(result):
    """Extract basic visual information from YOLO."""
    people = []

    if result.boxes is None:
        return people

    for i in range(len(result.boxes)):
        confidence = float(result.boxes.conf[i].item())

        if confidence < CONFIDENCE_THRESHOLD:
            continue

        class_id = int(result.boxes.cls[i].item())

        if class_id != 0:
            continue

        x1, y1, x2, y2 = result.boxes.xyxy[i].cpu().numpy()

        people.append({
            "confidence": confidence,
            "bbox": {
                "x1": float(x1),
                "y1": float(y1),
                "x2": float(x2),
                "y2": float(y2),
                "width": float(x2 - x1),
                "height": float(y2 - y1),
                "center_x": float((x1 + x2) / 2),
                "center_y": float((y1 + y2) / 2),
            }
        })

    return people


def main():
    print("Loading video...")

    cap = cv2.VideoCapture(VIDEO)

    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {VIDEO}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    duration = total_frames / fps

    print(f"FPS: {fps:.2f}")
    print(f"Frames: {total_frames}")
    print(f"Duration: {duration:.2f}s")

    print()
    print("Loading YOLO...")

    model = YOLO(MODEL)

    print("Sampling frames...")

    samples = []

    previous_frame = None
    sample_index = 0

    while True:
        timestamp = sample_index * SAMPLE_INTERVAL

        if timestamp >= duration:
            break

        frame_number = int(timestamp * fps)

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

        success, frame = cap.read()

        if not success:
            break

        result = model(
            frame,
            device=0,
            verbose=False
        )[0]

        people = classify_frame(result)

        difference = None

        if previous_frame is not None:
            difference = frame_difference(previous_frame, frame)

        samples.append({
            "sample": sample_index,
            "time": round(timestamp, 3),
            "people_count": len(people),
            "people": people,
            "visual_difference": difference,
        })

        previous_frame = frame.copy()

        print(
            f"{timestamp:6.2f}s | "
            f"people={len(people)} | "
            f"diff={difference if difference is not None else 0:.3f}"
        )

        sample_index += 1

    cap.release()

    result = {
        "video": VIDEO,
        "fps": float(fps),
        "duration": float(duration),
        "sample_interval": SAMPLE_INTERVAL,
        "sample_count": len(samples),
        "samples": samples,
    }

    Path(OUTPUT).parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print()
    print("Visual sampling complete.")
    print(f"Samples analyzed: {len(samples)}")
    print(f"Saved: {OUTPUT}")
    
        # Build candidate visual segments from the sampled measurements.
    samples = result["samples"]

    segments = []

    if samples:
        segment_start = samples[0]["time"]
        previous_people = samples[0]["people_count"]

        for i in range(1, len(samples)):
            current = samples[i]

            diff = current["visual_difference"] or 0.0
            people_changed = (
                abs(current["people_count"] - previous_people) >= 2
            )

            # A strong visual change or major change in detected
            # person count can indicate a new visual state.
            visual_change = diff >= 0.25

            if visual_change or people_changed:
                segments.append({
                    "start": round(segment_start, 3),
                    "end": round(current["time"], 3),
                })

                segment_start = current["time"]

            previous_people = current["people_count"]

        segments.append({
            "start": round(segment_start, 3),
            "end": round(duration, 3),
        })

    # Merge extremely short segments.
    merged_segments = []

    for segment in segments:
        duration_segment = segment["end"] - segment["start"]

        if (
            merged_segments
            and duration_segment < 1.5
        ):
            merged_segments[-1]["end"] = segment["end"]
        else:
            merged_segments.append(segment)

    for index, segment in enumerate(merged_segments, start=1):
        segment["segment_id"] = index
        segment["duration"] = round(
            segment["end"] - segment["start"],
            3
        )

    result["visual_segments"] = merged_segments

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print()
    print("Candidate visual segments:")
    for segment in merged_segments:
        print(
            f"Segment {segment['segment_id']:02d}: "
            f"{segment['start']:.2f}s -> "
            f"{segment['end']:.2f}s "
            f"({segment['duration']:.2f}s)"
        )


if __name__ == "__main__":
    main()
