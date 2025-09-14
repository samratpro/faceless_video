import re
import math
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Media processing
from moviepy import (
    AudioFileClip,
    ImageClip,
    CompositeVideoClip,
    concatenate_videoclips,
    ImageSequenceClip,
    VideoFileClip,
)

# Text rendering without ImageMagick
from PIL import Image, ImageDraw, ImageFont
import numpy as np


# -----------------------------
# Configuration
# -----------------------------
VIDEO_SIZE = (1280, 720)  # (width, height)
FPS = 30
BG_COLOR = (0, 0, 0)
TEXT_COLOR = (255, 255, 255)
TEXT_STROKE_COLOR = (0, 0, 0)
TEXT_STROKE_WIDTH = 2
TEXT_BOX_BG = (0, 0, 0, 170)  # semi-transparent black
MARGIN = 36  # px from bottom
WORDS_PER_SLIDE = 5  # show 4-5 words per caption slide
FADE_TIME = 0.25  # seconds for fade in/out of text
IMAGE_KEN_BURNS_ZOOM = (1.05, 1.15)  # (start_scale, end_scale)
CROSSFADE_BETWEEN_SEGMENTS = 0.0  # seconds, keep 0 for simplicity/robustness
SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
SUPPORTED_AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}


def read_text_fallback(path: Path) -> str:
    encodings = [
        "utf-8",
        "utf-8-sig",
        "utf-16",
        "utf-16-le",
        "utf-16-be",
        "cp1252",
    ]
    for enc in encodings:
        try:
            return path.read_text(encoding=enc)
        except Exception:
            continue
    # Last resort: binary read with ignore
    try:
        return path.read_bytes().decode("utf-8", errors="ignore")
    except Exception:
        return ""


# -----------------------------
# Utilities
# -----------------------------

def find_font() -> Optional[str]:
    """Try to find a usable TTF font path on this system."""
    candidates = [
        # Windows
        r"C:\\Windows\\Fonts\\arial.ttf",
        r"C:\\Windows\\Fonts\\ARIAL.TTF",
        r"C:\\Windows\\Fonts\\segoeui.ttf",
        # Common fallbacks
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return p
    return None


def chunk_words(text: str, words_per_slide: int) -> List[str]:
    words = [w for w in re.split(r"\s+", text.strip()) if w]
    if not words:
        return []
    chunks = []
    for i in range(0, len(words), words_per_slide):
        chunk = words[i : i + words_per_slide]
        chunks.append(" ".join(chunk))
    return chunks


def draw_text_image(
    text: str,
    video_size: Tuple[int, int],
    font_path: Optional[str],
    font_size: int = 42,
    max_width_ratio: float = 0.9,
    line_spacing: float = 1.1,
) -> Image.Image:
    """Render text onto a transparent image with a rounded rectangular background box.

    - Wrap lines to fit within max_width_ratio of video width.
    - Returns PIL Image with alpha channel.
    """
    vw, vh = video_size
    max_text_width = int(vw * max_width_ratio)

    # Load font
    try:
        if font_path and Path(font_path).exists():
            font = ImageFont.truetype(font_path, font_size)
        else:
            font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    # Basic word wrapping
    words = text.split()
    lines: List[str] = []
    current = []
    dummy_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    dummy_draw = ImageDraw.Draw(dummy_img)

    for w in words:
        tmp = " ".join(current + [w]) if current else w
        bbox = dummy_draw.textbbox((0, 0), tmp, font=font, stroke_width=TEXT_STROKE_WIDTH)
        width = bbox[2] - bbox[0]
        if width <= max_text_width:
            current.append(w)
        else:
            if current:
                lines.append(" ".join(current))
            current = [w]
    if current:
        lines.append(" ".join(current))

    # Compute text block size
    line_heights = []
    line_widths = []
    for line in lines:
        bbox = dummy_draw.textbbox((0, 0), line, font=font, stroke_width=TEXT_STROKE_WIDTH)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])

    if not line_heights:
        line_heights = [font_size]
        line_widths = [0]
        lines = [""]

    max_line_width = max(line_widths) if line_widths else 0
    line_height = max(line_heights)
    total_text_height = int(sum(line_heights[i] if i == 0 else line_height for i in range(len(lines))) + (len(lines) - 1) * int(line_height * (line_spacing - 1)))

    pad_x, pad_y = 24, 12
    box_w = max_line_width + pad_x * 2
    box_h = total_text_height + pad_y * 2

    # Create transparent image
    img = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw rounded rectangle background
    radius = 12
    draw.rounded_rectangle([0, 0, box_w, box_h], radius=radius, fill=TEXT_BOX_BG)

    # Draw text lines centered
    y = pad_y
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=TEXT_STROKE_WIDTH)
        lw = bbox[2] - bbox[0]
        lh = bbox[3] - bbox[1]
        x = (box_w - lw) // 2
        draw.text(
            (x, y),
            line,
            font=font,
            fill=TEXT_COLOR,
            stroke_width=TEXT_STROKE_WIDTH,
            stroke_fill=TEXT_STROKE_COLOR,
        )
        y += int(lh * line_spacing)

    return img


