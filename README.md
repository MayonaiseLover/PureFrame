<div align="center">
  <img src="assets/logo.svg" alt="PureFrame" width="140" />
  <h1>PureFrame</h1>
  <p>Blur the explicit parts of a movie instead of cutting them out.</p>

  <a href="#install"><img src="https://img.shields.io/pypi/v/pureframe?color=%2334D058&label=PyPI" alt="PyPI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT" /></a>
  <a href="https://github.com/xenoaitham/PureFrame/actions"><img src="https://img.shields.io/github/actions/workflow/status/xenoaitham/PureFrame/ci.yml?label=CI" alt="CI" /></a>
  <img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue" alt="Python 3.11 | 3.12 | 3.13" />

  <br /><br />
  <img src="assets/banner.png" alt="The same frame before and after PureFrame: the figure is blurred, the window stays sharp" width="800" />
  <p><em>Actual output from the tool. The figure gets a Gaussian blur that follows it across the frame, and everything else is left alone. There's a <a href="https://xenoaitham.github.io/PureFrame/demo/">walkthrough</a> too, and more images in <a href="screenshots/">screenshots/</a>.</em></p>
</div>

PureFrame scans a video file for nudity, sexual activity and intense kissing, then blurs just those regions of the frame and tracks them as they move. Nothing gets cut. The audio and the timeline stay exactly as they were, so the movie plays through normally with the flagged parts blurred.

Most family-friendly tools skip the flagged scenes instead, and you lose dialog and plot along with them. VidAngel and ClearPlay also only cover a curated list of titles. PureFrame uses computer vision, so it works on any MP4, MKV, AVI or WebM you have, foreign films and old DVDs included. It runs on your own machine and it's free.

## Downloads

