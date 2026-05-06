import os

with open("pureframe/cli.py", "w") as f:
    f.write('''import typer
import numpy as np
import cv2
import json
import platformdirs
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.table import Table

from pureframe.config import Config
from pureframe.hardware import HardwareProfile, detect_profile, get_settings
from pureframe.utils.logging import setup_logging
from pureframe.pipeline.probe import probe_video
from pureframe.pipeline.shots import detect_shots, Action, Category, ShotVerdict
from pureframe.pipeline.sample import sample_keyframes, extract_frames
from pureframe.pipeline.detect.nudity import NudityDetector
from pureframe.pipeline.densify import densify_shot
from pureframe.pipeline.smooth import smooth_detections
from pureframe.pipeline.render.apply import apply_censoring
from pureframe.pipeline.detect.scene_clip import SceneClassifier, ShotContext
from pureframe.pipeline.detect.audio import AudioClassifier, AudioContext
from pureframe.pipeline.detect.face import FaceDetector
from pureframe.pipeline.fuse import fuse
from pureframe.checkpoint import CheckpointStore

app = typer.Typer(help="PureFrame CLI")
jobs_app = typer.Typer(help="Manage jobs and checkpoints")
app.add_typer(jobs_app, name="jobs")

console = Console()

def get_store() -> CheckpointStore:
    db_path = Path(platformdirs.user_data_dir("PureFrame")) / "jobs.db"
    return CheckpointStore(db_path)

def process_file(config: Config):
    store = get_store()
    job = store.find_or_create_job(config.input_path, config.output_path, config)
    
    if job.status == "DONE":
        console.print(f"[green]Job {job.id} for {config.input_path.name} is already DONE. Skipping.[/green]")
        return
        
    settings = get_settings(config.profile)
    
    console.print(f"[bold blue]PureFrame[/bold blue] v0.2.0")
    console.print(f"Job ID: {job.id}")
    console.print(f"Profile: [bold]{settings.profile.value}[/bold]")
    console.print(f"Input: {config.input_path}")
    console.print(f"Output: {config.output_path}\\n")
    
    flagged_verdicts = []
    shots = []
    
    if job.status in ("RENDERING", "SHOTS_DETECTED"):
        verdicts = store.load_verdicts(job.id)
        shots = detect_shots(config.input_path)
        
        for v in verdicts:
            if v.action != Action.NONE:
                flagged_verdicts.append((shots[v.index], v))
    else:
        store.update_status(job.id, "DETECTING")
        
        with console.status("[bold green]Probing video..."):
            meta = probe_video(config.input_path)
            
        with console.status("[bold green]Detecting shots..."):
            shots = detect_shots(config.input_path)
            
        store.update_status(job.id, "DETECTING", total_shots=len(shots))
        console.print(f"Detected {len(shots)} shots.")
        
        detector = NudityDetector(settings)
        scene_classifier = SceneClassifier(settings)
        if config.no_clip:
            scene_classifier.enabled = False
            
        audio_classifier = AudioClassifier(settings)
        if config.no_audio or len(meta.audio_streams) == 0:
            audio_classifier.enabled = False
            
        face_detector = FaceDetector()
        
        existing_verdicts = store.load_verdicts(job.id)
        completed_indices = {v.index for v in existing_verdicts}
        
        for v in existing_verdicts:
            if v.action != Action.NONE:
                flagged_verdicts.append((shots[v.index], v))
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                console=console
            ) as progress:
                task = progress.add_task("Analyzing shots...", total=len(shots), completed=len(completed_indices))
                
                for shot in shots:
                    if shot.index in completed_indices:
                        continue
                        
                    progress.update(task, description=f"Analyzing [shot {shot.index+1}/{len(shots)}]")
                    kf_indices = sample_keyframes(shot, settings.sample_keyframes_per_shot)
                    frames_bgr = extract_frames(config.input_path, kf_indices, settings.detection_resolution)
                    
                    frames_list = [frames_bgr[i] for i in kf_indices if i in frames_bgr]
                    if not frames_list:
                        verdict = ShotVerdict(index=shot.index, action=Action.NONE, category=Category.SAFE)
                        store.save_verdict(job.id, verdict)
                        progress.advance(task)
                        continue
                        
                    batch_dets = detector.detect_batch(frames_list)
                    
                    mid_idx = len(frames_list) // 2
                    mid_frame = frames_list[mid_idx]
                    scene_ctx = scene_classifier.classify_shot(mid_frame)
                    
                    start_sec = shot.start_frame / meta.fps
                    end_sec = shot.end_frame / meta.fps
                    audio_ctx = audio_classifier.classify_segment(config.input_path, start_sec, end_sec)
                    
                    verdict = fuse(shot, batch_dets, scene_ctx, audio_ctx, config, strict_mode=config.strict)
                    
                    if config.strict and verdict.category == Category.KISS_LIGHT:
                        verdict.action = Action.BLACK_BOX
                    
                    if verdict.action != Action.NONE:
                        if verdict.action == Action.BLACK_BOX:
                            if verdict.category in (Category.KISS_INTENSE, Category.KISS_LIGHT):
                                all_frames = list(range(shot.start_frame, shot.end_frame))
                                all_bgr = extract_frames(config.input_path, all_frames, settings.detection_resolution)
                                
                                dense_faces = {}
                                for f_idx, f_bgr in all_bgr.items():
                                    mouths = face_detector.detect_mouths(f_bgr)
                                    from pureframe.pipeline.detect.nudity import Detection
                                    dense_faces[f_idx] = [Detection(label="MOUTH", score=1.0, box=m) for m in mouths]
                                
                                smooth_mouths = smooth_detections(dense_faces, shot, config.box_padding_pct)
                                verdict.boxes = smooth_mouths
                            else:
                                from pureframe.pipeline.shots import FrameResult
                                for idx, dets in zip(kf_indices, batch_dets):
                                    shot.frames[idx] = FrameResult(frame_idx=idx, detections=dets)
                                
                                dense_dets = densify_shot(shot, config.input_path, detector, settings, config.nudity_threshold)
                                smooth_boxes = smooth_detections(dense_dets, shot, config.box_padding_pct)
                                verdict.boxes = smooth_boxes
                        
                        flagged_verdicts.append((shot, verdict))
                        
                    store.save_verdict(job.id, verdict)
                    progress.advance(task)
                    
        except KeyboardInterrupt:
            store.update_status(job.id, "FAILED", error="Interrupted by user")
            raise
        except Exception as e:
            store.update_status(job.id, "FAILED", error=str(e))
            raise
            
        if not settings.keep_models_loaded:
            detector.unload()
            scene_classifier.unload()
            audio_classifier.unload()
            del detector
            del scene_classifier
            del audio_classifier
            del face_detector
            
        store.update_status(job.id, "RENDERING")
        
    console.print(f"Flagged {len(flagged_verdicts)} shots for censoring.")
    
    frame_actions = {}
    for shot, verdict in flagged_verdicts:
        for f in range(shot.start_frame, shot.end_frame):
            if f not in frame_actions:
                frame_actions[f] = {"action": Action.NONE, "boxes": []}
            
            curr = frame_actions[f]
            if verdict.action == Action.FULL_FRAME_BLUR:
                curr["action"] = Action.FULL_FRAME_BLUR
            elif verdict.action == Action.BLACK_BOX and curr["action"] != Action.FULL_FRAME_BLUR:
                curr["action"] = Action.BLACK_BOX
                if verdict.boxes and f in verdict.boxes:
                    curr["boxes"].extend(verdict.boxes[f])
                    
    try:
        with console.status("[bold green]Rendering final video... (this may take a while)"):
            apply_censoring(config.input_path, config.output_path, frame_actions, config, get_settings(config.profile))
            
        store.update_status(job.id, "DONE")
        console.print(f"\\n[bold green]Success![/bold green] Output saved to {config.output_path}")
        console.print(f"Total censored frames: {len(frame_actions)}")
    except KeyboardInterrupt:
        store.update_status(job.id, "FAILED", error="Interrupted during rendering")
        raise
    except Exception as e:
        store.update_status(job.id, "FAILED", error=str(e))
        raise

@app.command("process")
def process_cmd(
    input: Path = typer.Argument(..., exists=True, help="Path to input video file or folder"),
    output: Path = typer.Option(None, "--output", "-o", help="Path to output video file (ignored if input is folder)"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Process folder recursively"),
    parallel: int = typer.Option(1, "--parallel", "-p", help="Number of parallel workers for folders"),
    profile: HardwareProfile = typer.Option(None, "--profile", help="Hardware profile override"),
    threshold: float = typer.Option(0.55, "--threshold", help="Nudity detection threshold"),
    strict: bool = typer.Option(False, "--strict", help="Lowers thresholds 15% across the board"),
    no_clip: bool = typer.Option(False, "--no-clip", help="Disables CLIP scene classifier"),
    no_audio: bool = typer.Option(False, "--no-audio", help="Disables audio classifier"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging")
):
    """
    Process a video file or folder to censor explicit content.
    """
    setup_logging(log_level="DEBUG" if verbose else "INFO")
    
    if profile is None:
        profile = detect_profile()
        
    if input.is_dir():
        from pureframe.batch import process_folder
        # create a dummy config with a fake file path to satisfy Pydantic
        dummy_file = Path("/tmp/dummy.mp4")
        dummy_file.touch()
        base_config = Config.from_cli(
            input_path=dummy_file,
            profile=profile,
            nudity_threshold=threshold,
            strict=strict,
            no_clip=no_clip,
            no_audio=no_audio,
            log_level="DEBUG" if verbose else "INFO"
        )
        process_folder(input, recursive, parallel, base_config)
    else:
        config = Config.from_cli(
            input_path=input,
            output_path=output,
            profile=profile,
            nudity_threshold=threshold,
            strict=strict,
            no_clip=no_clip,
            no_audio=no_audio,
            log_level="DEBUG" if verbose else "INFO"
        )
        process_file(config)

@jobs_app.command("list")
def jobs_list():
    """List all unfinished jobs."""
    store = get_store()
    unfinished = store.list_unfinished()
    if not unfinished:
        console.print("No unfinished jobs.")
        return
        
    table = Table(title="Unfinished Jobs")
    table.add_column("ID")
    table.add_column("Input")
    table.add_column("Status")
    table.add_column("Completed / Total")
    table.add_column("Started At")
    
    for j in unfinished:
        p = Path(j.input_path).name
        table.add_row(str(j.id), p, j.status, f"{j.completed_shots} / {j.total_shots or '?'}", str(j.started_at))
    console.print(table)

@jobs_app.command("resume")
def jobs_resume(job_id: int = typer.Argument(..., help="Job ID to resume")):
    """Resume a specific job by ID."""
    store = get_store()
    unfinished = store.list_unfinished()
    job = next((j for j in unfinished if j.id == job_id), None)
    
    if not job:
        console.print(f"[red]Job {job_id} not found or already DONE.[/red]")
        return
        
    if not job.config_json:
        console.print(f"[red]Job {job_id} does not have a saved configuration to resume from.[/red]")
        return
        
    console.print(f"Resuming job {job_id} on {job.input_path}...")
    cfg = Config.model_validate_json(job.config_json)
    process_file(cfg)

@jobs_app.command("cleanup")
def jobs_cleanup():
    """Delete jobs marked DONE more than 30 days ago."""
    store = get_store()
    with store.conn:
        cursor = store.conn.cursor()
        cursor.execute("DELETE FROM shot_verdicts WHERE job_id IN (SELECT id FROM jobs WHERE status = 'DONE' AND finished_at < datetime('now', '-30 days'))")
        cursor.execute("DELETE FROM jobs WHERE status = 'DONE' AND finished_at < datetime('now', '-30 days')")
        deleted = cursor.rowcount
    console.print(f"Cleaned up {deleted} old jobs.")

if __name__ == "__main__":
    app()
''')

os.system("python update_cli.py")
