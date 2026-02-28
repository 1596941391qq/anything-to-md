"""
Video Intelligent Router - Smart content extraction from video files

Implements a probe-decide-extract-fuse pipeline:
1. PROBE: Detect subtitles, audio, and on-screen text
2. DECIDE: Choose optimal extraction strategy
3. EXTRACT: Run appropriate extraction pipelines
4. FUSE: Merge results with timeline alignment
"""

import os
import json
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib

# Lazy imports to avoid import errors
_rapidocr = None
_faster_whisper = None
_scenedetect = None
_imagehash = None
_pil_image = None


def _get_rapidocr():
    global _rapidocr
    if _rapidocr is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _rapidocr = RapidOCR
        except ImportError:
            pass
    return _rapidocr


def _get_faster_whisper():
    global _faster_whisper
    if _faster_whisper is None:
        try:
            from faster_whisper import WhisperModel
            _faster_whisper = WhisperModel
        except ImportError:
            pass
    return _faster_whisper


def _get_scenedetect():
    global _scenedetect
    if _scenedetect is None:
        try:
            from scenedetect import detect, ContentDetector
            _scenedetect = (detect, ContentDetector)
        except ImportError:
            pass
    return _scenedetect


def _get_imagehash():
    global _imagehash
    if _imagehash is None:
        try:
            import imagehash
            _imagehash = imagehash
        except ImportError:
            pass
    return _imagehash


def _get_pil():
    global _pil_image
    if _pil_image is None:
        try:
            from PIL import Image
            _pil_image = Image
        except ImportError:
            pass
    return _pil_image


class ExtractionStrategy(Enum):
    """Video extraction strategies based on content type"""
    EMBEDDED_SUBTITLE = "embedded_subtitle"      # Has internal subtitle track
    SIDECAR_SUBTITLE = "sidecar_subtitle"        # Has .srt/.vtt file
    AUDIO_TRANSCRIBE = "audio_transcribe"        # Pure audio (podcast, interview)
    VISUAL_OCR = "visual_ocr"                    # On-screen text (PPT recording)
    HYBRID = "hybrid"                            # Mix of audio + visual
    FULL_PIPELINE = "full_pipeline"              # Extract everything


@dataclass
class VideoProbeResult:
    """Result of video probing phase"""
    has_audio: bool = False
    has_embedded_subtitle: bool = False
    has_sidecar_subtitle: bool = False
    has_visual_text: bool = False  # Detected via sample frame OCR
    duration_seconds: float = 0.0
    subtitle_streams: List[Dict] = field(default_factory=list)
    audio_streams: List[Dict] = field(default_factory=list)
    sample_text_detected: str = ""  # Text from sample frame OCR


@dataclass
class TranscriptSegment:
    """A segment of transcribed or OCR'd text with timestamp"""
    start_time: float  # seconds
    end_time: float    # seconds
    text: str
    source: str  # "audio", "subtitle", "ocr"
    confidence: float = 1.0


@dataclass
class VideoExtractionResult:
    """Complete result of video content extraction"""
    strategy_used: ExtractionStrategy
    transcript_segments: List[TranscriptSegment] = field(default_factory=list)
    frames_extracted: int = 0
    frames_with_text: int = 0
    audio_transcribed: bool = False
    subtitles_extracted: bool = False
    markdown: str = ""
    images_dir: Optional[Path] = None
    error: Optional[str] = None


