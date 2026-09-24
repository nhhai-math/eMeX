"""GitHub account and project-to-repository helpers for eMeX."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
import re
import shutil
import subprocess
import sys
from urllib.parse import urlparse

from .config import CONFIG_DIR, load_json, save_json


GITHUB_CONFIG_FILE = os.path.join(CONFIG_DIR, "github_config.json")
GITHUB_API = "https://api.github.com"
GITHUB_WEB = "https://github.com"


class GitHubIntegrationError(RuntimeError):
    """Raised when GitHub or local Git integration cannot complete."""


@dataclass(frozen=True)
class RepoReference:
    full_name: str
    html_url: str
    clone_url: str


def _default_config() -> dict:
    return {"token": "", "user": {}, "linked_repos": {}}


def load_github_config() -> dict:
    cfg = load_json(GITHUB_CONFIG_FILE, _default_config())
    if not isinstance(cfg, dict):
        return _default_config()
    if not isinstance(cfg.get("linked_repos"), dict):
        cfg["linked_repos"] = {}
    if not isinstance(cfg.get("user"), dict):
        cfg["user"] = {}
    if not isinstance(cfg.get("token"), str):
        cfg["token"] = ""
    return cfg


def save_github_config(cfg: dict) -> bool:
    clean = _default_config()
    if isinstance(cfg, dict):
        clean.update(cfg)
    return save_json(GITHUB_CONFIG_FILE, clean)


def save_auth_token(token: str, user: dict) -> bool:
    cfg = load_github_config()
    cfg["token"] = token.strip()
    cfg["user"] = {
        "login": user.get("login", ""),
        "name": user.get("name") or "",
        "html_url": user.get("html_url", ""),
        "avatar_url": user.get("avatar_url", ""),
    }
    return save_github_config(cfg)


def clear_auth_token() -> bool:
    cfg = load_github_config()
    cfg["token"] = ""
    cfg["user"] = {}
    return save_github_config(cfg)


def stored_token() -> str:
    return load_github_config().get("token", "")


def stored_user() -> dict:
    return load_github_config().get("user", {})


def _headers(token: str) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "eMeX",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _request_json(url: str, token: str) -> object:
    try:
        import requests
    except ImportError as exc:
        raise GitHubIntegrationError(
            "Thiếu thư viện requests. Cài dependencies bằng: pip install -r requirements.txt"
        ) from exc

    try:
        response = requests.get(url, headers=_headers(token), timeout=15)
    except requests.RequestException as exc:
        raise GitHubIntegrationError(f"Lỗi kết nối GitHub: {exc}") from exc

    if response.status_code in (401, 403):
        raise GitHubIntegrationError("Token GitHub không hợp lệ hoặc không đủ quyền.")
    if response.status_code == 404:
        raise GitHubIntegrationError("Không tìm thấy repo GitHub hoặc tài khoản không có quyền truy cập.")
    if response.status_code >= 400:
        detail = ""
        try:
            data = response.json()
            detail = data.get("message", "")
        except Exception:
            detail = response.text[:200]
        raise GitHubIntegrationError(f"GitHub trả về lỗi {response.status_code}: {detail}")
    try:
        return response.json()
    except ValueError as exc:
        raise GitHubIntegrationError("GitHub trả về dữ liệu không hợp lệ.") from exc


def verify_token(token: str) -> dict:
    token = token.strip()
    if not token:
        raise GitHubIntegrationError("Hãy nhập token GitHub.")
    data = _request_json(f"{GITHUB_API}/user", token)
    if not isinstance(data, dict) or not data.get("login"):
        raise GitHubIntegrationError("Không đọc được thông tin tài khoản GitHub.")
    return data


def list_user_repositories(token: str, *, max_pages: int = 5) -> list[dict]:
    repos: list[dict] = []
    for page in range(1, max_pages + 1):
        data = _request_json(
            f"{GITHUB_API}/user/repos?sort=updated&per_page=100&page={page}", token)
        if not isinstance(data, list):
            break
        repos.extend(
            {
                "full_name": item.get("full_name", ""),
                "html_url": item.get("html_url", ""),
                "clone_url": item.get("clone_url", ""),
                "private": bool(item.get("private")),
            }
            for item in data
            if isinstance(item, dict) and item.get("full_name")
        )
        if len(data) < 100:
            break
    return repos


def normalize_repo_reference(value: str) -> RepoReference:
    raw = (value or "").strip()
    if not raw:
        raise GitHubIntegrationError("Hãy nhập URL repo GitHub hoặc owner/repo.")

    path = raw
    if raw.startswith("git@github.com:"):
        path = raw.split(":", 1)[1]
    elif raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        host = parsed.netloc.lower()
        if host not in {"github.com", "www.github.com"}:
            raise GitHubIntegrationError("Hiện eMeX chỉ hỗ trợ repo trên github.com.")
        path = parsed.path.strip("/")
    elif raw.startswith("github.com/"):
        path = raw[len("github.com/"):]

    path = path.strip().strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2:
        raise GitHubIntegrationError("Repo phải có dạng owner/repo.")

    owner, repo = parts[0], parts[1]
    valid = re.compile(r"^[A-Za-z0-9_.-]+$")
    if not valid.match(owner) or not valid.match(repo):
        raise GitHubIntegrationError("Tên owner/repo GitHub không hợp lệ.")

    full_name = f"{owner}/{repo}"
    return RepoReference(
        full_name=full_name,
        html_url=f"{GITHUB_WEB}/{full_name}",
        clone_url=f"{GITHUB_WEB}/{full_name}.git",
    )


def _config_key(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def get_link_for_project(path: str) -> dict:
    if not path:
        return {}
    linked = load_github_config().get("linked_repos", {})
    current = os.path.abspath(path)
    while current:
        item = linked.get(_config_key(current))
        if item:
            return item
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return {}


def unlink_project(path: str) -> bool:
    if not path:
        return False
    cfg = load_github_config()
    linked = cfg.get("linked_repos", {})
    link = get_link_for_project(path)
    if not link:
        return False
    target = link.get("project_path") if link else path
    linked.pop(_config_key(target), None)
    cfg["linked_repos"] = linked
    return save_github_config(cfg)


def _creation_flags() -> int:
    if sys.platform == "win32":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def _run_process(args: list[str], cwd: str | None = None, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=_creation_flags(),
    )


def _git(args: list[str], cwd: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return _run_process(["git", *args], cwd=cwd, timeout=timeout)


def github_cli_token() -> str:
    gh = shutil.which("gh")
    if not gh:
        raise GitHubIntegrationError("Chưa tìm thấy GitHub CLI (gh) trên máy.")
    result = _run_process([gh, "auth", "token"], timeout=20)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        raise GitHubIntegrationError(message or "GitHub CLI chưa đăng nhập.")
    token = result.stdout.strip()
    if not token:
        raise GitHubIntegrationError("GitHub CLI không trả về token.")
    return token


def read_git_origin(folder: str) -> str:
    folder = os.path.abspath(folder)
    if not folder or not os.path.isdir(folder) or not shutil.which("git"):
        return ""
    result = _git(["remote", "get-url", "origin"], folder, timeout=10)
    return result.stdout.strip() if result.returncode == 0 else ""


def _existing_git_root(folder: str) -> str:
    if not shutil.which("git"):
        return os.path.abspath(folder)
    result = _git(["rev-parse", "--show-toplevel"], folder, timeout=10)
    if result.returncode == 0 and result.stdout.strip():
        return os.path.abspath(result.stdout.strip())
    return os.path.abspath(folder)


def _configure_git_origin(project_path: str, clone_url: str) -> str:
    if not shutil.which("git"):
        return "Đã lưu liên kết trong eMeX, nhưng chưa cấu hình được Git vì chưa tìm thấy lệnh git."

    messages: list[str] = []
    if not os.path.exists(os.path.join(project_path, ".git")):
        init_result = _git(["init"], project_path)
        if init_result.returncode != 0:
            message = (init_result.stderr or init_result.stdout or "").strip()
            raise GitHubIntegrationError(message or "Không khởi tạo được Git repo cho thư mục.")
        messages.append("đã khởi tạo Git repo")

    remote_result = _git(["remote", "get-url", "origin"], project_path, timeout=10)
    if remote_result.returncode == 0:
        set_result = _git(["remote", "set-url", "origin", clone_url], project_path)
        action = "đã cập nhật origin"
    else:
        set_result = _git(["remote", "add", "origin", clone_url], project_path)
        action = "đã thêm origin"

    if set_result.returncode != 0:
        message = (set_result.stderr or set_result.stdout or "").strip()
        raise GitHubIntegrationError(message or "Không cấu hình được remote origin.")

    messages.append(action)
    return ", ".join(messages)


def link_project_to_repo(folder: str, repo_value: str) -> dict:
    folder = os.path.abspath((folder or "").strip())
    if not folder or not os.path.isdir(folder):
        raise GitHubIntegrationError("Hãy chọn thư mục dự án hợp lệ.")

    repo = normalize_repo_reference(repo_value)
    project_path = _existing_git_root(folder)
    git_message = _configure_git_origin(project_path, repo.clone_url)

    cfg = load_github_config()
    linked = cfg.get("linked_repos", {})
    linked[_config_key(project_path)] = {
        "project_path": project_path,
        "repo": repo.full_name,
        "repo_url": repo.clone_url,
        "html_url": repo.html_url,
        "linked_at": datetime.now(timezone.utc).isoformat(),
    }
    cfg["linked_repos"] = linked
    save_github_config(cfg)

    return {
        "project_path": project_path,
        "repo": repo.full_name,
        "repo_url": repo.clone_url,
        "html_url": repo.html_url,
        "git_message": git_message,
    }
