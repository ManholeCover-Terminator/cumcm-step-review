#!/usr/bin/env python3
"""使用隔离的 LibreOffice 配置接受 DOCX 中的全部修订。"""

import argparse
import logging
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from office.soffice import get_soffice_env


logger = logging.getLogger(__name__)

ACCEPT_CHANGES_MACRO = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE script:module PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" "module.dtd">
<script:module xmlns:script="http://openoffice.org/2000/script" script:name="Module1" script:language="StarBasic">
    Sub AcceptAllTrackedChanges()
        Dim frame As Object
        Dim dispatcher As Object
        frame = ThisComponent.CurrentController.Frame
        dispatcher = createUnoService("com.sun.star.frame.DispatchHelper")
        dispatcher.executeDispatch(frame, ".uno:AcceptAllTrackedChanges", "", 0, Array())
        ThisComponent.store()
        ThisComponent.close(True)
    End Sub
</script:module>"""

TRACKED_TAG = re.compile(rb"<w:(?:ins|del|moveFrom|moveTo)\b")


def contains_tracked_changes(path: Path) -> bool:
    """检查 DOCX 的所有 Word XML 部件是否仍含修订标记。"""
    with zipfile.ZipFile(path) as archive:
        return any(
            TRACKED_TAG.search(archive.read(name))
            for name in archive.namelist()
            if name.startswith("word/") and name.endswith(".xml")
        )


def _setup_libreoffice_macro(profile: Path) -> bool:
    macro_dir = profile / "user" / "basic" / "Standard"
    macro_file = macro_dir / "Module1.xba"
    try:
        initialized = subprocess.run(
            [
                "soffice",
                "--headless",
                f"-env:UserInstallation={profile.resolve().as_uri()}",
                "--terminate_after_init",
            ],
            capture_output=True,
            timeout=10,
            check=False,
            env=get_soffice_env(),
        )
        if initialized.returncode != 0:
            return False
        macro_dir.mkdir(parents=True, exist_ok=True)
        macro_file.write_text(ACCEPT_CHANGES_MACRO, encoding="utf-8")
        return True
    except OSError as exc:
        logger.warning("无法创建 LibreOffice 宏: %s", exc)
        return False


def accept_changes(input_file: str, output_file: str) -> tuple[None, str]:
    source = Path(input_file).resolve()
    output = Path(output_file).resolve()
    if not source.is_file():
        return None, f"Error: 输入文件不存在: {source}"
    if source.suffix.lower() != ".docx":
        return None, f"Error: 输入文件不是 DOCX: {source}"

    try:
        with tempfile.TemporaryDirectory(prefix="math-modeling-docx-") as temp_dir:
            temp_root = Path(temp_dir)
            profile = temp_root / "profile"
            working = temp_root / "working.docx"
            shutil.copy2(source, working)
            if not _setup_libreoffice_macro(profile):
                return None, "Error: 无法建立隔离的 LibreOffice 宏"

            command = [
                "soffice",
                "--headless",
                f"-env:UserInstallation={profile.resolve().as_uri()}",
                "--norestore",
                "vnd.sun.star.script:Standard.Module1.AcceptAllTrackedChanges?language=Basic&location=application",
                str(working),
            ]
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
                env=get_soffice_env(),
            )
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout or "未知错误").strip()
                return None, f"Error: LibreOffice 接受修订失败: {detail}"
            if contains_tracked_changes(working):
                return None, "Error: 处理后仍检测到修订标记，未发布输出文件"

            output.parent.mkdir(parents=True, exist_ok=True)
            temporary_output = output.with_name(f".{output.name}.tmp")
            shutil.copy2(working, temporary_output)
            os.replace(temporary_output, output)
            return None, f"已接受全部修订: {source} -> {output}"
    except subprocess.TimeoutExpired:
        return None, "Error: LibreOffice 接受修订超时，未发布输出文件"
    except FileNotFoundError:
        return None, "Error: 未找到 LibreOffice 可执行文件 soffice"
    except (OSError, zipfile.BadZipFile) as exc:
        return None, f"Error: DOCX 处理失败: {exc}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="接受 DOCX 中的全部修订")
    parser.add_argument("input_file")
    parser.add_argument("output_file")
    args = parser.parse_args()
    _, message = accept_changes(args.input_file, args.output_file)
    print(message)
    if message.startswith("Error:"):
        raise SystemExit(1)