class VideoProbe:
    """Phase 1: Probe video to determine content type"""

    VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.wmv', '.m4v', '.flv'}

    @classmethod
    def is_video(cls, path: Path) -> bool:
        return path.suffix.lower() in cls.VIDEO_EXTENSIONS

    def probe(self, video_path: Path, sample_frames: int = 5) -> VideoProbeResult:
        """Probe video file for content analysis"""
        result = VideoProbeResult()

        # Run ffprobe to get streams info
        try:
            proc = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                 '-print_format', 'json', str(video_path)],
                capture_output=True, text=True, timeout=30, check=False
            )
            if proc.returncode == 0 and proc.stdout.strip():
                data = json.loads(proc.stdout)

                # Analyze streams
                for stream in data.get('streams', []):
                    codec_type = stream.get('codec_type', '')
                    if codec_type == 'audio':
                        result.has_audio = True
                        result.audio_streams.append(stream)
                    elif codec_type == 'subtitle':
                        result.has_embedded_subtitle = True
                        result.subtitle_streams.append(stream)

                # Get duration
                fmt = data.get('format', {})
                duration = fmt.get('duration')
                if duration:
                    result.duration_seconds = float(duration)

        except Exception:
            pass

        # Check for sidecar subtitle files
        sidecar_exts = ['.srt', '.vtt', '.ass', '.ssa']
        for ext in sidecar_exts:
            sidecar = video_path.with_suffix(ext)
            if sidecar.exists():
                result.has_sidecar_subtitle = True
                break

        # Sample frame OCR to detect on-screen text
        if result.duration_seconds > 0:
            sample_text = self._sample_frame_ocr(video_path, result.duration_seconds, sample_frames)
            result.sample_text_detected = sample_text
            result.has_visual_text = len(sample_text.strip()) > 10

        return result

    def _sample_frame_ocr(self, video_path: Path, duration: float, num_samples: int) -> str:
        """Extract sample frames and run quick OCR to detect on-screen text"""
        RapidOCR = _get_rapidocr()
        if RapidOCR is None:
            return ""

        temp_dir = Path(tempfile.mkdtemp(prefix='video_probe_'))
        try:
            # Sample frames evenly across the video
            timestamps = [duration * (i + 1) / (num_samples + 1) for i in range(num_samples)]

            all_text = []
            ocr = RapidOCR()

            for i, ts in enumerate(timestamps):
                frame_path = temp_dir / f"frame_{i:03d}.jpg"
                try:
                    # Extract single frame
                    proc = subprocess.run(
                        ['ffmpeg', '-y', '-v', 'error', '-ss', str(ts),
                         '-i', str(video_path), '-vframes', '1',
                         '-q:v', '2', str(frame_path)],
                        capture_output=True, timeout=10, check=False
                    )
                    if proc.returncode == 0 and frame_path.exists():
                        # Run OCR
                        result, elapse = ocr(str(frame_path))
                        if result:
                            for item in result:
                                if item and len(item) > 1:
                                    text = str(item[1]).strip()
                                    if text and len(text) > 2:
                                        all_text.append(text)
                except Exception:
                    pass

            return ' '.join(all_text[:10])  # Return first 10 detected texts

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class AudioTranscriber:
    """Phase 2a: Transcribe audio using faster-whisper"""

    def __init__(self, model_size: str = "base", device: str = "cpu"):
        self.model_size = model_size
        self.device = device
        self._model = None

    def _get_model(self):
        if self._model is None:
            WhisperModel = _get_faster_whisper()
            if WhisperModel is None:
                raise ImportError("faster-whisper not installed")
            self._model = WhisperModel(self.model_size, device=self.device, compute_type="int8")
        return self._model

    def transcribe(self, video_path: Path, language: str = None) -> List[TranscriptSegment]:
        """Transcribe audio from video file"""
        segments = []

        try:
            model = self._get_model()

            # Extract audio to temp file for faster processing
            temp_audio = Path(tempfile.mktemp(suffix='.wav'))
            try:
                proc = subprocess.run(
                    ['ffmpeg', '-y', '-v', 'error', '-i', str(video_path),
                     '-vn', '-ac', '1', '-ar', '16000', str(temp_audio)],
                    capture_output=True, timeout=300, check=False
                )
                if proc.returncode != 0 or not temp_audio.exists():
                    return []

                # Transcribe
                transcribe_kwargs = {"task": "transcribe"}
                if language:
                    transcribe_kwargs["language"] = language

                trans_segments, info = model.transcribe(str(temp_audio), **transcribe_kwargs)

                for seg in trans_segments:
                    segments.append(TranscriptSegment(
                        start_time=seg.start,
                        end_time=seg.end,
                        text=seg.text.strip(),
                        source="audio",
                        confidence=seg.no_speech_prob
                    ))

            finally:
                if temp_audio.exists():
                    temp_audio.unlink()

        except Exception:
            pass

        return segments


