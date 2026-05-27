"""Auto-update checker/downloader cho eMeX."""
from __future__ import annotations

import json
import os
import platform
import plistlib
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import NamedTuple

from PyQt6.QtCore import QObject, pyqtSignal

from .config import APP_VERSION, CONFIG_DIR
from .i18n import t


GITHUB_REPO = "nhhai-math/eMeX"
_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases?per_page=30"
_SKIP_FILE = Path(CONFIG_DIR) / "update_skip.json"
_LOG_FILE = Path(CONFIG_DIR) / "update.log"


class ReleaseInfo(NamedTuple):
    version: str
    tag: str
    body: str
    download_url: str


def _log(message: str) -> None:
    text = f"[updater] {message}"
    print(text)
    try:
        _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception:
        pass


def _bundle_info_version() -> str:
    if not (getattr(sys, "frozen", False) and sys.platform == "darwin"):
        return ""
    try:
        exe_path = Path(sys.executable).resolve()
        app_bundle = exe_path.parents[2]
        plist_path = app_bundle / "Contents" / "Info.plist"
        with plist_path.open("rb") as f:
            info = plistlib.load(f)
        return str(info.get("CFBundleShortVersionString") or "").strip()
    except Exception as exc:
        _log(f"khong doc duoc Info.plist version: {exc}")
        return ""


def current_version() -> str:
    version = _bundle_info_version()
    return version or APP_VERSION


def _version_tuple(v: str) -> tuple[int, ...]:
    text = (v or "").strip()
    if text.lower().startswith("v"):
        text = text[1:]
    match = re.match(r"(\d+(?:\.\d+)*)", text)
    if not match:
        return (0,)
    return tuple(int(x) for x in match.group(1).split("."))


def _clean_version(tag_or_version: str) -> str:
    text = (tag_or_version or "").strip()
    if text.lower().startswith("v"):
        text = text[1:]
    match = re.match(r"(\d+(?:\.\d+)*)", text)
    return match.group(1) if match else ""


def _asset_name() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows":
        return "emex-windows-x64.zip"
    if system == "darwin":
        if machine in ("arm64", "aarch64"):
            return "emex-macos-arm64.tar.gz"
        return "emex-macos-intel.tar.gz"
    return "emex-linux-x64.tar.gz"


def _get_json(url: str) -> "dict | list | None":
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "eMeX-Updater/1.0",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        _log(f"GET {url} loi: {exc}")
        return None


def fetch_latest_release() -> ReleaseInfo | None:
    def _from_release(data: dict) -> ReleaseInfo | None:
        tag = data.get("tag_name") or ""
        version = _clean_version(tag)
        if not version:
            return None
        asset = _asset_name()
        download_url = next(
            (
                item.get("browser_download_url", "")
                for item in data.get("assets", [])
                if item.get("name") == asset
            ),
            "",
        )
        return ReleaseInfo(
            version=version,
            tag=tag,
            body=data.get("body", "") or "",
            download_url=download_url,
        )

    releases = _get_json(_RELEASES_URL)
    if isinstance(releases, list):
        candidates = [
            info
            for item in releases
            if isinstance(item, dict)
            and not item.get("draft")
            and not item.get("prerelease")
            for info in [_from_release(item)]
            if info is not None
        ]
        if candidates:
            candidates.sort(key=lambda r: _version_tuple(r.version), reverse=True)
            chosen = candidates[0]
            _log(f"chon release moi nhat theo so phien ban: {chosen.tag}")
            return chosen

    latest = _get_json(_API_URL)
    if isinstance(latest, dict):
        return _from_release(latest)
    return None


def is_newer(latest: str) -> bool:
    return bool(latest) and _version_tuple(latest) > _version_tuple(current_version())


def is_skipped(latest_version: str) -> bool:
    try:
        data = json.loads(_SKIP_FILE.read_text(encoding="utf-8"))
        return (
            data.get("skipped_version") == latest_version
            and data.get("from_version") == current_version()
        )
    except Exception:
        return False


