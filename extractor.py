"""
extractor.py — Extract distinct music-sheet frames from video using fast frame seeking
and perceptual hash deduplication.
"""

import os
import cv2
from PIL import Image
import imagehash

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "frames")


def extract_distinct_frames(
    video_path: str,
    output_dir: str = OUTPUT_DIR,
    sample_interval_sec: float = 5.0,
    dedup: bool = True,
    threshold: int = 7,
) -> list[dict]:
    """
    Extract frames from *video_path* at regular intervals (fast seek).

    Args:
        video_path: Path to video file.
        output_dir: Folder to save PNG frames.
        sample_interval_sec: Seconds between sampled frames (e.g. 3s, 5s, 10s).
        dedup: Whether to filter out consecutive duplicate frames (pHash distance <= threshold).
        threshold: Max Hamming distance to consider two frames "the same sheet" (default: 7).

    Returns:
        List of dicts: [{"filename": "frame_0001.png", "timestamp_sec": 5.0, "timestamp_str": "0:05"}, ...]
    """
    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_skip = max(1, int(fps * sample_interval_sec))

    results: list[dict] = []
    saved_count = 0
    prev_hash = None

    # Fast seek directly to target positions
    for target_pos in range(frame_skip, total_frames, frame_skip):
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_pos)
        ret, frame = cap.read()
        if not ret:
            break

        is_distinct = True
        if dedup:
            pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            cur_hash = imagehash.phash(pil_img)
            if prev_hash is not None and (cur_hash - prev_hash) <= threshold:
                is_distinct = False

        if is_distinct:
            saved_count += 1
            filename = f"frame_{saved_count:04d}.png"
            out_path = os.path.join(output_dir, filename)

            cv2.imwrite(out_path, frame, [cv2.IMWRITE_PNG_COMPRESSION, 3])

            if dedup:
                prev_hash = cur_hash

            timestamp = target_pos / fps
            mins = int(timestamp // 60)
            secs = int(timestamp % 60)
            results.append({
                "filename": filename,
                "timestamp_sec": round(timestamp, 2),
                "timestamp_str": f"{mins}:{secs:02d}",
            })

    cap.release()

    # Fallback: if no frames extracted (very short video or high interval), grab first frame
    if not results and total_frames > 0:
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        if ret:
            out_path = os.path.join(output_dir, "frame_0001.png")
            cv2.imwrite(out_path, frame, [cv2.IMWRITE_PNG_COMPRESSION, 3])
            results.append({"filename": "frame_0001.png", "timestamp_sec": 0.0, "timestamp_str": "0:00"})
        cap.release()

    return results


if __name__ == "__main__":
    import sys
    video = sys.argv[1] if len(sys.argv) > 1 else input("Video path: ")
    frames = extract_distinct_frames(video, sample_interval_sec=5.0)
    print(f"Extracted {len(frames)} frames:")
    for f in frames[:5]:
        print(f"  {f['filename']} @ {f['timestamp_str']}")