class FrameExtractor:
    """Phase 2b: Extract keyframes using scene detection"""

    def __init__(self, threshold: float = 27.0, min_scene_len: int = 15):
        self.threshold = threshold
        self.min_scene_len = min_scene_len

    def extract_keyframes(
        self,
        video_path: Path,
        output_dir: Path,
        max_frames: int = 200
    ) -> List[Tuple[Path, float]]:
        """Extract keyframes from video using scene detection

        Returns: List of (frame_path, timestamp) tuples
        """
        scenedetect = _get_scenedetect()
        imagehash = _get_imagehash()
        Image = _get_pil()

        if scenedetect is None or imagehash is None or Image is None:
            return self._extract_evenly(video_path, output_dir, max_frames)

        detect, ContentDetector = scenedetect

        output_dir.mkdir(parents=True, exist_ok=True)
        frames = []

        try:
            # Detect scene changes
            scene_list = detect(str(video_path), ContentDetector(
                threshold=self.threshold,
                min_scene_len=self.min_scene_len
            ))

            # Also add middle frames for long scenes
            timestamps = []
            for i, scene in enumerate(scene_list):
                # Start of scene
                timestamps.append(scene[0].get_seconds())
                # Middle of scene if long enough
                duration = scene[1].get_seconds() - scene[0].get_seconds()
                if duration > 10:
                    timestamps.append(scene[0].get_seconds() + duration / 2)

            # Ensure we don't exceed max_frames
            if len(timestamps) > max_frames:
                # Sample evenly
                step = len(timestamps) / max_frames
                timestamps = [timestamps[int(i * step)] for i in range(max_frames)]

            # Extract frames and deduplicate by perceptual hash
            seen_hashes = set()
            frame_idx = 0

            for ts in sorted(set(timestamps)):
                frame_path = output_dir / f"frame_{frame_idx:04d}.jpg"
                try:
                    proc = subprocess.run(
                        ['ffmpeg', '-y', '-v', 'error', '-ss', str(ts),
                         '-i', str(video_path), '-vframes', '1',
                         '-q:v', '2', str(frame_path)],
                        capture_output=True, timeout=10, check=False
                    )
                    if proc.returncode == 0 and frame_path.exists():
                        # Compute perceptual hash
                        img = Image.open(frame_path)
                        phash = imagehash.phash(img)

                        # Skip if similar to existing frame
                        if any(abs(phash - h) < 10 for h in seen_hashes):
                            frame_path.unlink()
                            continue

                        seen_hashes.add(phash)
                        frames.append((frame_path, ts))
                        frame_idx += 1

                except Exception:
                    pass

        except Exception:
            return self._extract_evenly(video_path, output_dir, max_frames)

        return frames

    def _extract_evenly(
        self,
        video_path: Path,
        output_dir: Path,
        num_frames: int
    ) -> List[Tuple[Path, float]]:
        """Fallback: Extract frames evenly across video"""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get duration first
        try:
            proc = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_format', '-print_format', 'json',
                 str(video_path)],
                capture_output=True, text=True, timeout=30, check=False
            )
            duration = 60.0  # default
            if proc.returncode == 0:
                data = json.loads(proc.stdout)
                dur = data.get('format', {}).get('duration')
                if dur:
                    duration = float(dur)
        except Exception:
            duration = 60.0

        frames = []
        interval = duration / (num_frames + 1)

        for i in range(num_frames):
            ts = interval * (i + 1)
            frame_path = output_dir / f"frame_{i:04d}.jpg"
            try:
                proc = subprocess.run(
                    ['ffmpeg', '-y', '-v', 'error', '-ss', str(ts),
                     '-i', str(video_path), '-vframes', '1',
                     '-q:v', '2', str(frame_path)],
                    capture_output=True, timeout=10, check=False
                )
                if proc.returncode == 0 and frame_path.exists():
                    frames.append((frame_path, ts))
            except Exception:
                pass

        return frames