def set_skipped_version(latest_version: str) -> None:
    try:
        _SKIP_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SKIP_FILE.write_text(
            json.dumps(
                {
                    "skipped_version": latest_version,
                    "from_version": current_version(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


class UpdateChecker(QObject):
    update_available = pyqtSignal(object)
    check_done = pyqtSignal()

    def run(self) -> None:
        release = fetch_latest_release()
        current = current_version()
        latest = release.version if release else "N/A"
        _log(
            f"hien tai={current!r} | moi nhat={latest!r} "
            f"| asset={_asset_name()} | co_asset={bool(release and release.download_url)}"
        )
        if release and is_newer(release.version) and not is_skipped(release.version):
            self.update_available.emit(release)
        self.check_done.emit()


class UpdateDownloader(QObject):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(bool, str)

    def __init__(self, release: ReleaseInfo) -> None:
        super().__init__()
        self._release = release
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            self._do_update()
        except Exception as exc:
            self.finished.emit(False, str(exc))

    def _do_update(self) -> None:
        if not getattr(sys, "frozen", False):
            self.finished.emit(False, t("Đang chạy từ mã nguồn nên không hỗ trợ tự cập nhật."))
            return
        if not self._release.download_url:
            self.finished.emit(
                False,
                t("Không tìm thấy gói cập nhật phù hợp ({asset}).", asset=_asset_name()),
            )
            return

        tmp = tempfile.mkdtemp(prefix="emex_upd_")
        archive = os.path.join(tmp, _asset_name())

        req = urllib.request.Request(
            self._release.download_url,
            headers={"User-Agent": "eMeX-Updater/1.0"},
        )
        with urllib.request.urlopen(req, timeout=180.0) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            done = 0
            with open(archive, "wb") as f:
                while True:
                    if self._cancelled:
                        self.finished.emit(False, t("Đã hủy cập nhật."))
                        return
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    self.progress.emit(done, total)

        extract_dir = os.path.join(tmp, "x")
        os.makedirs(extract_dir, exist_ok=True)
        self._extract_archive(archive, extract_dir)
        system = platform.system().lower()
        src = self._find_extracted_app(extract_dir, system)
        if src is None:
            expected = "eMeX.app" if system == "darwin" else "eMeX"
            raise RuntimeError(t("Không tìm thấy '{expected}' trong gói cập nhật.", expected=expected))

        exe_path = Path(sys.executable).resolve()
        if system == "darwin":
            app_bundle = exe_path.parents[2]
            dest_parent = str(app_bundle.parent)
            dest_name = app_bundle.name
        elif system == "linux":
            dest_parent = str(exe_path.parent.parent)
            dest_name = exe_path.parent.name
        else:
            dest_parent = str(exe_path.parent)
            dest_name = ""

        self._schedule(src, dest_parent, dest_name, str(exe_path), tmp, system)
        self.finished.emit(True, "")

    def _extract_archive(self, archive: str, dest: str) -> None:
        if archive.endswith(".zip"):
            with zipfile.ZipFile(archive, "r") as zf:
                zf.extractall(dest)
        else:
            with tarfile.open(archive, "r:gz") as tf:
                tf.extractall(dest)

    def _find_extracted_app(self, root: str, system: str) -> str | None:
        root_path = Path(root)
        if system == "darwin":
            for path in [root_path, *root_path.rglob("eMeX.app")]:
                if path.name == "eMeX.app" and path.is_dir():
                    return str(path)
            return None

        exe_name = "eMeX.exe" if system == "windows" else "eMeX"
        if (root_path / exe_name).is_file():
            return str(root_path)
        for path in root_path.rglob(exe_name):
            if path.is_file():
                return str(path.parent)
        return None

    def _schedule(
        self,
        src: str,
        dest_parent: str,
        dest_name: str,
        exe: str,
        tmp: str,
        system: str,
    ) -> None:
        current_pid = os.getpid()

        def sh_quote(value: str) -> str:
            return "'" + value.replace("'", "'\"'\"'") + "'"

        if system == "windows":
            dest = os.path.join(dest_parent, dest_name) if dest_name else dest_parent
            log = str(Path(CONFIG_DIR) / "update-install.log")
            script = os.path.join(tmp, "update-emex.ps1")

            def ps_quote(value: str) -> str:
                return "'" + value.replace("'", "''") + "'"

            ps1 = f"""\
$ErrorActionPreference = 'Stop'
$Source = {ps_quote(src)}
$Destination = {ps_quote(dest)}
$Exe = {ps_quote(exe)}
$Log = {ps_quote(log)}
$OldPid = {current_pid}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Log) | Out-Null
function Write-InstallLog([string]$Message) {{
    Add-Content -Path $Log -Encoding UTF8 -Value ("[install] " + $Message)
}}

try {{
    Write-InstallLog "waiting for old process $OldPid"
    $oldProcess = Get-Process -Id $OldPid -ErrorAction SilentlyContinue
    if ($oldProcess) {{
        $oldProcess.WaitForExit(120000)
    }}
    $oldProcess = Get-Process -Id $OldPid -ErrorAction SilentlyContinue
    if ($oldProcess) {{
        Stop-Process -Id $OldPid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }}

    Write-InstallLog "copying from $Source to $Destination"
    & robocopy $Source $Destination /E /R:20 /W:1 /NFL /NDL /NP /NJH /NJS | Out-File -FilePath $Log -Append -Encoding UTF8
    $rc = $LASTEXITCODE
    Write-InstallLog "robocopy exit code $rc"
    if ($rc -ge 8) {{
        throw "robocopy failed with exit code $rc"
    }}

    Start-Process -FilePath $Exe -WorkingDirectory (Split-Path -Parent $Exe) -WindowStyle Normal
}} catch {{
    Write-InstallLog ("error: " + $_.Exception.Message)
}} finally {{
    Start-Sleep -Seconds 1
    Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
}}
"""
            with open(script, "w", encoding="utf-8-sig") as f:
                f.write(ps1)

            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-WindowStyle",
                    "Hidden",
                    "-File",
                    script,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
                startupinfo=startupinfo,
                close_fds=True,
            )
            return

        if system == "darwin":
            dest = os.path.join(dest_parent, dest_name)
            script = os.path.join(tmp, "update-emex.sh")
            sh = (
                "#!/bin/bash\n"
                f"while kill -0 {current_pid} 2>/dev/null; do sleep 1; done\n"
                f"rm -rf {sh_quote(dest)}\n"
                f"cp -R {sh_quote(src)} {sh_quote(dest_parent + '/')}\n"
                f"open {sh_quote(dest)}\n"
                'rm -- "$0"\n'
            )
            with open(script, "w", encoding="utf-8") as f:
                f.write(sh)
            os.chmod(script, 0o755)
            subprocess.Popen(["bash", script])
            return

        dest = os.path.join(dest_parent, dest_name) if dest_name else dest_parent
        script = os.path.join(tmp, "update-emex.sh")
        log = str(Path(CONFIG_DIR) / "update-install.log")
        exe_name = Path(exe).name
        sh = f"""\
#!/bin/bash
set -euo pipefail

Source={sh_quote(src)}
Destination={sh_quote(dest)}
ExeName={sh_quote(exe_name)}
Log={sh_quote(log)}
OldPid={current_pid}
Stage="${{Destination}}.new.$$"
Backup="${{Destination}}.old.$$"

mkdir -p "$(dirname "$Log")"
write_log() {{
    printf '[install] %s\\n' "$1" >> "$Log"
}}
cleanup() {{
    rc=$?
    if [ "$rc" -ne 0 ]; then
        write_log "error: installer exited with code $rc"
        if [ -d "$Backup" ] && [ ! -d "$Destination" ]; then
            mv "$Backup" "$Destination" || true
        fi
    fi
    rm -rf "$Stage"
    rm -- "$0" 2>/dev/null || true
}}
trap cleanup EXIT

for _ in $(seq 1 120); do
    if kill -0 "$OldPid" 2>/dev/null; then sleep 1; else break; fi
done
if kill -0 "$OldPid" 2>/dev/null; then
    kill "$OldPid" 2>/dev/null || true
    sleep 2
fi

rm -rf "$Stage" "$Backup"
mkdir -p "$Stage"
cp -a "$Source/." "$Stage/"
chmod +x "$Stage/$ExeName"
if [ -d "$Destination" ]; then
    mv "$Destination" "$Backup"
fi
mv "$Stage" "$Destination"
rm -rf "$Backup"
nohup "$Destination/$ExeName" >/dev/null 2>&1 &
"""
        with open(script, "w", encoding="utf-8") as f:
            f.write(sh)
        os.chmod(script, 0o755)
        subprocess.Popen(["bash", script])
