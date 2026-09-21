#!/usr/bin/env python3
"""Build a local, non-impersonating documentary-style narration preview."""

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "video"
ASSETS = VIDEO_DIR / "assets"
WORK = VIDEO_DIR / "voice_preview_work"
LINES = (VIDEO_DIR / "旁白样轨文案.txt").read_text(encoding="utf-8").splitlines()
VOICE = "Reed (中文（中国大陆）)"


def run(*args):
    subprocess.run(args, check=True)


def duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        check=True,
        stdout=subprocess.PIPE,
        universal_newlines=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def main():
    if len(LINES) != 8:
        raise SystemExit("旁白样轨必须正好包含 8 行，与 8 张视觉卡对应。")
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)

    audio_segments = []
    segment_durations = []
    for index, line in enumerate(LINES):
        raw = WORK / f"{index:02d}_raw.aiff"
        processed = WORK / f"{index:02d}_voice.m4a"
        run("say", "-v", VOICE, "-r", "185", "-o", str(raw), line)
        run(
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw),
            "-af", "asetrate=22050*0.94,aresample=22050,atempo=1.06383,equalizer=f=140:t=q:w=1:g=3,loudnorm=I=-16:TP=-2:LRA=7,apad=pad_dur=0.45",
            "-c:a", "aac", "-b:a", "192k", str(processed),
        )
        audio_segments.append(processed)
        segment_durations.append(duration(processed))

    audio_list = WORK / "audio_concat.txt"
    audio_list.write_text("".join(f"file '{path.name}'\n" for path in audio_segments), encoding="utf-8")
    narration = VIDEO_DIR / "原创竞技纪录片声线_旁白样轨.m4a"
    run(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
        "-i", str(audio_list), "-c", "copy", str(narration),
    )

    visual_list = WORK / "visual_concat.txt"
    cards = sorted(ASSETS.glob("*.png"))
    lines = []
    for card, seconds in zip(cards, segment_durations):
        lines.extend([f"file '{card.resolve()}'", f"duration {seconds:.3f}"])
    lines.append(f"file '{cards[-1].resolve()}'")
    visual_list.write_text("\n".join(lines) + "\n", encoding="utf-8")
    silent_video = WORK / "visual.mp4"
    run(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
        "-i", str(visual_list), "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-movflags", "+faststart", str(silent_video),
    )
    preview = VIDEO_DIR / "亚运会男篮数据分析_AI旁白预览.mp4"
    run(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(silent_video), "-i", str(narration),
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(preview),
    )
    print(json.dumps({"voice": VOICE, "duration": round(duration(preview), 2), "preview": str(preview)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
