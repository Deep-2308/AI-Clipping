from ultralytics import YOLO
import cv2
import json
from pathlib import Path

VIDEO = "output/final_clips/clip_01_raw.mp4"
MODEL = "yolo11n.pt"
OUTPUT = "output/visual_analysis_v12.json"

model = YOLO(MODEL)

cap = cv2.VideoCapture(VIDEO)

fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
duration = total_frames / fps if fps else 0

print(f"Video FPS: {fps}")
print(f"Total frames: {total_frames}")
print(f"Duration: {duration:.2f}s")
print("Running YOLO person tracking...")

tracking_data = []

results = model.track(
    source=VIDEO,
    persist=True,
    tracker="bytetrack.yaml",
    classes=[0],
    device=0,
    stream=True,
    verbose=False,
)

for frame_index, result in enumerate(results):
    people = []

    if result.boxes is not None:
        boxes = result.boxes

        for i in range(len(boxes)):
            xyxy = boxes.xyxy[i].cpu().numpy().tolist()

            track_id = None
            if boxes.id is not None:
                track_id = int(boxes.id[i].item())

            confidence = float(boxes.conf[i].item())

            x1, y1, x2, y2 = xyxy

            people.append({
                "track_id": track_id,
                "confidence": confidence,
                "bbox": {
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "width": x2 - x1,
                    "height": y2 - y1,
                    "center_x": (x1 + x2) / 2,
                    "center_y": (y1 + y2) / 2,
                }
            })

    tracking_data.append({
        "frame": frame_index,
        "time": frame_index / fps if fps else 0,
        "people": people,
    })

    if frame_index % 100 == 0:
        print(f"Processed {frame_index}/{total_frames} frames")

cap.release()

output = {
    "video": VIDEO,
    "fps": fps,
    "total_frames": total_frames,
    "duration": duration,
    "tracking": tracking_data,
}

Path(OUTPUT).parent.mkdir(parents=True, exist_ok=True)

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2)

print()
print("Visual analysis complete.")
print(f"Saved: {OUTPUT}")
print(f"Frames analyzed: {len(tracking_data)}")
