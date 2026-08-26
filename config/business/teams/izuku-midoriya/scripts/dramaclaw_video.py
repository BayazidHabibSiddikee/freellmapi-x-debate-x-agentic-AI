"""
DramaClaw Video Assembly — standalone wrapper.
Uses DramaClaw's Ken Burns effects + scene composition via ffmpeg.
No Docker or DC key required — just ffmpeg.
"""

import asyncio
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

# Add DramaClaw to path
sys.path.insert(0, "/home/sword/Documents/dramaclaw/src")

# ── Ken Burns Effects (from DramaClaw) ────────────────────────────────────────

class KenBurnsEffect:
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    PAN_LEFT = "pan_left"
    PAN_RIGHT = "pan_right"

    @staticmethod
    def get_ffmpeg_filter(effect: str, duration: float, width: int, height: int) -> str:
        fps = 24
        frames = int(duration * fps)

        if effect == KenBurnsEffect.ZOOM_IN:
            return (
                f"zoompan=z='min(zoom+0.002,1.15)':d={frames}:x='iw/2-(iw/zoom/2)':"
                f"y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps}"
            )
        elif effect == KenBurnsEffect.ZOOM_OUT:
            return (
                f"zoompan=z='if(lte(zoom,1.0),1.15,max(1.001,zoom-0.002))':d={frames}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps}"
            )
        elif effect == KenBurnsEffect.PAN_LEFT:
            return (
                f"zoompan=z=1.08:d={frames}:x='iw/2-(iw/zoom/2)+{duration}*5':"
                f"y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps}"
            )
        elif effect == KenBurnsEffect.PAN_RIGHT:
            return (
                f"zoompan=z=1.08:d={frames}:x='iw/2-(iw/zoom/2)-{duration}*5':"
                f"y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps}"
            )
        else:
            return f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"


def normalize_video_title(title: str) -> str:
    normalized = re.sub(r"\s+", " ", str(title or "")).strip()
    return normalized or "untitled"


def _drawtext_fontfile_arg() -> str:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/PingFang.ttc",
    ):
        if os.path.exists(path):
            return f":fontfile={path}"
    return ""


# ── Scene Video ───────────────────────────────────────────────────────────────

def create_scene_video(
    image_path: str,
    audio_path: str,
    output_path: str,
    effect: Optional[str] = None,
    width: int = 1080,
    height: int = 1920,
    duration: float = 10.0,
) -> bool:
    """Create a single scene video from image + audio with Ken Burns effect."""
    if effect:
        video_filter = KenBurnsEffect.get_ffmpeg_filter(effect, duration, width, height)
    else:
        video_filter = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
        )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", image_path,
        "-i", audio_path,
        "-vf", video_filter,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return result.returncode == 0


# ── Title Card ────────────────────────────────────────────────────────────────

def create_title_card(title: str, output_path: str, duration: float = 3.0, width: int = 1080, height: int = 1920) -> bool:
    """Create a title card video with text overlay."""
    fontfile = _drawtext_fontfile_arg()
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:d={duration}:r=30",
        "-vf",
        f"drawtext=text='{title}'{fontfile}:fontsize=64:fontcolor=white:"
        f"x=(w-text_w)/2:y=(h-text_h)/2",
        "-c:v", "libx264", "-preset", "fast",
        "-pix_fmt", "yuv420p",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return result.returncode == 0


# ── End Card ──────────────────────────────────────────────────────────────────

def create_end_card(output_path: str, duration: float = 2.0, width: int = 1080, height: int = 1920) -> bool:
    """Create a simple end card."""
    fontfile = _drawtext_fontfile_arg()
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:d={duration}:r=30",
        "-vf",
        f"drawtext=text='To be continued...'{fontfile}:fontsize=48:fontcolor=white:"
        f"x=(w-text_w)/2:y=(h-text_h)/2",
        "-c:v", "libx264", "-preset", "fast",
        "-pix_fmt", "yuv420p",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return result.returncode == 0


# ── Concatenation ─────────────────────────────────────────────────────────────

def concat_videos(video_paths: list[str], output_path: str) -> bool:
    """Merge multiple videos into one."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for path in video_paths:
            f.write(f"file '{path}'\n")
        list_file = f.name

    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", list_file,
            "-c", "copy",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.returncode == 0
    finally:
        os.unlink(list_file)


# ── Subtitles ─────────────────────────────────────────────────────────────────

def add_subtitles(video_path: str, subtitle_path: str, output_path: str) -> bool:
    """Burn subtitles into video."""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"subtitles={subtitle_path}:force_style='FontSize=24,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2'",
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "copy",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return result.returncode == 0


# ── Full Assembly ─────────────────────────────────────────────────────────────

def assemble_episode(
    scenes: list[dict],
    output_path: str,
    title: str = "",
    add_title_card: bool = True,
    add_end_card: bool = True,
    width: int = 1080,
    height: int = 1920,
) -> bool:
    """
    Assemble a full episode from scene assets.

    scenes: list of dicts with keys:
        - image_path: str (path to scene image)
        - audio_path: str (path to scene audio)
        - duration_seconds: float
        - narration_text: str (optional)
    """
    effects = [
        KenBurnsEffect.ZOOM_IN,
        KenBurnsEffect.ZOOM_OUT,
        KenBurnsEffect.PAN_LEFT,
        KenBurnsEffect.PAN_RIGHT,
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        scene_videos = []

        for i, scene in enumerate(scenes):
            scene_video = os.path.join(temp_dir, f"scene_{i:03d}.mp4")
            effect = effects[i % len(effects)]

            success = create_scene_video(
                image_path=scene["image_path"],
                audio_path=scene["audio_path"],
                output_path=scene_video,
                effect=effect,
                width=width,
                height=height,
                duration=scene.get("duration_seconds", 10.0),
            )

            if success and os.path.isfile(scene_video):
                scene_videos.append(scene_video)

        # Title card
        if add_title_card and title:
            title_video = os.path.join(temp_dir, "title.mp4")
            if create_title_card(normalize_video_title(title), title_video, width=width, height=height):
                scene_videos.insert(0, title_video)

        # End card
        if add_end_card:
            end_video = os.path.join(temp_dir, "end.mp4")
            if create_end_card(end_video, width=width, height=height):
                scene_videos.append(end_video)

        if not scene_videos:
            return False

        return concat_videos(scene_videos, output_path)
