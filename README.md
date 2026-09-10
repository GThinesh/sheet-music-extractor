# YouTube Sheet Music to PDF Converter

A web application that converts YouTube videos of sheet music into printable PDF files. Extract distinct music sheet frames from videos, select/reorder pages, split or crop images, and generate high-quality A4 PDFs optimized for printing.

## Features

- **YouTube Download**: Download videos at highest resolution using yt-dlp
- **Frame Extraction**: Extract distinct frames at configurable intervals with perceptual hash deduplication
- **Smart Selection**: Pairwise comparison view or gallery view to select relevant pages
- **Page Editing**: Reorder pages, split vertically (for 2-column sheets), or crop margins
- **PDF Generation**: Create 300 DPI A4 PDFs with proper scaling and centering
- **Modern UI**: Responsive, dark-themed interface with intuitive workflow

## For Consumers

### How to Use

1. **Download Video**: Paste a YouTube URL containing sheet music and click "Download"
2. **Extract Frames**: Set sample interval (recommended: 5 seconds) and enable smart deduplication, then click "Extract Frames"
3. **Select Pages**: 
   - Use **Compare View** to review frames pairwise (select or cancel candidates)
   - Or switch to **Gallery View** to select/deselect all frames visually
4. **Edit & Arrange**: 
   - Drag to reorder pages
   - Use **Split Vertical** to separate left/right halves of 2-column pages
   - Use **Crop** to trim unwanted margins
5. **Generate PDF**: Click "Generate A4 PDF" to download your printable sheet music

### Example Workflow

For a typical piano tutorial video:
1. Download the YouTube video
2. Extract frames every 5 seconds with deduplication enabled
3. In Compare View: Select distinct pages, cancel duplicates/similar frames
4. In Edit View: Reorder pages as needed, split 2-column pages, crop excess borders
5. Generate PDF and print!

## For Developers

### System Requirements

- Python 3.8+
- Git
- FFmpeg (for video processing via yt-dlp)
- Modern web browser

### Installation

```bash
# Clone the repository
git clone https://github.com/GThinesh/song-sheet.git
cd song-sheet

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Project Structure

```
song-sheet/
├── app.py                 # Main Flask application
├── downloader.py          # YouTube video download (yt-dlp)
├── extractor.py           # Frame extraction & deduplication (OpenCV, PIL, imagehash)
├── pdf_builder.py         # PDF generation from images (Pillow)
├── requirements.txt       # Python dependencies
├── static/                # Static assets (CSS, JS)
│   ├── css/style.css      # Styling
│   └── js/app.js          # Frontend logic
├── templates/             # HTML templates
│   └── index.html         # Main UI
└── output/                # Generated files (video, frames, edited, PDFs)
```

### External Dependencies

#### Python Packages (from requirements.txt)
- **Flask>=3.0**: Web framework
- **yt-dlp>=2024.0**: YouTube video download
- **opencv-python>=4.9**: Video frame extraction
- **imagehash>=4.3**: Perceptual hash for frame deduplication
- **Pillow>=10.0**: Image processing and PDF generation

#### System Dependencies
- **FFmpeg**: Required by yt-dlp for video/audio processing
- **Git**: For version control

### Running the Application

```bash
# Ensure FFmpeg is installed and in PATH
# On Ubuntu/Debian: sudo apt install ffmpeg
# On macOS: brew install ffmpeg
# On Windows: Download from https://ffmpeg.org/download.html

# Start the Flask development server
python app.py

# Open in browser: http://localhost:5000
```

### API Endpoints

- `GET /` - Main page
- `POST /api/download` - Download YouTube video
- `POST /api/extract` - Extract frames from video
- `GET /api/frames` - List available frame images
- `GET /api/frames/<filename>` - Serve specific frame image
- `POST /api/split` - Split image vertically
- `POST /api/crop` - Crop image to rectangle
- `POST /api/generate-pdf` - Generate PDF from image list

### Development Notes

- The app uses in-memory state (suitable for single-user/local use)
- All processing happens server-side; frontend is purely for interaction
- Images are stored temporarily in the `output/` directory
- PDFs are generated at 300 DPI A4 size (2480 × 3508 pixels)
- Frame comparison uses perceptual hashing (average difference threshold: 7)

### Building for Production

For production deployment, consider:
- Using a production WSGI server (Gunicorn, uWSGI)
- Setting `debug=False` in `app.py`
- Configuring proper static file serving
- Implementing user/session isolation for multi-user scenarios

### License

This project is open source and available for modification and redistribution.

---
*Built with Flask, OpenCV, yt-dlp, and Pillow*