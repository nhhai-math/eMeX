"""GitHub sidebar panel for linking an eMeX project folder to a repository."""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QInputDialog,
                              QLabel, QLineEdit, QListWidget, QListWidgetItem,
                              QMessageBox, QPushButton, QTabWidget,
                              QVBoxLayout, QWidget)

from .github_integration import (clear_auth_token, get_link_for_project,
                                 github_cli_token, link_project_to_repo,
                                 list_user_repositories,
                                 normalize_repo_reference, read_git_origin,
                                 save_auth_token, stored_token, stored_user,
                                 unlink_project, verify_token)
from .i18n import t
from .workers import run_async


def _small_button(text: str, tooltip: str = "") -> QPushButton:
    btn = QPushButton(text)
    btn.setToolTip(tooltip)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


class GitHubPanel(QWidget):
    """eTeX-inspired sidebar panel backed by the existing eMeX GitHub helpers."""

    link_updated = pyqtSignal(str, str)

    def __init__(self, main_window):
        super().__init__(main_window)
        self.win = main_window
        self._task_buttons: list[QPushButton] = []
        self._build_ui()
        self.refresh_context(load_remote=False)

    def _build_ui(self):
        self.setObjectName("githubPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        icon = QLabel("GH")
        icon.setStyleSheet("font-weight:800;color:#475569;font-size:14px;")
        header.addWidget(icon)
        title = QLabel("GitHub")
        title.setStyleSheet("font-weight:700;color:#0f172a;font-size:15px;")
        header.addWidget(title)
        header.addStretch()

        self.btn_refresh = _small_button("↻", t("Làm mới bảng GitHub"))
        self.btn_refresh.setFixedSize(30, 28)
        self.btn_refresh.clicked.connect(lambda: self.refresh_context(load_remote=True))
        header.addWidget(self.btn_refresh)

        self.btn_cli = _small_button("CLI", t("Dùng token từ GitHub CLI"))
        self.btn_cli.setFixedSize(44, 28)
        self.btn_cli.clicked.connect(self._use_cli_token)
        header.addWidget(self.btn_cli)

        self.btn_token = _small_button("🔑", t("Nhập/lưu mã truy cập GitHub"))
        self.btn_token.setFixedSize(34, 28)
        self.btn_token.clicked.connect(self._show_token_dialog)
        header.addWidget(self.btn_token)
        layout.addLayout(header)

        self.lbl_auth = QLabel("")
        self.lbl_folder = QLabel("")
        self.lbl_repo = QLabel("")
        for label in (self.lbl_auth, self.lbl_folder, self.lbl_repo):
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            label.setStyleSheet("color:#64748b;font-size:12px;")
            layout.addWidget(label)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        layout.addWidget(self.tabs, 1)

        self._build_repositories_tab()
        self._build_link_tab()

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("color:#64748b;font-size:12px;")
        layout.addWidget(self.lbl_status)

        self._task_buttons.extend([
            self.btn_refresh, self.btn_cli, self.btn_token, self.btn_load_repos,
            self.btn_open_repo, self.btn_link_selected, self.btn_browse,
            self.btn_use_origin, self.btn_link, self.btn_unlink,
            self.btn_open_linked_repo,
        ])

    def _build_repositories_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(6, 8, 6, 6)
        lay.setSpacing(8)

        self.repo_list = QListWidget()
        self.repo_list.itemDoubleClicked.connect(self._open_repo_item)
        self.repo_list.currentItemChanged.connect(lambda _cur, _prev: self._sync_selected_repo())
        lay.addWidget(self.repo_list, 1)

        row = QHBoxLayout()
        self.btn_load_repos = QPushButton(t("Tải repo của tôi"))
        self.btn_load_repos.clicked.connect(self._load_repositories)
        row.addWidget(self.btn_load_repos)

        self.btn_open_repo = QPushButton(t("Mở repo"))
        self.btn_open_repo.clicked.connect(self._open_selected_repo)
        row.addWidget(self.btn_open_repo)
        lay.addLayout(row)

        self.btn_link_selected = QPushButton(t("Liên kết thư mục hiện tại"))
        self.btn_link_selected.clicked.connect(self._link_selected_repo_to_current_folder)
        lay.addWidget(self.btn_link_selected)

        self.tabs.addTab(tab, t("Kho"))

    def _build_link_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(6, 8, 6, 6)
        lay.setSpacing(8)

        self.project_input = QLineEdit()
        self.project_input.setPlaceholderText(t("Chọn thư mục dự án"))
        lay.addWidget(self.project_input)

        project_row = QHBoxLayout()
        self.btn_browse = QPushButton(t("Chọn..."))
        self.btn_browse.clicked.connect(self._browse_project)
        project_row.addWidget(self.btn_browse)
        self.btn_use_origin = QPushButton(t("Dùng origin hiện có"))
        self.btn_use_origin.clicked.connect(self._use_existing_origin)
        project_row.addWidget(self.btn_use_origin)
        lay.addLayout(project_row)

        self.repo_combo = QComboBox()
        self.repo_combo.setEditable(True)
        self.repo_combo.lineEdit().setPlaceholderText(
            t("owner/repo hoặc https://github.com/owner/repo"))
        lay.addWidget(self.repo_combo)

        action_row = QHBoxLayout()
        self.btn_link = QPushButton(t("Liên kết repo"))
        self.btn_link.clicked.connect(self._link_repo)
        action_row.addWidget(self.btn_link)

        self.btn_unlink = QPushButton(t("Bỏ liên kết"))
        self.btn_unlink.clicked.connect(self._unlink_repo)
        action_row.addWidget(self.btn_unlink)
        lay.addLayout(action_row)

        self.btn_open_linked_repo = QPushButton(t("Mở repo"))
        self.btn_open_linked_repo.clicked.connect(self._open_linked_repo)
        lay.addWidget(self.btn_open_linked_repo)
        lay.addStretch()

        self.tabs.addTab(tab, t("Liên kết"))

    def refresh_context(self, load_remote: bool = False):
        project_path = self._current_project_folder()
        if project_path:
            self.project_input.setText(project_path)
        self._refresh_auth_state()
        self._refresh_project_state()
        if load_remote:
            self._load_repositories()

    def _current_project_folder(self) -> str:
        current = self.project_input.text().strip()
        if current and os.path.isdir(current):
            return os.path.abspath(current)
        if hasattr(self.win, "_current_project_folder"):
            folder = self.win._current_project_folder()
            if folder and os.path.isdir(folder):
                return os.path.abspath(folder)
        return ""

    def _refresh_auth_state(self):
        user = stored_user()
        login = user.get("login", "")
        if login:
            display = user.get("name") or login
            self.lbl_auth.setText(t("GitHub: {name} ({login})", name=display, login=login))
            self.lbl_auth.setStyleSheet("color:#166534;font-size:12px;font-weight:600;")
        else:
            self.lbl_auth.setText(t("Mã truy cập: chưa cấu hình"))
            self.lbl_auth.setStyleSheet("color:#92400e;font-size:12px;font-weight:600;")

    def _refresh_project_state(self):
        project_path = self.project_input.text().strip()
        self.lbl_folder.setText(t("Thư mục: {folder}", folder=project_path or "-"))
        link = get_link_for_project(project_path) if project_path else {}
        if link:
            self._set_repo_text(link.get("repo_url") or link.get("html_url") or link.get("repo", ""))
            self.lbl_repo.setText(t("Đang liên kết: {folder} -> {repo}",
                                    folder=link.get("project_path", project_path),
                                    repo=link.get("repo", "")))
            return
        origin = read_git_origin(project_path) if project_path else ""
        if origin and not self.repo_combo.currentText().strip():
            self._set_repo_text(origin)
            self.lbl_repo.setText(t("Đã phát hiện origin hiện có: {origin}", origin=origin))
        elif project_path:
            self.lbl_repo.setText(t("Chưa liên kết repo cho thư mục này."))
        else:
            self.lbl_repo.setText(t("Chọn thư mục dự án để liên kết repo."))

    def _set_repo_text(self, text: str):
        if text and self.repo_combo.findText(text) < 0:
            self.repo_combo.insertItem(0, text)
        self.repo_combo.setEditText(text)

    def _sync_selected_repo(self):
        item = self.repo_list.currentItem()
        if not item:
            return
        repo_value = item.data(Qt.ItemDataRole.UserRole) or item.text().split()[0]
        self._set_repo_text(repo_value)

    def _show_token_dialog(self):
        token, ok = QInputDialog.getText(
            self,
            t("Mã truy cập GitHub"),
            t("Mã truy cập GitHub:"),
            QLineEdit.EchoMode.Password,
            stored_token(),
        )
        token = token.strip()
        if not ok:
            return
        if not token:
            clear_auth_token()
            self._refresh_auth_state()
            self.lbl_status.setText(t("Đã đăng xuất GitHub khỏi eMeX."))
            return
        self._verify_and_save_token(token)

    def _use_cli_token(self):
        self._set_busy(True, t("Đang lấy token từ GitHub CLI..."))

        def work():
            token = github_cli_token()
            return token, verify_token(token)

        def done(result):
            token, user = result
            save_auth_token(token, user)
            self._set_busy(False, t("Đã đăng nhập GitHub: {login}", login=user.get("login", "")))
            self._refresh_auth_state()
            self._load_repositories()

        self._run_task(work, done)

    def _verify_and_save_token(self, token: str):
        self._set_busy(True, t("Đang kiểm tra GitHub..."))

        def work():
            return verify_token(token)

        def done(user):
            save_auth_token(token, user)
            self._set_busy(False, t("Đã đăng nhập GitHub: {login}", login=user.get("login", "")))
            self._refresh_auth_state()
            self._load_repositories()

        self._run_task(work, done)

    def _load_repositories(self):
        token = stored_token()
        if not token:
            QMessageBox.warning(self, t("Thiếu token"), t("Hãy đăng nhập GitHub trước."))
            return
        self._set_busy(True, t("Đang tải danh sách repo..."))

        def work():
            return list_user_repositories(token)

        def done(repos):
            self.repo_list.clear()
            current = self.repo_combo.currentText().strip()
            self.repo_combo.clear()
            for repo in repos:
                label = repo["full_name"] + ("  · private" if repo.get("private") else "")
                item = QListWidgetItem(label)
                item.setToolTip(repo.get("html_url", repo["full_name"]))
                item.setData(Qt.ItemDataRole.UserRole, repo.get("clone_url") or repo["full_name"])
                item.setData(Qt.ItemDataRole.UserRole + 1, repo.get("html_url", ""))
                self.repo_list.addItem(item)
                self.repo_combo.addItem(label, repo.get("clone_url") or repo["full_name"])
            if current:
                self._set_repo_text(current)
            self._set_busy(False, t("Đã tải {count} repo.", count=len(repos)))

        self._run_task(work, done)

    def _browse_project(self):
        start_dir = self.project_input.text().strip()
        if not start_dir or not os.path.isdir(start_dir):
            start_dir = os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(self, t("Chọn thư mục"), start_dir)
        if not folder:
            return
        self.project_input.setText(os.path.abspath(folder))
        if hasattr(self.win, "_show_folder_tree"):
            self.win._show_folder_tree(folder)
        self._refresh_project_state()

    def _use_existing_origin(self):
        project_path = self.project_input.text().strip()
        origin = read_git_origin(project_path) if project_path else ""
        if not origin:
            QMessageBox.information(self, t("Chưa có origin"), t("Thư mục này chưa có git remote origin."))
            return
        self._set_repo_text(origin)
        self.lbl_status.setText(t("Đã dùng origin hiện có: {origin}", origin=origin))

    def _selected_repo_value(self) -> str:
        item = self.repo_list.currentItem()
        if item and self.tabs.currentIndex() == 0:
            value = item.data(Qt.ItemDataRole.UserRole)
            if value:
                return str(value)
        text = self.repo_combo.currentText().replace("  · private", "").replace(" (private)", "").strip()
        data = self.repo_combo.currentData()
        index = self.repo_combo.currentIndex()
        if (index >= 0
                and text == self.repo_combo.itemText(index).replace("  · private", "").replace(" (private)", "").strip()
                and isinstance(data, str) and data):
            return data
        return text

    def _link_selected_repo_to_current_folder(self):
        self.tabs.setCurrentIndex(0)
        if not self.repo_list.currentItem():
            QMessageBox.information(self, t("GitHub"), t("Hãy chọn repo để liên kết."))
            return
        self._link_repo()

    def _link_repo(self):
        project_path = self.project_input.text().strip() or self._current_project_folder()
        repo_value = self._selected_repo_value()
        self._set_busy(True, t("Đang liên kết repo..."))

        def work():
            return link_project_to_repo(project_path, repo_value)

        def done(result):
            self.project_input.setText(result.get("project_path", project_path))
            self._set_repo_text(result.get("repo_url", repo_value))
            message = t("Đã liên kết {folder} -> {repo} ({git})",
                        folder=result.get("project_path", project_path),
                        repo=result.get("repo", ""),
                        git=result.get("git_message", ""))
            self._set_busy(False, message)
            self._refresh_project_state()
            self.link_updated.emit(result.get("project_path", project_path), result.get("repo", ""))
            if hasattr(self.win, "_show_folder_tree"):
                self.win._show_folder_tree(result.get("project_path", project_path))

        self._run_task(work, done)

    def _unlink_repo(self):
        project_path = self.project_input.text().strip()
        if not project_path:
            return
        if unlink_project(project_path):
            self.lbl_status.setText(t("Đã bỏ liên kết repo trong eMeX. Git remote origin vẫn được giữ nguyên."))
            self._refresh_project_state()
            self.link_updated.emit(project_path, "")
        else:
            self.lbl_status.setText(t("Không tìm thấy liên kết repo để xoá."))

    def _open_repo_item(self, item: QListWidgetItem):
        url = item.data(Qt.ItemDataRole.UserRole + 1)
        if url:
            QDesktopServices.openUrl(QUrl(str(url)))

    def _open_selected_repo(self):
        item = self.repo_list.currentItem()
        if item:
            self._open_repo_item(item)
            return
        self._open_linked_repo()

    def _open_linked_repo(self):
        try:
            repo = normalize_repo_reference(self._selected_repo_value())
            QDesktopServices.openUrl(QUrl(repo.html_url))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, t("Không mở được repo"), str(exc))

    def _set_busy(self, busy: bool, message: str = ""):
        for button in self._task_buttons:
            button.setEnabled(not busy)
        if message:
            self.lbl_status.setText(message)

    def _run_task(self, work, on_done):
        def done(result):
            on_done(result)

        def error(message):
            self._set_busy(False, message)
            QMessageBox.critical(self, t("GitHub"), message)

        run_async(self, work, on_done=done, on_error=error)
