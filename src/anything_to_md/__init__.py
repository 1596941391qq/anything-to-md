"""
Anything-to-MD: Convert any file to LLM-ready Markdown

Combines Microsoft MarkItDown with Claude Code Skill capabilities
for comprehensive document processing.

Features:
- PDF: MinerU OCR → MarkItDown → pypdf fallback chain
- Video: Intelligent routing (subtitle → audio transcribe → frame OCR)
- Office: Word, Excel, PowerPoint via MarkItDown
- Audio: Speech transcription
- Images: OCR extraction
"""

__version__ = "0.2.0"

from .converter import AnythingToMD
from .video_router import (
    VideoRouter,
    VideoProbe,
    AudioTranscriber,
    FrameExtractor,
    FrameOCR,
    ContentFusion,
    ExtractionStrategy,
    VideoProbeResult,
    TranscriptSegment,
    VideoExtractionResult,
    extract_video_content,
)

__all__ = [
    "AnythingToMD",
    "__version__",
    # Video Router exports
    "VideoRouter",
    "VideoProbe",
    "AudioTranscriber",
    "FrameExtractor",
    "FrameOCR",
    "ContentFusion",
    "ExtractionStrategy",
    "VideoProbeResult",
    "TranscriptSegment",
    "VideoExtractionResult",
    "extract_video_content",
]
