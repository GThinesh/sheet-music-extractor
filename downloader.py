"""
downloader.py — Download YouTube videos at highest resolution using yt-dlp.
"""

import os
import yt_dlp


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "video")


def download_video(url: str, output_dir: str = OUTPUT_DIR) -> dict:
    """
    Download a YouTube video at the highest available resolution.

    Returns:
        dict with keys: filepath, title, resolution, ext
    """
    os.makedirs(output_dir, exist_ok=True)

    # We'll capture info via a progress hook
    result = {}

    def _progress_hook(d):
        if d["status"] == "finished":
            result["_tmp_filename"] = d["filename"]

    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
        "progress_hooks": [_progress_hook],
        # Avoid issues with long filenames
        "restrictfilenames": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    title = info.get("title", "video")
    # yt-dlp sanitises the filename; reconstruct it
    filename = ydl.prepare_filename(info)
    # After merge the extension is always mp4
    filepath = os.path.splitext(filename)[0] + ".mp4"

    return {
        "filepath": filepath,
        "title": title,
        "resolution": f'{info.get("width", "?")}x{info.get("height", "?")}',
        "ext": "mp4",
    }


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else input("YouTube URL: ")
    info = download_video(url)
    print(f"Downloaded: {info['filepath']}  ({info['resolution']})")