def prepare_image_frame(image_path: Path, target_size: Tuple[int, int]) -> np.ndarray:
    tw, th = target_size
    with Image.open(image_path) as im:
        im = im.convert("RGB")
        iw, ih = im.size
        if iw == 0 or ih == 0:
            return np.array(im.resize((tw, th), Image.LANCZOS))
        scale = max(tw / iw, th / ih)
        new_w, new_h = int(iw * scale), int(ih * scale)
        im = im.resize((new_w, new_h), Image.LANCZOS)
        # center crop
        left = (new_w - tw) // 2
        top = (new_h - th) // 2
        im = im.crop((left, top, left + tw, top + th))
        return np.array(im)


def prepare_base_image_pil(image_path: Path, target_size: Tuple[int, int]) -> Image.Image:
    tw, th = target_size
    with Image.open(image_path) as im:
        im = im.convert("RGB")
        iw, ih = im.size
        if iw == 0 or ih == 0:
            return im.resize((tw, th), Image.LANCZOS)
        scale = max(tw / iw, th / ih)
        new_w, new_h = int(iw * scale), int(ih * scale)
        im = im.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - tw) // 2
        top = (new_h - th) // 2
        im = im.crop((left, top, left + tw, top + th))
        return im


def make_segment_clip(
    base_img_pil: Image.Image,
    caption_imgs: List[Image.Image],
    total_frames: int,
    zoom_start: float = 1.02,
    zoom_end: float = 1.12,
) -> ImageSequenceClip:
    W, H = base_img_pil.size
    n = max(1, len(caption_imgs))

    # Precompute caption positions for each caption
    caps_info = []
    for cap in caption_imgs:
        cap_w, cap_h = cap.size
        cap_x = (W - cap_w) // 2
        cap_y = H - cap_h - MARGIN
        caps_info.append((cap, cap_x, cap_y))

    total_frames = max(1, int(total_frames))

    frames = []
    for i in range(total_frames):
        # Cosine easing for smoother zoom
        if total_frames <= 1:
            prog = 1.0
        else:
            prog = i / (total_frames - 1)
        ease = 0.5 - 0.5 * math.cos(math.pi * prog)
        szoom = zoom_start + (zoom_end - zoom_start) * ease

        crop_w = max(1, int(W / szoom))
        crop_h = max(1, int(H / szoom))
        left = (W - crop_w) // 2
        top = (H - crop_h) // 2
        frame = base_img_pil.crop((left, top, left + crop_w, top + crop_h)).resize((W, H), Image.LANCZOS).convert("RGBA")
        out = Image.new("RGBA", (W, H))
        out.paste(frame, (0, 0))

        # Equal frame-based slide selection
        slide_idx = min(n - 1, (i * n) // total_frames)
        cap, cap_x, cap_y = caps_info[slide_idx]

        # paste caption with alpha
        if cap.mode == "RGBA":
            out.paste(cap, (cap_x, cap_y), mask=cap.split()[3])
        else:
            out.paste(cap, (cap_x, cap_y))
        rgb = out.convert("RGB")
        frames.append(np.array(rgb))

    return ImageSequenceClip(frames, fps=FPS)


def build_segment(
    image_path: Path,
    script_text: str,
    voice_path: Path,
    font_path: Optional[str],
) -> CompositeVideoClip:
    voice = AudioFileClip(str(voice_path))
    duration = voice.duration

    base_pil = prepare_base_image_pil(image_path, VIDEO_SIZE)

    slides = chunk_words(script_text, WORDS_PER_SLIDE)
    slides_list = slides if slides else [""]
    n = len(slides_list)

    total_frames = max(1, int(round(duration * FPS)))

    caption_imgs = [draw_text_image(txt, VIDEO_SIZE, font_path) for txt in slides_list]
    composed = make_segment_clip(base_pil, caption_imgs, total_frames)
    composed.audio = voice

    # Ensure resources will be cleaned when the final video is written
    return composed


def scan_serial_files(base: Path) -> Tuple[Dict[int, Path], Dict[int, Path], Dict[int, Path]]:
    images_dir = base / "images"
    scripts_dir = base / "scripts"
    voices_dir = base / "voices"

    if not images_dir.exists() or not scripts_dir.exists() or not voices_dir.exists():
        raise FileNotFoundError("Missing 'images', 'scripts', or 'voices' folder in: " + str(base))

    images: Dict[int, Path] = {}
    scripts: Dict[int, Path] = {}
    voices: Dict[int, Path] = {}

    # Images: img<number>.<ext>
    for p in images_dir.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in SUPPORTED_IMAGE_EXTS:
            continue
        m = re.match(r"^img(\d+)$", p.stem, flags=re.IGNORECASE)
        if m:
            idx = int(m.group(1))
            images[idx] = p

    # Scripts: script<number>.txt or scripts<number>.txt
    for p in scripts_dir.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() != ".txt":
            continue
        m = re.match(r"^script?(\d+)$", p.stem, flags=re.IGNORECASE)
        if m:
            idx = int(m.group(1))
            scripts[idx] = p

    # Voices: voice<number>.<audio ext>
    for p in voices_dir.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in SUPPORTED_AUDIO_EXTS:
            continue
        m = re.match(r"^voice(\d+)$", p.stem, flags=re.IGNORECASE)
        if m:
            idx = int(m.group(1))
            voices[idx] = p

    return images, scripts, voices


def build_video_for_keyword(keyword: str, project_root: Path) -> Path:
    base = project_root / "resource" / keyword
    if not base.exists():
        raise FileNotFoundError(f"Resource folder not found: {base}")

    images, scripts, voices = scan_serial_files(base)

    common_indices = sorted(set(images.keys()) & set(scripts.keys()) & set(voices.keys()))
    if not common_indices:
        raise RuntimeError("No matching imgN, scriptN, voiceN triplets found.")

    font_path = find_font()

    output_dir = project_root / "output" / keyword
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_keyword = re.sub(r"[^\w\-]+", "_", keyword.strip())
    segment_dir = output_dir / "segments"
    segment_dir.mkdir(parents=True, exist_ok=True)

    segment_files: List[Path] = []
    skipped: List[int] = []
    for idx in common_indices:
        try:
            raw = read_text_fallback(scripts[idx])
            script_text = raw.replace("\r\n", " ").replace("\n", " ").strip()
            print(f"[INFO] Building segment {idx}: script length={len(script_text)}")
            if not script_text:
                script_text = ""
            seg = build_segment(images[idx], script_text, voices[idx], font_path)
            seg_out = segment_dir / f"{safe_keyword}_seg_{idx:04d}.mp4"
            temp_audio = output_dir / f"temp-audio-seg-{idx}.m4a"
            seg.write_videofile(
                str(seg_out),
                fps=FPS,
                codec="libx264",
                audio_codec="aac",
                preset="medium",
                threads=4,
                temp_audiofile=str(temp_audio),
                remove_temp=True,
            )
            try:
                seg.close()
            except Exception:
                pass
            segment_files.append(seg_out)
        except Exception as e:
            print(f"[WARN] Skipping index {idx} due to error: {e}")
            skipped.append(idx)

    if not segment_files:
        raise RuntimeError("All segments failed to build; nothing to render.")

    # Load the rendered segment files and concatenate
    vclips = []
    for p in segment_files:
        try:
            vclips.append(VideoFileClip(str(p)))
        except Exception as e:
            print(f"[WARN] Failed to load segment file {p}: {e}")

    if not vclips:
        raise RuntimeError("No segment files could be loaded; nothing to render.")

    final = concatenate_videoclips(vclips, method="compose")
    output_path = output_dir / f"{safe_keyword}_faceless_video.mp4"

    final.write_videofile(
        str(output_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
        temp_audiofile=str(output_dir / "temp-audio.m4a"),
        remove_temp=True,
    )

    try:
        final.close()
    except Exception:
        pass
    for vc in vclips:
        try:
            vc.close()
        except Exception:
            pass

    if skipped:
        print(f"Finished with {len(skipped)} skipped segments: {skipped}")

    return output_path


def main():
    project_root = Path(__file__).resolve().parent

    # Ignore any 'prompt' folder as requested; we operate under resource/<keyword>
    keyword = input("Enter keyword (resource folder name): ").strip()
    if not keyword:
        print("Keyword cannot be empty.")
        sys.exit(1)

    try:
        output = build_video_for_keyword(keyword, project_root)
        print(f"Video exported to: {output}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
