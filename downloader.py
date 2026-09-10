"""
downloader.py — Download YouTube videos at highest resolution using yt-dlp.
Configured with Windows-safe path, filename trimming, and disabled mtime updates
to prevent [Errno 22] Invalid argument.
"""

import os
import glob
import yt_dlp


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "video")


def download_video(url: str, output_dir: str = OUTPUT_DIR) -> dict:
    """
    Download a YouTube video at the highest available resolution.

    Returns:
        dict with keys: filepath, title, resolution, ext
    """
    os.makedirs(output_dir, exist_ok=True)
    url = url.strip().strip('"\'')

    # Progress tracking
    result = {}

    def _progress_hook(d):
        if d.get("status") == "finished":
            result["_tmp_filename"] = d.get("filename")

    ydl_opts = {
        # Highest video + highest audio, fallback to best
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        # Windows-safe filename: id + truncated title to avoid MAX_PATH and Errno 22
        "outtmpl": os.path.join(output_dir, "%(id)s_%(title).40s.%(ext)s"),
        "windowsfilenames": True,
        "restrictfilenames": True,
        "trim_file_name": 50,
        # IMPORTANT: updatetime=False prevents os.utime() from failing with [Errno 22] Invalid argument on Windows
        "updatetime": False,
        "progress_hooks": [_progress_hook],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    title = info.get("title", "video")

    # Locate the actual downloaded .mp4 file
    mp4_files = glob.glob(os.path.join(output_dir, "*.mp4"))
    if mp4_files:
        # Get the most recently created mp4
        filepath = max(mp4_files, key=os.path.getmtime)
    else:
        filename = ydl.prepare_filename(info)
        filepath = os.path.splitext(filename)[0] + ".mp4"

    return {
        "filepath": filepath,
        "title": title,
        "resolution": f'{info.get("width", "?")}x{info.get("height", "?")}',
        "ext": "mp4",
    }


if __name__ == "__main__":
    import sys
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=_e-zw3Lf-Uw"
    info = download_video(test_url)
    print(f"Downloaded: {info['filepath']} ({info['resolution']})")