Prebuilt binaries are on the [releases page](https://github.com/xenoaitham/PureFrame/releases/latest).

The desktop app (Tauri):

- Windows: [PureFrame_x64-setup.exe](https://github.com/xenoaitham/PureFrame/releases/latest) or the `.msi`
- macOS, Apple Silicon: `PureFrame_aarch64.dmg`
- macOS, Intel: `PureFrame_x64.dmg`
- Linux: `.AppImage`, `.deb` or `.rpm`

A standalone command line build (PyInstaller, so no Python needed):

- Windows: [pureframe-windows-x86_64.zip](https://github.com/xenoaitham/PureFrame/releases/latest/download/pureframe-windows-x86_64.zip)
- macOS, Apple Silicon: [pureframe-macos-arm64.tar.gz](https://github.com/xenoaitham/PureFrame/releases/latest/download/pureframe-macos-arm64.tar.gz)
- Linux, x86_64: [pureframe-linux-x86_64.tar.gz](https://github.com/xenoaitham/PureFrame/releases/latest/download/pureframe-linux-x86_64.tar.gz)

Extract it anywhere and run `pureframe --help` (`pureframe.exe --help` on Windows). The Windows zip bundles `ffmpeg.exe` and `ffprobe.exe`, so there's nothing else to install. On macOS and Linux you need ffmpeg on your PATH (`brew install ffmpeg` or `apt install ffmpeg`).

There's no standalone build for Intel Macs. GitHub's `macos-13` runners are end-of-life, and the queue was always backed up anyway. Use `pip install pureframe` or the Intel `.dmg` instead.

### Code signing

The binaries aren't signed since I don't have paid Apple or Microsoft certificates yet, so expect a warning the first time you run one.

- Windows: SmartScreen says "Windows protected your PC". Click More info, then Run anyway.
- macOS: Gatekeeper blocks it as coming from an unidentified developer. Right-click the app or binary, choose Open and confirm. Or run `xattr -dr com.apple.quarantine /path/to/PureFrame.app`.
- Linux: nothing to do.

Each release has a `SHA256SUMS.txt` if you want to check your download:

```bash
# Linux / macOS
curl -LO https://github.com/xenoaitham/PureFrame/releases/latest/download/SHA256SUMS.txt
sha256sum -c --ignore-missing SHA256SUMS.txt

# Windows PowerShell
$expected = (Select-String -Path SHA256SUMS.txt -Pattern 'pureframe-windows-x86_64\.zip').Line.Split(' ')[0]
$actual   = (Get-FileHash pureframe-windows-x86_64.zip -Algorithm SHA256).Hash.ToLower()
if ($expected -eq $actual) { 'OK' } else { 'MISMATCH' }
```

## Install

```bash
# from PyPI
pip install pureframe

# from source
git clone https://github.com/xenoaitham/PureFrame.git
cd PureFrame
pip install -e ".[dev]"
```

You need Python 3.11 or newer and FFmpeg on your PATH. A GPU helps but you don't need one. The [installation guide](docs/installation.md) covers platform-specific setup, GPU setup and troubleshooting.

## Quick start

```bash
# detect and blur in one go
pureframe process movie.mp4 --output movie_clean.mp4

# or do it in steps so you can check the results first
pureframe plan movie.mp4                           # writes movie.censorplan.json
pureframe plan-edit movie.censorplan.json          # open it in your editor
pureframe plan-whitelist movie.censorplan.json 3   # whitelist #3, a false positive
pureframe apply movie.mp4 movie.censorplan.json    # render the final video

# HTML contact sheet of the flagged shots, so you don't have to watch the whole thing
pureframe preview movie.censorplan.json
```

The `.censorplan.json` file is plain JSON. It lists every flagged shot with its category, confidence, reasoning and bounding boxes. Go through it, whitelist whatever's wrong, and only then run `apply`. Nothing gets rendered before that.

## Content types

The defaults assume live-action movies and TV. For anything else, pick a profile:

```bash
pureframe process cartoon.mp4 --content-type animation
```

- `live-action`: movies and TV, the default
- `animation`: higher thresholds, so fewer false positives on cartoons
- `anime`: tuned for anime art styles
- `low-light`: dark scenes, more sensitive
- `art`: museums and galleries. It has the highest bar, so classical art stops getting flagged
- `medical`: clinical footage, so surgery and anatomy stop getting flagged

## Strictness

`--strictness` takes `low`, `medium` or `high`. Medium is the default, low censors the least and high is aggressive. You can also set the number yourself with `--threshold`:

```bash
pureframe process movie.mp4 --strictness high
pureframe process movie.mp4 --threshold 0.35
```

Start with medium. If swimwear and bare skin keep getting flagged, try low. If explicit scenes are slipping through, try high. The [calibration guide](docs/CALIBRATION.md) goes into more detail, and the [evaluation report](docs/evaluation.md) has accuracy numbers and threshold calibration.

## How it works

PySceneDetect splits the video into shots. NudeNet looks at sampled frames from each shot and returns nudity detections with bounding boxes, while CLIP classifies the scene as a whole to pick up sexual activity. When a shot is ambiguous, PANNs listens to the audio for context. That only runs on shots where the audio could actually change the result, so most shots never touch it, and that's a big part of why detection got about ten times faster.

The signals are combined using per-category thresholds and written to the `.censorplan.json` file. After you've reviewed it, the renderer applies the blurs frame by frame, following the bounding boxes, and re-encodes with FFmpeg. There's a diagram in [docs/architecture.md](docs/architecture.md).

## Performance

These are medians from `pureframe bench --duration 30 --reps 3` on my machine (i5-10400F, RTX 3060, Pop!_OS), after a round of speed work. The big changes were seeking straight to the frames it needs instead of decoding everything, keeping the ONNX models loaded, only running the audio classifier when it matters, overlapping decode with inference, int8 quantization on CPU (on by default, `--no-quant` turns it off), and encoder presets per profile.

| Profile | 30 s clip | Detections |
|---|---:|---:|
| CPU | 3.0 s | 0 |
| LOW | 15.1 s | 1 |
| MEDIUM | 16.2 s | 1 |
| HIGH | 23.7 s | 1 |

The goal is 10 to 20 minutes for a 90 minute movie on CPU-only hardware. Don't read too much into this table, though. It's a synthetic 30 second clip with one or two shots, and the CPU run found nothing to blur, so it says little about how a real film behaves. The per-step breakdowns and the numbers from before the changes are in [docs/performance.md](docs/performance.md) and [BENCHMARKS.md](BENCHMARKS.md).

To time your own machine:

```bash
pureframe bench --duration 30 --reps 3 -o bench-report.json
```

## Desktop app

There's an experimental desktop app built with [Tauri](https://tauri.app/). Drop videos into the queue, watch each job's progress live, and review the results shot by shot with thumbnails and a color-coded timeline. You can whitelist or blacklist a shot with one click, scrub through the timeline, compare before and after, and change the hardware profile or detection sensitivity in settings. It has a dark theme.

| Job queue | Editor |
|---|---|
| <img src="assets/gui_queue.png" alt="PureFrame desktop GUI, job queue with live progress" width="400" /> | <img src="assets/gui_plan_editor.png" alt="PureFrame desktop GUI, shot editor with a color-coded timeline" width="400" /> |

To run it from source:

```bash
cd gui && npm install && npm run tauri dev
```

## Known limitations

It isn't perfect. Some explicit content can still slip through, so treat it as a tool, not a replacement for parental judgment. [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) has the full list: what was fixed, what's only better (with what's left over spelled out), and what I've accepted and why. The short version:

- Swimwear and shirtless athletes are held back by a scene-context factor. For museums and surgical footage, use `--content-type art` or `--content-type medical`.
- Dark scenes, grayscale, flash frames, small or distant figures and extreme close-ups get a second look: normalization first, then a bounded rescan with tiled zoom.
- Variable frame rate input is converted to constant frame rate automatically. AV1 stays AV1 when re-encoded, and HDR10 metadata survives.

## Legal and privacy

PureFrame is meant for private, local use on video files you're legally allowed to have. It only works on local, unencrypted files. It doesn't get around DRM, download or upload anything, or share altered copies. Laws vary and this isn't legal advice. More in [docs/legal.md](docs/legal.md).

The first run downloads the AI models (about 400 to 500 MB). After that it never touches the network, and there's no telemetry. Models are cached in the usual place for your OS (`~/.cache/` on Linux, `~/Library/Caches/` on macOS, `%LOCALAPPDATA%\cache\` on Windows). The [installation guide](docs/installation.md#model-downloads) explains how to delete them, and the [privacy policy](docs/privacy.md) has the details.

## Docs

- [Installation](docs/installation.md): platform setup, GPU, troubleshooting
- [CLI reference](docs/cli-reference.md)
- [Calibration](docs/CALIBRATION.md): thresholds, content types, how to tune them
- [Parental guides](docs/guides.md): use known scene timestamps (from a saved guide page, say) as detection targets
- [Known limitations](docs/KNOWN_LIMITATIONS.md)
- [Evaluation](docs/evaluation.md) and [real-footage evaluation](docs/real-footage-eval.md), which lets you score your own clips against hand-marked ranges
- [Performance](docs/performance.md) and [benchmarks](BENCHMARKS.md)
- [censorplan.json format](docs/censor-plan-schema.md)
- [Architecture](docs/architecture.md)
- [Privacy](docs/privacy.md), [security](SECURITY.md) and [legal](docs/legal.md)
- [Examples](examples/), [changelog](CHANGELOG.md) and [roadmap](ROADMAP.md)

## Credits

PureFrame sits on top of [NudeNet](https://github.com/notAI-tech/NudeNet) for nudity detection, [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) for shot boundaries, [CLIP](https://github.com/openai/CLIP) for scene understanding, [PANNs](https://github.com/qiuqiangkong/audioset_tagging_cnn) for audio classification, [FFmpeg](https://ffmpeg.org/) for video I/O and [Tauri](https://tauri.app/) for the desktop app. Thanks to everyone who works on them.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md), and look for issues labeled `good first issue` if you want somewhere to start.

## License

[MIT](LICENSE)
