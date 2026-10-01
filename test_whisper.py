from faster_whisper import WhisperModel
import time
import os

VIDEO_FILE = "input/test.wav"

print("Loading Whisper model...")

model = WhisperModel(
    "tiny.en",
    device="cuda",
    compute_type="float32"
)

print("Model loaded.")
print(f"Transcribing: {VIDEO_FILE}")

start_time = time.time()

segments, info = model.transcribe(
    VIDEO_FILE,
    beam_size=5,
    vad_filter=True
)

segments = list(segments)

elapsed = time.time() - start_time

print("\n" + "=" * 60)
print("TRANSCRIPTION RESULT")
print("=" * 60)

for segment in segments:
    print(
        f"[{segment.start:.2f}s -> {segment.end:.2f}s] "
        f"{segment.text.strip()}"
    )

print("=" * 60)
print(f"Detected language: {info.language}")
print(f"Audio duration: {info.duration:.2f} seconds")
print(f"Processing time: {elapsed:.2f} seconds")
