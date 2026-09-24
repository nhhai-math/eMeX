"""GitHub account and project link dialog."""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (QComboBox, QDialog, QFileDialog, QFormLayout,
                              QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                              QMessageBox, QPushButton, QVBoxLayout, QWidget)

from .dialogs import LIGHT_QSS
from .github_integration import (clear_auth_token, get_link_for_project,
                                 github_cli_token, link_project_to_repo,
                                 list_user_repositories,
                                 normalize_repo_reference, read_git_origin,
                                 save_auth_token, stored_token, stored_user,
                                 unlink_project, verify_token)
from .i18n import t
from .workers import run_async


class GitHubDialog(QDialog):
    """Manage GitHub authentication and bind the active project folder to a repo."""

    link_updated = pyqtSignal(str, str)  # project_path, repo

    def __init__(self, project_path: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("GitHub"))
        self.setMinimumSize(680, 500)
        self.setStyleSheet(LIGHT_QSS)
        self._task_buttons: list[QPushButton] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(12)

        title = QLabel(t("GitHub"))
        title.setStyleSheet("font-size:24px;font-weight:800;color:#0f172a;")
        outer.addWidget(title)

        hint = QLabel(
            t("Đăng nhập bằng token GitHub để eMeX xác minh tài khoản và lưu liên kết repo cho thư mục dự án đang soạn."))
        hint.setWordWrap(True)
        hint.setStyleSheet(
            "color:#475569;background:#f8fafc;border:1px solid #e2e8f0;"
            "border-radius:8px;padding:8px 10px;")
        outer.addWidget(hint)

        outer.addWidget(self._build_auth_group())
        outer.addWidget(self._build_link_group(), 1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        btn_close = QPushButton(t("Đóng"))
        btn_close.setDefault(True)
        btn_close.clicked.connect(self.accept)
        close_row.addWidget(btn_close)
        outer.addLayout(close_row)

        self.project_input.setText(os.path.abspath(project_path) if project_path else "")
        self._refresh_auth_state()
        self._refresh_project_state()

    def _build_auth_group(self) -> QGroupBox:
        group = QGroupBox(t("Đăng nhập GitHub"))
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)

        self.auth_status = QLabel("")
        self.auth_status.setWordWrap(True)
        form.addRow(t("Trạng thái:"), self.auth_status)

        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setPlaceholderText(t("Dán GitHub token"))
        self.token_input.setText(stored_token())
        form.addRow(t("Token:"), self.token_input)

        help_label = QLabel(
            t("Token được lưu cục bộ trong cấu hình eMeX. Tạo token tại <a href='https://github.com/settings/tokens'>github.com/settings/tokens</a>."))
        help_label.setTextFormat(Qt.TextFormat.RichText)
        help_label.setOpenExternalLinks(True)
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color:#64748b;")
        form.addRow("", help_label)

        row = QHBoxLayout()
        self.btn_verify = QPushButton(t("Đăng nhập / kiểm tra"))
        self.btn_verify.clicked.connect(self._verify_token)
        self.btn_cli = QPushButton(t("Dùng token từ GitHub CLI"))
        self.btn_cli.clicked.connect(self._use_cli_token)
        self.btn_logout = QPushButton(t("Đăng xuất"))
        self.btn_logout.clicked.connect(self._logout)
        for button in (self.btn_verify, self.btn_cli, self.btn_logout):
            self._task_buttons.append(button)
            row.addWidget(button)
        row.addStretch()
        form.addRow("", row)
        return group

    def _build_link_group(self) -> QGroupBox:
        group = QGroupBox(t("Liên kết thư mục dự án với repo"))
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)

        project_row = QHBoxLayout()
        self.project_input = QLineEdit()
        self.project_input.setPlaceholderText(t("Chọn thư mục dự án"))
        project_row.addWidget(self.project_input, 1)
        self.btn_browse = QPushButton(t("Chọn..."))
        self.btn_browse.clicked.connect(self._browse_project)
        project_row.addWidget(self.btn_browse)
        form.addRow(t("Thư mục:"), project_row)

        self.repo_combo = QComboBox()
        self.repo_combo.setEditable(True)
        self.repo_combo.lineEdit().setPlaceholderText(
            t("owner/repo hoặc https://github.com/owner/repo"))
        form.addRow(t("Repo:"), self.repo_combo)
        layout.addLayout(form)

        row = QHBoxLayout()
        self.btn_load_repos = QPushButton(t("Tải repo của tôi"))
        self.btn_load_repos.clicked.connect(self._load_repositories)
        self.btn_use_origin = QPushButton(t("Dùng origin hiện có"))
        self.btn_use_origin.clicked.connect(self._use_existing_origin)
        self.btn_link = QPushButton(t("Liên kết repo"))
        self.btn_link.clicked.connect(self._link_repo)
        self.btn_unlink = QPushButton(t("Bỏ liên kết"))
        self.btn_unlink.clicked.connect(self._unlink_repo)
        self.btn_open_repo = QPushButton(t("Mở repo"))
        self.btn_open_repo.clicked.connect(self._open_repo)

        for button in (self.btn_load_repos, self.btn_use_origin, self.btn_link,
                       self.btn_unlink, self.btn_open_repo, self.btn_browse):
            self._task_buttons.append(button)
            row.addWidget(button)
        row.addStretch()
        layout.addLayout(row)

        self.link_status = QLabel("")
        self.link_status.setWordWrap(True)
        self.link_status.setStyleSheet("color:#475569;")
        layout.addWidget(self.link_status)
        return group

    def _set_busy(self, busy: bool, message: str = "") -> None:
        for button in self._task_buttons:
            button.setEnabled(not busy)
        if not busy and hasattr(self, "btn_logout"):
            self._refresh_auth_state()
        if message:
            self.link_status.setText(message)

    def _refresh_auth_state(self) -> None:
        user = stored_user()
        login = user.get("login", "")
        if login:
            display = user.get("name") or login
            self.auth_status.setText(t("Đã đăng nhập: {name} ({login})", name=display, login=login))
            self.auth_status.setStyleSheet("color:#166534;font-weight:600;")
            self.btn_logout.setEnabled(True)
        else:
            self.auth_status.setText(t("Chưa đăng nhập GitHub."))
            self.auth_status.setStyleSheet("color:#92400e;font-weight:600;")
            self.btn_logout.setEnabled(False)

    def _refresh_project_state(self) -> None:
        project_path = self.project_input.text().strip()
        link = get_link_for_project(project_path) if project_path else {}
        if link:
            self._set_repo_text(link.get("repo_url") or link.get("html_url") or link.get("repo", ""))
            self.link_status.setText(
                t("Đang liên kết: {folder} -> {repo}",
                  folder=link.get("project_path", project_path), repo=link.get("repo", "")))
            return

        origin = read_git_origin(project_path) if project_path else ""
        if origin and not self.repo_combo.currentText().strip():
            self._set_repo_text(origin)
            self.link_status.setText(t("Đã phát hiện origin hiện có: {origin}", origin=origin))
        elif project_path:
            self.link_status.setText(t("Chưa liên kết repo cho thư mục này."))
        else:
            self.link_status.setText(t("Chọn thư mục dự án để liên kết repo."))

    def _set_repo_text(self, text: str) -> None:
        if self.repo_combo.findText(text) < 0 and text:
            self.repo_combo.insertItem(0, text)
        self.repo_combo.setEditText(text)

    def _verify_token(self) -> None:
        token = self.token_input.text().strip()
        self._set_busy(True, t("Đang kiểm tra GitHub..."))

        def work():
            user = verify_token(token)
            return token, user

        def done(result):
            token_value, user = result
            save_auth_token(token_value, user)
            self._refresh_auth_state()
            self._set_busy(False, t("Đã đăng nhập GitHub: {login}", login=user.get("login", "")))

        self._run_task(work, done)

    def _use_cli_token(self) -> None:
        self._set_busy(True, t("Đang lấy token từ GitHub CLI..."))

        def work():
            token = github_cli_token()
            user = verify_token(token)
            return token, user

        def done(result):
            token, user = result
            self.token_input.setText(token)
            save_auth_token(token, user)
            self._refresh_auth_state()
            self._set_busy(False, t("Đã đăng nhập GitHub: {login}", login=user.get("login", "")))

        self._run_task(work, done)

    def _logout(self) -> None:
        clear_auth_token()
        self.token_input.clear()
        self._refresh_auth_state()
        self.link_status.setText(t("Đã đăng xuất GitHub khỏi eMeX."))

    def _browse_project(self) -> None:
        start_dir = self.project_input.text().strip()
        if not start_dir or not os.path.isdir(start_dir):
            start_dir = os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(self, t("Chọn thư mục"), start_dir)
        if folder:
            self.project_input.setText(folder)
            self._refresh_project_state()

    def _load_repositories(self) -> None:
        token = self.token_input.text().strip() or stored_token()
        if not token:
            QMessageBox.warning(self, t("Thiếu token"), t("Hãy đăng nhập GitHub trước."))
            return
        self._set_busy(True, t("Đang tải danh sách repo..."))

        def work():
            return list_user_repositories(token)

        def done(repos):
            current = self.repo_combo.currentText().strip()
            self.repo_combo.clear()
            for repo in repos:
                suffix = " (private)" if repo.get("private") else ""
                self.repo_combo.addItem(f"{repo['full_name']}{suffix}", repo.get("clone_url", ""))
            if current:
                self._set_repo_text(current)
            self._set_busy(False, t("Đã tải {count} repo.", count=len(repos)))

        self._run_task(work, done)

    def _use_existing_origin(self) -> None:
        project_path = self.project_input.text().strip()
        origin = read_git_origin(project_path) if project_path else ""
        if not origin:
            QMessageBox.information(self, t("Chưa có origin"), t("Thư mục này chưa có git remote origin."))
            return
        self._set_repo_text(origin)
        self.link_status.setText(t("Đã dùng origin hiện có: {origin}", origin=origin))

    def _selected_repo_value(self) -> str:
        text = self.repo_combo.currentText().replace(" (private)", "").strip()
        data = self.repo_combo.currentData()
        index = self.repo_combo.currentIndex()
        if index >= 0 and text == self.repo_combo.itemText(index).replace(" (private)", "").strip() and isinstance(data, str) and data:
            return data
        return text

    def _link_repo(self) -> None:
        project_path = self.project_input.text().strip()
        repo_value = self._selected_repo_value()
        self._set_busy(True, t("Đang liên kết repo..."))

        def work():
            return link_project_to_repo(project_path, repo_value)

        def done(result):
            self.project_input.setText(result.get("project_path", project_path))
            self._set_repo_text(result.get("repo_url", repo_value))
            self._set_busy(
                False,
                t("Đã liên kết {folder} -> {repo} ({git})",
                  folder=result.get("project_path", project_path),
                  repo=result.get("repo", ""),
                  git=result.get("git_message", "")),
            )
            self.link_updated.emit(result.get("project_path", project_path), result.get("repo", ""))

        self._run_task(work, done)

    def _unlink_repo(self) -> None:
        project_path = self.project_input.text().strip()
        if not project_path:
            return
        if unlink_project(project_path):
            self.link_status.setText(t("Đã bỏ liên kết repo trong eMeX. Git remote origin vẫn được giữ nguyên."))
            self.link_updated.emit(project_path, "")
        else:
            self.link_status.setText(t("Không tìm thấy liên kết repo để xoá."))

    def _open_repo(self) -> None:
        try:
            repo = normalize_repo_reference(self._selected_repo_value())
            QDesktopServices.openUrl(QUrl(repo.html_url))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, t("Không mở được repo"), str(exc))

    def _run_task(self, work, on_done) -> None:
        def done(result):
            on_done(result)

        def error(message):
            self._set_busy(False, message)
            QMessageBox.critical(self, t("GitHub"), message)

        run_async(self, work, on_done=done, on_error=error)
