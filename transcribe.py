from faster_whisper import WhisperModel
import json
import os
import time

INPUT_FILE = "input/real_test.mp4"
OUTPUT_FILE = "output/transcript.json"

print("Loading Whisper model...")

model = WhisperModel(
    "tiny.en",
    device="cuda",
    compute_type="float32"
)

print("Model loaded.")
print(f"Transcribing: {INPUT_FILE}")

start_time = time.time()

segments, info = model.transcribe(
    INPUT_FILE,
    beam_size=5,
    vad_filter=True,
    word_timestamps=True
)

segments = list(segments)

transcript = {
    "source_file": INPUT_FILE,
    "language": info.language,
    "duration": info.duration,
    "segments": []
}

for segment in segments:
    words = []

    if segment.words:
        for word in segment.words:
            words.append({
                "word": word.word.strip(),
                "start": round(word.start, 2),
                "end": round(word.end, 2)
            })

    transcript["segments"].append({
        "start": round(segment.start, 2),
        "end": round(segment.end, 2),
        "text": segment.text.strip(),
        "words": words
    })

os.makedirs("output", exist_ok=True)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(transcript, f, indent=2, ensure_ascii=False)

elapsed = time.time() - start_time

print()
print("=" * 60)
print("TRANSCRIPTION COMPLETE")
print("=" * 60)
print(f"Language: {info.language}")
print(f"Duration: {info.duration:.2f} seconds")
print(f"Segments: {len(segments)}")
print(f"Processing time: {elapsed:.2f} seconds")
print(f"Saved to: {OUTPUT_FILE}")
print("=" * 60)