class FrameOCR:
    """Phase 2c: OCR keyframes for on-screen text"""

    def __init__(self):
        self._ocr = None

    def _get_ocr(self):
        if self._ocr is None:
            RapidOCR = _get_rapidocr()
            if RapidOCR is None:
                raise ImportError("rapidocr-onnxruntime not installed")
            self._ocr = RapidOCR()
        return self._ocr

    def ocr_frames(
        self,
        frames: List[Tuple[Path, float]],
        min_text_length: int = 3
    ) -> List[TranscriptSegment]:
        """Run OCR on extracted frames"""
        segments = []

        try:
            ocr = self._get_ocr()

            for frame_path, timestamp in frames:
                try:
                    result, elapse = ocr(str(frame_path))
                    if result:
                        frame_texts = []
                        for item in result:
                            if item and len(item) > 1:
                                text = str(item[1]).strip()
                                if text and len(text) >= min_text_length:
                                    frame_texts.append(text)

                        if frame_texts:
                            # Combine all text from this frame
                            combined = ' '.join(frame_texts)
                            segments.append(TranscriptSegment(
                                start_time=timestamp,
                                end_time=timestamp + 1,  # Approximate
                                text=combined,
                                source="ocr",
                                confidence=0.9
                            ))
                except Exception:
                    pass

        except Exception:
            pass

        return segments


class ContentFusion:
    """Phase 3: Merge and deduplicate content from multiple sources"""

    def __init__(self, similarity_threshold: float = 0.8):
        self.similarity_threshold = similarity_threshold

    def _similar(self, text1: str, text2: str) -> bool:
        """Check if two texts are similar using sequence matching"""
        if not text1 or not text2:
            return False
        from difflib import SequenceMatcher
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio() > self.similarity_threshold

    def fuse(
        self,
        audio_segments: List[TranscriptSegment],
        subtitle_segments: List[TranscriptSegment],
        ocr_segments: List[TranscriptSegment]
    ) -> List[TranscriptSegment]:
        """Merge segments from different sources, deduplicating by time and content"""

        # Priority: subtitle > audio > ocr for overlapping content
        all_segments = []

        # Add subtitle segments (highest priority)
        for seg in subtitle_segments:
            all_segments.append(seg)

        # Add audio segments, checking for overlap with subtitles
        for seg in audio_segments:
            is_dup = False
            for sub_seg in subtitle_segments:
                if self._time_overlaps(seg, sub_seg) and self._similar(seg.text, sub_seg.text):
                    is_dup = True
                    break
            if not is_dup:
                all_segments.append(seg)

        # Add OCR segments, checking for overlap
        for seg in ocr_segments:
            is_dup = False
            for existing in all_segments:
                if self._time_overlaps(seg, existing) and self._similar(seg.text, existing.text):
                    is_dup = True
                    break
            if not is_dup:
                all_segments.append(seg)

        # Sort by time
        all_segments.sort(key=lambda s: s.start_time)

        return all_segments

    def _time_overlaps(self, seg1: TranscriptSegment, seg2: TranscriptSegment, tolerance: float = 2.0) -> bool:
        """Check if two segments overlap in time"""
        return abs(seg1.start_time - seg2.start_time) < tolerance


