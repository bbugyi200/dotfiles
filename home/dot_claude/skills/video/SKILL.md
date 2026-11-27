---
name: video
description:
  Inspect, transcribe, OCR, and edit video or audio files through ffprobe, contact
  sheets, Whisper, and ffmpeg. Use whenever a task involves a video or audio file.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skill use video --reason "<one-line reason for using this skill>"
```

Work from a scratch dir and never overwrite inputs. All commands below run on athena or
apollo; both have the same `whisper_run`, `yt-dlp`, `ffmpeg`, `tesseract`, `mediainfo`,
`exiftool`, `mkvtoolnix`, `scenedetect`, and `auto-editor`.

## 1. Probe

```bash
ffprobe -v error -show_format -show_streams -of json in.mp4
mediainfo in.mp4
exiftool -G -a in.mp4
```

`ffprobe` gives length and codecs; `mediainfo` and `exiftool` add rotation, capture
date, GPS, and HDR flags.

## 2. Look

Make a timestamped contact sheet and read it as images:

```bash
ffmpeg -i in.mp4 -vf "fps=1/3,scale=384:-1,drawtext=text='%{pts\:hms}':x=8:y=h-th-8:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.65,tile=5x2" -frames:v 1 sheet.jpg
```

For one frame per shot, prefer `scenedetect`:

```bash
scenedetect -i in.mp4 -o . detect-content list-scenes save-images
```

Without it, fall back to `ffmpeg select='gt(scene,0.3)'`.

## 3. OCR

```bash
tesseract <frame> -
```

Use it for on-screen text in a sheet frame or a single export.

## 4. Listen

```bash
whisper_run in.mp4 --output_format srt --output_dir <scratch>
```

Add `--language en` to skip language detection. `json` and `vtt` outputs work too. The
default model is `large-v3-turbo` on every host; override with `WHISPER_MODEL` or a
trailing `--model`, and force CPU or GPU with `WHISPER_DEVICE=cpu|cuda|auto`. stderr
always logs `device=<d> compute=<c> model=<m>`.

## 5. Edit

Lossless trim (keyframe cuts only):

```bash
ffmpeg -ss 00:01:00 -to 00:02:00 -i in.mp4 -c copy out.mp4
```

Re-encoded trim, concat, burn-in, text, loudness, transition, and GIF:

```bash
ffmpeg -ss 00:01:00 -to 00:02:00 -i in.mp4 -c:v libx264 -c:a aac out.mp4
ffmpeg -f concat -safe 0 -i list.txt -c copy out.mp4
ffmpeg -i in.mp4 -vf subtitles=clip.srt out.mp4
ffmpeg -i in.mp4 -vf "drawtext=text='Title':x=8:y=8:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.65" out.mp4
ffmpeg -i in.mp4 -af loudnorm out.mp4
ffmpeg -i a.mp4 -i b.mp4 -filter_complex xfade=transition=fade:duration=1:offset=4 out.mp4
ffmpeg -i in.mp4 -vf "fps=15,scale=480:-1:flags=lanczos,palettegen" palette.png
ffmpeg -i in.mp4 -i palette.png -lavfi "fps=15,scale=480:-1:flags=lanczos [x]; [x][1:v] paletteuse" out.gif
```

On athena, use GPU encodes with `h264_nvenc` or `hevc_nvenc` (`av1_nvenc` is
unsupported, so use `libsvtav1` for AV1).

MKV tracks, chapters, and subtitles go through mkvtoolnix (`mkvmerge`, `mkvpropedit`,
`mkvextract`). Use `auto-editor` to cut silence automatically (check `--help` first;
apollo's apt build is older).

## 6. Re-check

Build a new contact sheet and confirm duration for every output:

```bash
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 in.mp4
```

## Mac screen recordings

Mac screen recordings land in `~/tmp/screencasts` as `YYYYMMDD_HHMMSS.mp4`. Fetch the
nth newest with `svid_fetch N --sheet` (or `#svid --sheet` in an agent prompt) for a
cached timestamped contact sheet plus a one-line summary. That output also prints a
`Keystrokes:` WebVTT file of the exact keys shown on screen, or `none`. Clips are silent
unless the mic was on for that clip. Read the Keystrokes subtitle stream before OCR.
Recorder clips carry exactly one subtitle stream:

```bash
ffmpeg -v error -i CLIP -map 0:s:0 -f webvtt -
```

The `title:Keystrokes` stream map (`-map 0:s:m:title:Keystrokes`) matched nothing on
ffmpeg 6.1.1 and 9.0.2.

## Host notes

- athena is the GPU box; send heavy jobs there.
- apollo is a CPU-only shared server: keep jobs short and prefer `ssh athena` for long
  ones.
- On the Mac, Homebrew ffmpeg lacks drawtext and libass and there is no Whisper, so run
  video jobs with `ssh athena`.

## Rules

- Never overwrite inputs; work in a scratch dir.
- Run `yt-dlp` only on URLs the user supplied.
- Gemini CLI on athena can watch short clips, but it uploads them to Google, so use it
  only with the user's explicit OK.
- Never install Python video libraries globally. Use `uv run --with moviepy` for the one
  task instead.
