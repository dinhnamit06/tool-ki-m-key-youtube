import json
import shutil
from datetime import datetime
from pathlib import Path


def _sanitize_name(text: str, fallback: str = "project") -> str:
    safe = "".join(ch if ch.isalnum() or ch in (" ", "-", "_") else "_" for ch in str(text or "").strip())
    safe = "_".join(part for part in safe.split() if part)
    return safe[:80] or fallback


def _scene_lines(project_data: dict) -> str:
    lines = []
    for scene in project_data.get("scenes", []):
        lines.append(
            "\n".join(
                [
                    f"{scene.get('scene_no', '')} | {scene.get('title', '')} | {scene.get('duration', '')}",
                    f"Visual Goal: {scene.get('visual_goal', '')}",
                    f"Voiceover: {scene.get('voiceover', '')}",
                    f"Shot Type: {scene.get('shot_type', '')}",
                    f"Status: {scene.get('status', '')}",
                    f"Clip: {scene.get('clip_file_name', '') or scene.get('clip', '')}",
                ]
            ).strip()
        )
    return "\n\n".join(line for line in lines if line.strip()).strip()


def _prompt_lines(project_data: dict) -> str:
    lines = []
    for scene in project_data.get("scenes", []):
        prompt = str(scene.get("prompt_draft", "")).strip()
        if not prompt:
            continue
        lines.append(f"{scene.get('scene_no', '')} - {scene.get('title', '')}\n{prompt}".strip())
    return "\n\n".join(lines).strip()


def export_project_package(project_data: dict, export_parent: str | Path) -> dict:
    parent = Path(export_parent)
    parent.mkdir(parents=True, exist_ok=True)

    project_name = str(project_data.get("project_name", "")).strip() or "My Veo Project"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    package_dir = parent / f"{_sanitize_name(project_name, 'veo_project')}_package_{stamp}"
    package_dir.mkdir(parents=True, exist_ok=True)

    clips_dir = package_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    source_script = str(project_data.get("source_script", "")).strip()
    source_file = package_dir / "source_script.txt"
    source_file.write_text(source_script, encoding="utf-8")

    scenes = list(project_data.get("scenes", []) or [])
    clips_manifest = []
    copied_clips = 0
    for scene in scenes:
        clip_path = str(scene.get("clip_path", "")).strip()
        copied_path = ""
        if clip_path:
            src = Path(clip_path)
            if src.exists() and src.is_file():
                target = clips_dir / src.name
                if target.resolve() != src.resolve():
                    shutil.copy2(src, target)
                copied_path = str(target)
                copied_clips += 1
        clips_manifest.append(
            {
                "scene_no": scene.get("scene_no", ""),
                "title": scene.get("title", ""),
                "status": scene.get("status", ""),
                "clip_file_name": scene.get("clip_file_name", "") or scene.get("clip", ""),
                "original_clip_path": clip_path,
                "copied_clip_path": copied_path,
                "veo_model": scene.get("veo_model", ""),
                "veo_operation_name": scene.get("veo_operation_name", ""),
                "veo_video_uri": scene.get("veo_video_uri", ""),
            }
        )

    (package_dir / "scene_plan.json").write_text(
        json.dumps(scenes, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (package_dir / "scene_plan.txt").write_text(_scene_lines(project_data), encoding="utf-8")
    (package_dir / "prompt_drafts.json").write_text(
        json.dumps(
            [
                {
                    "scene_no": scene.get("scene_no", ""),
                    "title": scene.get("title", ""),
                    "prompt_draft": scene.get("prompt_draft", ""),
                }
                for scene in scenes
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (package_dir / "prompt_drafts.txt").write_text(_prompt_lines(project_data), encoding="utf-8")
    (package_dir / "clip_manifest.json").write_text(
        json.dumps(clips_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (package_dir / "veo_settings.json").write_text(
        json.dumps(dict(project_data.get("veo_settings", {}) or {}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (package_dir / "project_manifest.json").write_text(
        json.dumps(
            {
                "project_name": project_name,
                "exported_at": stamp,
                "scene_count": len(scenes),
                "copied_clip_count": copied_clips,
                "prompt_format": project_data.get("prompt_format", ""),
                "project_prompt_settings": project_data.get("project_prompt_settings", {}),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "package_dir": str(package_dir),
        "scene_count": len(scenes),
        "copied_clip_count": copied_clips,
        "files": [
            "source_script.txt",
            "scene_plan.json",
            "scene_plan.txt",
            "prompt_drafts.json",
            "prompt_drafts.txt",
            "clip_manifest.json",
            "veo_settings.json",
            "project_manifest.json",
        ],
    }