class VideoRouter:
    """Main entry point: Intelligent video content extraction"""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.probe = VideoProbe()
        self.transcriber = AudioTranscriber()
        self.frame_extractor = FrameExtractor()
        self.frame_ocr = FrameOCR()
        self.fusion = ContentFusion()

    def _print(self, msg: str):
        if self.verbose:
            print(msg)

    def decide_strategy(self, probe_result: VideoProbeResult) -> ExtractionStrategy:
        """Decide extraction strategy based on probe results"""
        # Priority: embedded/subtitle > hybrid > audio > visual > full

        if probe_result.has_embedded_subtitle and not probe_result.has_visual_text:
            return ExtractionStrategy.EMBEDDED_SUBTITLE

        if probe_result.has_sidecar_subtitle and not probe_result.has_visual_text:
            return ExtractionStrategy.SIDECAR_SUBTITLE

        if probe_result.has_audio and probe_result.has_visual_text:
            return ExtractionStrategy.HYBRID

        if probe_result.has_audio and not probe_result.has_visual_text:
            return ExtractionStrategy.AUDIO_TRANSCRIBE

        if probe_result.has_visual_text and not probe_result.has_audio:
            return ExtractionStrategy.VISUAL_OCR

        # Default: run full pipeline
        return ExtractionStrategy.FULL_PIPELINE

    def extract(
        self,
        video_path: Path,
        output_dir: Optional[Path] = None,
        strategy: Optional[ExtractionStrategy] = None,
        language: str = None
    ) -> VideoExtractionResult:
        """Extract content from video using intelligent routing"""

        video_path = Path(video_path)
        if output_dir is None:
            output_dir = video_path.parent

        # Phase 1: Probe
        self._print(f"[VideoRouter] Probing {video_path.name}...")
        probe_result = self.probe.probe(video_path)

        self._print(f"  - Duration: {probe_result.duration_seconds:.1f}s")
        self._print(f"  - Audio: {probe_result.has_audio}")
        self._print(f"  - Embedded subtitles: {probe_result.has_embedded_subtitle}")
        self._print(f"  - Visual text: {probe_result.has_visual_text}")

        # Phase 2: Decide strategy
        if strategy is None:
            strategy = self.decide_strategy(probe_result)
        self._print(f"[VideoRouter] Strategy: {strategy.value}")

        result = VideoExtractionResult(strategy_used=strategy)

        # Create temp directory for frames
        temp_frames_dir = Path(tempfile.mkdtemp(prefix='video_frames_'))

        try:
            audio_segments = []
            subtitle_segments = []
            ocr_segments = []

            # Phase 3: Extract based on strategy
            if strategy in [ExtractionStrategy.EMBEDDED_SUBTITLE, ExtractionStrategy.HYBRID, ExtractionStrategy.FULL_PIPELINE]:
                subtitle_segments = self._extract_subtitles(video_path)
                result.subtitles_extracted = len(subtitle_segments) > 0

            if strategy in [ExtractionStrategy.AUDIO_TRANSCRIBE, ExtractionStrategy.HYBRID, ExtractionStrategy.FULL_PIPELINE]:
                if probe_result.has_audio:
                    self._print("[VideoRouter] Transcribing audio...")
                    audio_segments = self.transcriber.transcribe(video_path, language)
                    result.audio_transcribed = len(audio_segments) > 0
                    self._print(f"  - Got {len(audio_segments)} audio segments")

            if strategy in [ExtractionStrategy.VISUAL_OCR, ExtractionStrategy.HYBRID, ExtractionStrategy.FULL_PIPELINE]:
                self._print("[VideoRouter] Extracting keyframes...")
                frames = self.frame_extractor.extract_keyframes(video_path, temp_frames_dir)
                result.frames_extracted = len(frames)
                self._print(f"  - Extracted {len(frames)} keyframes")

                if frames:
                    self._print("[VideoRouter] Running OCR on frames...")
                    ocr_segments = self.frame_ocr.ocr_frames(frames)
                    result.frames_with_text = len(ocr_segments)
                    self._print(f"  - {len(ocr_segments)} frames with text")

            # Phase 4: Fuse content
            self._print("[VideoRouter] Fusing content...")
            result.transcript_segments = self.fusion.fuse(audio_segments, subtitle_segments, ocr_segments)

            # Generate markdown
            result.markdown = self._generate_markdown(video_path, result, probe_result)

            # Copy frames to output if requested
            if result.frames_with_text > 0 and output_dir:
                images_dir = output_dir / f"{video_path.stem}_frames"
                if temp_frames_dir.exists():
                    shutil.copytree(temp_frames_dir, images_dir, dirs_exist_ok=True)
                    result.images_dir = images_dir

        except Exception as e:
            result.error = str(e)

        finally:
            shutil.rmtree(temp_frames_dir, ignore_errors=True)

        return result

    def _extract_subtitles(self, video_path: Path) -> List[TranscriptSegment]:
        """Extract subtitles from video file"""
        segments = []

        # Check for sidecar files first
        sidecar_exts = ['.srt', '.vtt']
        for ext in sidecar_exts:
            sidecar = video_path.with_suffix(ext)
            if sidecar.exists():
                segments.extend(self._parse_subtitle_file(sidecar))
                return segments

        # Extract embedded subtitles
        try:
            # Get subtitle streams
            proc = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_streams', '-print_format', 'json',
                 str(video_path)],
                capture_output=True, text=True, timeout=30, check=False
            )
            if proc.returncode != 0:
                return []

            data = json.loads(proc.stdout)
            sub_streams = [s for s in data.get('streams', []) if s.get('codec_type') == 'subtitle']

            if sub_streams:
                # Extract first subtitle stream
                stream_idx = sub_streams[0].get('index', 0)
                temp_srt = Path(tempfile.mktemp(suffix='.srt'))

                try:
                    proc = subprocess.run(
                        ['ffmpeg', '-y', '-v', 'error', '-i', str(video_path),
                         '-map', f'0:{stream_idx}', '-f', 'srt', str(temp_srt)],
                        capture_output=True, timeout=60, check=False
                    )
                    if proc.returncode == 0 and temp_srt.exists():
                        segments.extend(self._parse_subtitle_file(temp_srt))
                finally:
                    if temp_srt.exists():
                        temp_srt.unlink()

        except Exception:
            pass

        return segments

    def _parse_subtitle_file(self, srt_path: Path) -> List[TranscriptSegment]:
        """Parse SRT/VTT subtitle file into segments"""
        segments = []

        try:
            content = srt_path.read_text(encoding='utf-8', errors='replace')
            content = content.replace('\r\n', '\n').replace('\r', '\n').strip()

            for block in content.split('\n\n'):
                lines = [l.strip() for l in block.split('\n') if l.strip()]
                if not lines:
                    continue

                # Find timestamp line
                time_idx = -1
                for i, line in enumerate(lines):
                    if '-->' in line:
                        time_idx = i
                        break

                if time_idx < 0:
                    continue

                # Parse timestamp
                time_parts = lines[time_idx].split('-->')
                if len(time_parts) != 2:
                    continue

                start = self._parse_timestamp(time_parts[0].strip())
                end = self._parse_timestamp(time_parts[1].strip())
                text = ' '.join(lines[time_idx + 1:]).strip()

                if text:
                    segments.append(TranscriptSegment(
                        start_time=start,
                        end_time=end,
                        text=text,
                        source="subtitle"
                    ))

        except Exception:
            pass

        return segments

    def _parse_timestamp(self, ts: str) -> float:
        """Parse SRT timestamp to seconds"""
        # Format: 00:00:00,000 or 00:00:00.000
        ts = ts.replace(',', '.')
        parts = ts.split(':')
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        return 0.0

    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds to HH:MM:SS"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _generate_markdown(
        self,
        video_path: Path,
        result: VideoExtractionResult,
        probe_result: VideoProbeResult
    ) -> str:
        """Generate markdown output from extraction result"""
        lines = [
            f"# Video Transcript: {video_path.stem}",
            "",
            "## Metadata",
            "",
            f"- **Source**: `{video_path.name}`",
            f"- **Duration**: {self._format_timestamp(probe_result.duration_seconds)}",
            f"- **Strategy**: {result.strategy_used.value}",
            f"- **Audio transcribed**: {result.audio_transcribed}",
            f"- **Subtitles extracted**: {result.subtitles_extracted}",
            f"- **Frames analyzed**: {result.frames_extracted}",
            f"- **Frames with text**: {result.frames_with_text}",
            "",
        ]

        if result.transcript_segments:
            lines.append("## Transcript")
            lines.append("")

            current_source = None
            for seg in result.transcript_segments:
                # Add source section header if changed
                if seg.source != current_source:
                    current_source = seg.source
                    source_name = {
                        "subtitle": "Subtitles",
                        "audio": "Audio Transcription",
                        "ocr": "On-Screen Text (OCR)"
                    }.get(current_source, current_source.title())
                    lines.append(f"### {source_name}")
                    lines.append("")

                ts = self._format_timestamp(seg.start_time)
                lines.append(f"- [{ts}] {seg.text}")

            lines.append("")

        if result.images_dir:
            lines.append("## Extracted Frames")
            lines.append("")
            lines.append(f"Frames saved to: `{result.images_dir.name}/`")
            lines.append("")

        return '\n'.join(lines)


# Convenience function
def extract_video_content(
    video_path: Path,
    output_dir: Optional[Path] = None,
    verbose: bool = True
) -> Tuple[str, VideoExtractionResult]:
    """Extract content from video and return markdown + result"""
    router = VideoRouter(verbose=verbose)
    result = router.extract(video_path, output_dir)
    return result.markdown, result
