"""Build a shareable source package without local credentials or runtime data."""

from __future__ import annotations

import hashlib
import io
import os
import re
import zipfile
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = "工银e生-21天扑满计划"
SOURCE_DIRS = {"web", "21day-wealth-script", "picture_copy", "tools"}
ROOT_FILES = {"README.md", ".gitignore"}
EXCLUDED_DIRS = {".git", ".agents", ".codex", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules", "dist", ".secrets", "secrets"}
KEY_PATTERN = re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}")


def excluded(relative: Path) -> bool:
    name = relative.name.lower()
    return (
        any(part.lower() in EXCLUDED_DIRS for part in relative.parts)
        or name.startswith("~$")
        or (name.startswith(".env") and name != ".env.example")
        or name == "deepseek.json"
        or ".sqlite3" in name
        or name.endswith((".db", ".db-wal", ".db-shm", ".pyc", ".pyo", ".log", ".tmp", ".bak", ".key", ".pem", ".secret", ".local.json"))
    )


def source_files() -> list[Path]:
    files = []
    for path in ROOT.iterdir():
        if path.is_file() and (path.name in ROOT_FILES or path.suffix.lower() == ".docx") and not excluded(path.relative_to(ROOT)):
            files.append(path)
        elif path.name in SOURCE_DIRS and path.is_dir() and not path.is_symlink():
            for directory, subdirs, names in os.walk(path, followlinks=False):
                subdirs[:] = [name for name in subdirs if name.lower() not in EXCLUDED_DIRS]
                for name in names:
                    source = Path(directory) / name
                    if not excluded(source.relative_to(ROOT)):
                        files.append(source)
    for path in files:
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise RuntimeError("External link excluded from package: " + str(path.relative_to(ROOT)))
    return sorted(files, key=lambda path: path.relative_to(ROOT).as_posix())


def check_payload(relative: Path, payload: bytes) -> None:
    if KEY_PATTERN.search(payload):
        raise RuntimeError("Possible API key found; package stopped: " + str(relative))
    if relative.suffix.lower() == ".docx":
        with zipfile.ZipFile(io.BytesIO(payload)) as document:
            for member in document.infolist():
                if member.filename.endswith((".xml", ".rels")) and KEY_PATTERN.search(document.read(member)):
                    raise RuntimeError("Possible API key in Word document; package stopped: " + str(relative))


def main() -> None:
    contents = {}
    for source in source_files():
        relative = source.relative_to(ROOT)
        payload = source.read_bytes()
        check_payload(relative, payload)
        contents[relative.as_posix()] = payload

    required = {"README.md", "web/index.html", "web/server.py", "web/ai_service.py", "web/behavior_model.py", "web/private_config.py", "web/.env.example"}
    if not required.issubset(contents):
        raise RuntimeError("Required project files are missing")
    if [name for name in contents if Path(name).name.lower() == "readme.md"] != ["README.md"]:
        raise RuntimeError("Project documentation must be consolidated into the root README.md")

    manifest = "".join(hashlib.sha256(data).hexdigest() + "  " + name + "\n" for name, data in contents.items())
    contents["MANIFEST.sha256"] = manifest.encode("utf-8")
    output_dir = ROOT / "dist"
    output_dir.mkdir(exist_ok=True)
    stem = PACKAGE_ROOT + "-完整项目-" + date.today().isoformat()
    output = output_dir / (stem + ".zip")
    sequence = 2
    while output.exists() or output.with_suffix(".sha256").exists():
        output = output_dir / (stem + "-" + str(sequence) + ".zip")
        sequence += 1
    with zipfile.ZipFile(output, mode="x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for relative, payload in contents.items():
            archive.writestr(PACKAGE_ROOT + "/" + relative, payload)

    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP integrity check failed")
        for relative, payload in contents.items():
            if archive.read(PACKAGE_ROOT + "/" + relative) != payload:
                raise RuntimeError("Archive content mismatch: " + relative)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".sha256").write_text(digest + "  " + output.name + "\n", encoding="utf-8")
    print("Archive:", output)
    print("Files:", len(contents))
    print("Size (MiB):", round(output.stat().st_size / (1024 * 1024), 2))
    print("SHA-256:", digest)
    print("Verified: one README, no suspected API keys, ZIP integrity, all file contents")


if __name__ == "__main__":
    main()
