"""
app.py — Flask web application for the Music Sheet → PDF converter.
"""

import os
import uuid
import shutil
from flask import Flask, request, jsonify, send_file, send_from_directory, render_template
from PIL import Image

from downloader import download_video
from extractor import extract_distinct_frames
from pdf_builder import build_pdf

app = Flask(__name__)

BASE_DIR = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
VIDEO_DIR = os.path.join(OUTPUT_DIR, "video")
FRAMES_DIR = os.path.join(OUTPUT_DIR, "frames")
EDITED_DIR = os.path.join(OUTPUT_DIR, "edited")

# In-memory state (single-user, fine for local tool)
state = {
    "video_path": None,
    "frames": [],       # list of dicts from extractor
}


@app.route("/")
def index():
    return render_template("index.html")


# ---------- Step 1: Download ----------

@app.route("/api/download", methods=["POST"])
def api_download():
    data = request.get_json(force=True)
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        # Clean previous run
        for d in (VIDEO_DIR, FRAMES_DIR, EDITED_DIR):
            if os.path.exists(d):
                shutil.rmtree(d)

        info = download_video(url, VIDEO_DIR)
        state["video_path"] = info["filepath"]
        state["frames"] = []
        return jsonify({
            "ok": True,
            "title": info["title"],
            "resolution": info["resolution"],
            "filepath": info["filepath"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------- Step 2: Extract ----------

@app.route("/api/extract", methods=["POST"])
def api_extract():
    if not state["video_path"] or not os.path.exists(state["video_path"]):
        return jsonify({"error": "No video downloaded yet"}), 400

    data = request.get_json(silent=True) or {}
    interval = float(data.get("interval", 5.0))
    dedup = bool(data.get("dedup", True))

    try:
        # Clean previous frames
        for d in (FRAMES_DIR, EDITED_DIR):
            if os.path.exists(d):
                shutil.rmtree(d)

        frames = extract_distinct_frames(
            state["video_path"],
            FRAMES_DIR,
            sample_interval_sec=interval,
            dedup=dedup,
        )
        state["frames"] = frames
        return jsonify({"ok": True, "count": len(frames), "frames": frames})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------- Step 3 & 4: Browse / edit frames ----------

@app.route("/api/frames")
def api_frames_list():
    """Return list of available frame filenames (original + edited)."""
    names = []
    for d in (FRAMES_DIR, EDITED_DIR):
        if os.path.isdir(d):
            names.extend(sorted(os.listdir(d)))
    return jsonify(names)


@app.route("/api/frames/<path:name>")
def api_frame_image(name):
    """Serve a frame image by filename."""
    # Check edited first, then originals
    for d in (EDITED_DIR, FRAMES_DIR):
        path = os.path.join(d, name)
        if os.path.isfile(path):
            return send_from_directory(d, name)
    return jsonify({"error": "not found"}), 404


@app.route("/api/split", methods=["POST"])
def api_split():
    """
    Split an image vertically (left / right halves).
    Body: {"filename": "frame_0001.png"}
    Returns: {"ok": true, "left": "..._left.png", "right": "..._right.png"}
    """
    data = request.get_json(force=True)
    filename = data.get("filename", "")

    # Locate the source image
    src_path = None
    for d in (EDITED_DIR, FRAMES_DIR):
        p = os.path.join(d, filename)
        if os.path.isfile(p):
            src_path = p
            break
    if not src_path:
        return jsonify({"error": "Image not found"}), 404

    os.makedirs(EDITED_DIR, exist_ok=True)
    img = Image.open(src_path)
    w, h = img.size
    mid = w // 2

    base, ext = os.path.splitext(filename)
    left_name = f"{base}_left{ext}"
    right_name = f"{base}_right{ext}"

    img.crop((0, 0, mid, h)).save(os.path.join(EDITED_DIR, left_name))
    img.crop((mid, 0, w, h)).save(os.path.join(EDITED_DIR, right_name))

    return jsonify({"ok": True, "left": left_name, "right": right_name})


@app.route("/api/crop", methods=["POST"])
def api_crop():
    """
    Crop an image to a rectangle.
    Body: {"filename": "...", "x": 0, "y": 0, "width": 500, "height": 300}
    All coordinates are in *original image* pixels.
    Returns: {"ok": true, "cropped": "..._crop.png"}
    """
    data = request.get_json(force=True)
    filename = data.get("filename", "")
    x = int(data.get("x", 0))
    y = int(data.get("y", 0))
    w = int(data.get("width", 0))
    h = int(data.get("height", 0))

    src_path = None
    for d in (EDITED_DIR, FRAMES_DIR):
        p = os.path.join(d, filename)
        if os.path.isfile(p):
            src_path = p
            break
    if not src_path:
        return jsonify({"error": "Image not found"}), 404

    os.makedirs(EDITED_DIR, exist_ok=True)
    img = Image.open(src_path)
    cropped = img.crop((x, y, x + w, y + h))

    base, ext = os.path.splitext(filename)
    crop_name = f"{base}_crop_{uuid.uuid4().hex[:6]}{ext}"
    cropped.save(os.path.join(EDITED_DIR, crop_name))

    return jsonify({"ok": True, "cropped": crop_name})


# ---------- Step 5: Generate PDF ----------

@app.route("/api/generate-pdf", methods=["POST"])
def api_generate_pdf():
    """
    Build a PDF from an ordered list of image filenames.
    Body: {"images": ["frame_0001.png", "frame_0003_left.png", ...]}
    """
    data = request.get_json(force=True)
    image_names = data.get("images", [])
    if not image_names:
        return jsonify({"error": "No images provided"}), 400

    # Resolve full paths
    paths = []
    for name in image_names:
        found = None
        for d in (EDITED_DIR, FRAMES_DIR):
            p = os.path.join(d, name)
            if os.path.isfile(p):
                found = p
                break
        if not found:
            return jsonify({"error": f"Image not found: {name}"}), 404
        paths.append(found)

    try:
        pdf_bytes = build_pdf(paths)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Save to disk and send
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    pdf_path = os.path.join(OUTPUT_DIR, "music_sheet.pdf")
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    return send_file(
        pdf_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="music_sheet.pdf",
    )


@app.route("/api/cleanup", methods=["POST"])
def api_cleanup():
    """Clean up output directories"""
    try:
        # Remove and recreate directories to keep them but empty
        for d in (VIDEO_DIR, FRAMES_DIR, EDITED_DIR):
            if os.path.exists(d):
                shutil.rmtree(d)
            os.makedirs(d, exist_ok=True)

        # Remove PDF if it exists
        pdf_path = os.path.join(OUTPUT_DIR, "music_sheet.pdf")
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

        return jsonify({"ok": True, "message": "Output cleaned up"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)

