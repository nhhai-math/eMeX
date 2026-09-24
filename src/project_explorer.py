"""Project folder tree used by the eMeX left sidebar."""
from __future__ import annotations

import os
import shutil
import subprocess

from PyQt6.QtCore import QDir, QItemSelectionModel, QModelIndex, QSize, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFileSystemModel
from PyQt6.QtWidgets import (QFileDialog, QHBoxLayout, QInputDialog, QLabel,
                              QMenu, QMessageBox, QPushButton, QTreeView,
                              QVBoxLayout, QWidget)

from .i18n import t


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp", ".bmp", ".pdf"}
OPENABLE_EXTENSIONS = {".md", ".markdown", ".mdown", ".txt"}


def _button(text: str, tooltip: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setToolTip(tooltip)
    btn.setFixedSize(30, 28)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def _git_root(path: str) -> str:
    if not path or not shutil.which("git"):
        return ""
    start = path if os.path.isdir(path) else os.path.dirname(path)
    if not start or not os.path.isdir(start):
        return ""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return ""
    if result.returncode == 0 and result.stdout.strip():
        return os.path.abspath(result.stdout.strip())
    return ""


class ProjectExplorer(QWidget):
    """Compact project tree with eTeX-like project actions."""

    file_open_requested = pyqtSignal(str)
    root_changed = pyqtSignal(str)
    github_requested = pyqtSignal()
    path_renamed = pyqtSignal(str, str)
    path_deleted = pyqtSignal(str)
    image_renamed = pyqtSignal(str, str)

    def __init__(self, parent=None, editor_config: dict | None = None):
        super().__init__(parent)
        self._config = editor_config or {}
        self._root_path = ""

        self.setObjectName("projectExplorer")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        self.icon = QLabel("▣")
        self.icon.setStyleSheet("font-size:18px;color:#475569;font-weight:700;")
        header.addWidget(self.icon)

        self.title = QLabel(t("Dự án"))
        self.title.setStyleSheet("font-weight:700;color:#0f172a;font-size:15px;")
        header.addWidget(self.title)
        header.addStretch()

        self.btn_open = _button("…", t("Mở thư mục"))
        self.btn_open.clicked.connect(self.browse_folder)
        header.addWidget(self.btn_open)

        self.btn_refresh = _button("↻", t("Làm mới cây thư mục"))
        self.btn_refresh.clicked.connect(self.refresh)
        header.addWidget(self.btn_refresh)

        self.btn_github = _button("GH", t("GitHub: đăng nhập và liên kết repo"))
        self.btn_github.clicked.connect(self.github_requested.emit)
        header.addWidget(self.btn_github)
        layout.addLayout(header)

        self.lbl_root = QLabel(t("Chưa có dự án"))
        self.lbl_root.setStyleSheet("font-weight:600;color:#0f172a;")
        layout.addWidget(self.lbl_root)

        self.lbl_path = QLabel(t("Mở thư mục hoặc lưu một tệp Markdown để hiện cây thư mục."))
        self.lbl_path.setWordWrap(True)
        self.lbl_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.lbl_path.setStyleSheet("color:#64748b;font-size:12px;")
        layout.addWidget(self.lbl_path)

        self.model = QFileSystemModel(self)
        self.model.setFilter(
            QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot
        )
        self.model.setNameFilterDisables(False)

        self.tree = QTreeView()
        self.tree.setObjectName("projectTree")
        self.tree.setModel(self.model)
        self.tree.setHeaderHidden(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(16)
        self.tree.setUniformRowHeights(True)
        self.tree.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.tree.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        self.tree.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.doubleClicked.connect(self._on_double_clicked)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        for column in range(1, self.model.columnCount()):
            self.tree.hideColumn(column)
        layout.addWidget(self.tree, 1)

        self.apply_config(self._config)
        self._set_empty()

    @property
    def root_path(self) -> str:
        return self._root_path

    def apply_config(self, config: dict):
        self._config = config or {}
        try:
            icon_size = int(self._config.get("toolbar_icon_size", 22))
        except (TypeError, ValueError):
            icon_size = 22
        icon_size = max(14, min(34, icon_size))
        for btn in (self.btn_open, self.btn_refresh, self.btn_github):
            btn.setIconSize(QSize(icon_size, icon_size))

    def retranslate_ui(self):
        self.title.setText(t("Dự án"))
        self.btn_open.setToolTip(t("Mở thư mục"))
        self.btn_refresh.setToolTip(t("Làm mới cây thư mục"))
        self.btn_github.setToolTip(t("GitHub: đăng nhập và liên kết repo"))
        if not self._root_path:
            self.lbl_root.setText(t("Chưa có dự án"))
            self.lbl_path.setText(t("Mở thư mục hoặc lưu một tệp Markdown để hiện cây thư mục."))

    def set_context(self, file_path: str = "", fallback_root: str = ""):
        root = self._resolve_project_root(file_path)
        if not root and fallback_root and os.path.isdir(fallback_root):
            root = fallback_root
        if root:
            self.set_root(root)
        elif not self._root_path:
            self._set_empty()

    def set_root(self, root_path: str):
        root = os.path.abspath(root_path)
        if not os.path.isdir(root):
            self._set_empty()
            return
        if root == self._root_path:
            return
        self._root_path = root
        index = self.model.setRootPath(root)
        self.tree.setRootIndex(index)
        self.tree.expand(index)
        self.lbl_root.setText(os.path.basename(root) or root)
        self.lbl_path.setText(root)
        self.lbl_path.setToolTip(root)
        self.btn_refresh.setEnabled(True)
        self.btn_github.setEnabled(True)
        self.root_changed.emit(root)

    def browse_folder(self, start_dir: str = ""):
        start = start_dir if isinstance(start_dir, str) else ""
        if not start or not os.path.isdir(start):
            start = self._root_path if os.path.isdir(self._root_path) else os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(self, t("Chọn thư mục"), start)
        if folder:
            self.set_root(folder)

    def refresh(self):
        if not self._root_path:
            return
        index = self.model.setRootPath("")
        self.tree.setRootIndex(index)
        index = self.model.setRootPath(self._root_path)
        self.tree.setRootIndex(index)
        self.tree.expand(index)

    def _set_empty(self):
        self._root_path = ""
        self.lbl_root.setText(t("Chưa có dự án"))
        self.lbl_path.setText(t("Mở thư mục hoặc lưu một tệp Markdown để hiện cây thư mục."))
        self.tree.setRootIndex(QModelIndex())
        self.btn_refresh.setEnabled(False)
        self.btn_github.setEnabled(False)

    def _resolve_project_root(self, file_path: str) -> str:
        if not file_path:
            return ""
        abs_path = os.path.abspath(file_path)
        if not os.path.exists(abs_path):
            return ""
        root = _git_root(abs_path)
        if root:
            return root
        return os.path.dirname(abs_path) if os.path.isfile(abs_path) else abs_path

    def _on_double_clicked(self, index: QModelIndex):
        path = self.model.filePath(index)
        if not path:
            return
        if os.path.isdir(path):
            self.tree.setExpanded(index, not self.tree.isExpanded(index))
            return
        self._open_path(path)

    def _open_path(self, path: str):
        if os.path.splitext(path)[1].lower() in OPENABLE_EXTENSIONS:
            self.file_open_requested.emit(path)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _show_context_menu(self, pos):
        if not self._root_path:
            return
        index = self.tree.indexAt(pos)
        if index.isValid() and not self.tree.selectionModel().isSelected(index):
            self.tree.selectionModel().select(
                index,
                QItemSelectionModel.SelectionFlag.ClearAndSelect
                | QItemSelectionModel.SelectionFlag.Rows,
            )
            self.tree.setCurrentIndex(index)

        path = self.model.filePath(index) if index.isValid() else self._root_path
        if not path:
            path = self._root_path
        selected_paths = self._selected_paths()
        selected_count = len(selected_paths)
        target_dir = path if os.path.isdir(path) else os.path.dirname(path)

        menu = QMenu(self)
        act_new_folder = menu.addAction(t("Tạo thư mục mới"))
        act_new_file = menu.addAction(t("Tạo tệp mới"))
        act_add_image = menu.addAction(t("Thêm ảnh..."))

        act_open = act_reveal = act_rename = act_delete = None
        if index.isValid():
            menu.addSeparator()
            if selected_count == 1:
                act_open = menu.addAction(t("Mở"))
                act_reveal = menu.addAction(t("Mở thư mục chứa"))
                act_rename = menu.addAction(t("Đổi tên"))
            delete_label = (t("Xóa") if selected_count <= 1
                            else t("Xóa {count} mục", count=selected_count))
            act_delete = menu.addAction(delete_label)

        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen == act_new_folder:
            self._create_folder(target_dir)
        elif chosen == act_new_file:
            self._create_file(target_dir)
        elif chosen == act_add_image:
            self._add_images(target_dir)
        elif chosen == act_open:
            self._open_path(path)
        elif chosen == act_reveal:
            QDesktopServices.openUrl(QUrl.fromLocalFile(target_dir))
        elif chosen == act_rename:
            self._rename_path(path)
        elif chosen == act_delete:
            self._delete_paths(selected_paths or [path])

    def _create_folder(self, parent_dir: str):
        name, ok = QInputDialog.getText(self, t("Tạo thư mục mới"), t("Tên thư mục:"))
        name = name.strip()
        if not ok or not name:
            return
        path = os.path.join(parent_dir, name)
        if not self._is_safe_project_path(path):
            self._warn(t("Tên thư mục không hợp lệ."))
            return
        if os.path.exists(path):
            self._warn(t("Thư mục hoặc tệp đã tồn tại."))
            return
        try:
            os.makedirs(path)
            self.refresh()
        except OSError as exc:
            self._warn(t("Không tạo được thư mục: {error}", error=exc))

    def _create_file(self, parent_dir: str):
        name, ok = QInputDialog.getText(self, t("Tạo tệp mới"), t("Tên tệp:"), text="new.md")
        name = name.strip()
        if not ok or not name:
            return
        path = os.path.join(parent_dir, name)
        if not self._is_safe_project_path(path):
            self._warn(t("Tên tệp không hợp lệ."))
            return
        if os.path.exists(path):
            self._warn(t("Thư mục hoặc tệp đã tồn tại."))
            return
        try:
            with open(path, "x", encoding="utf-8"):
                pass
            self.refresh()
            self.file_open_requested.emit(path)
        except OSError as exc:
            self._warn(t("Không tạo được tệp: {error}", error=exc))

    def _add_images(self, parent_dir: str):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            t("Thêm ảnh vào dự án"),
            "",
            t("Hình ảnh (*.png *.jpg *.jpeg *.svg *.gif *.webp *.bmp *.pdf);;Tất cả (*)"),
        )
        if not paths:
            return
        copied = 0
        for src in paths:
            dest = os.path.join(parent_dir, os.path.basename(src))
            if not self._is_safe_project_path(dest):
                continue
            if os.path.exists(dest):
                answer = QMessageBox.question(
                    self,
                    t("Ghi đè ảnh?"),
                    t("{name} đã tồn tại. Ghi đè?", name=os.path.basename(dest)),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    continue
            try:
                shutil.copy2(src, dest)
                copied += 1
            except OSError as exc:
                self._warn(t("Không thêm được ảnh {name}: {error}",
                             name=os.path.basename(src), error=exc))
        if copied:
            self.refresh()

    def _rename_path(self, path: str):
        if not self._is_safe_project_path(path):
            return
        old_name = os.path.basename(path)
        new_name, ok = QInputDialog.getText(self, t("Đổi tên"), t("Tên mới:"), text=old_name)
        new_name = new_name.strip()
        if not ok or not new_name or new_name == old_name:
            return
        new_path = os.path.join(os.path.dirname(path), new_name)
        if not self._is_safe_project_path(new_path):
            self._warn(t("Tên mới không hợp lệ."))
            return
        if os.path.exists(new_path):
            self._warn(t("Đã có thư mục hoặc tệp cùng tên."))
            return
        try:
            os.rename(path, new_path)
        except OSError as exc:
            self._warn(t("Không đổi tên được: {error}", error=exc))
            return
        self.path_renamed.emit(path, new_path)
        if self._is_image_path(path) or self._is_image_path(new_path):
            self.image_renamed.emit(path, new_path)
        self.refresh()

    def _delete_paths(self, paths: list[str]):
        targets = self._normalized_delete_targets(paths)
        if not targets:
            return
        if len(targets) == 1:
            kind = t("thư mục") if os.path.isdir(targets[0]) else t("tệp")
            message = t("Xóa {kind} '{name}' khỏi dự án?",
                        kind=kind, name=os.path.basename(targets[0]))
            title = t("Xóa {kind}?", kind=kind)
        else:
            message = t("Xóa {count} mục đã chọn khỏi dự án?", count=len(targets))
            title = t("Xóa nhiều mục?")
        answer = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        deleted: list[str] = []
        for path in targets:
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                deleted.append(path)
            except OSError as exc:
                self._warn(t("Không xóa được {name}: {error}",
                             name=os.path.basename(path), error=exc))
        for path in deleted:
            self.path_deleted.emit(path)
        self.refresh()

    def _selected_paths(self) -> list[str]:
        rows = self.tree.selectionModel().selectedRows(0)
        paths: list[str] = []
        seen = set()
        for index in rows:
            path = self.model.filePath(index)
            if path and self._is_safe_project_path(path):
                abs_path = os.path.abspath(path)
                if abs_path not in seen:
                    paths.append(abs_path)
                    seen.add(abs_path)
        return paths

    def _normalized_delete_targets(self, paths: list[str]) -> list[str]:
        safe_paths = []
        for path in paths:
            if path and self._is_safe_project_path(path) and os.path.exists(path):
                safe_paths.append(os.path.abspath(path))
        unique = sorted(set(safe_paths), key=lambda item: item.count(os.sep))
        result: list[str] = []
        for path in unique:
            if any(path.startswith(parent + os.sep) for parent in result):
                continue
            result.append(path)
        return result

    def _is_image_path(self, path: str) -> bool:
        return os.path.splitext(path)[1].lower() in IMAGE_EXTENSIONS

    def _is_safe_project_path(self, path: str) -> bool:
        if not self._root_path:
            return False
        root = os.path.abspath(self._root_path)
        candidate = os.path.abspath(path)
        try:
            return os.path.commonpath([root, candidate]) == root
        except ValueError:
            return False

    def _warn(self, message: str):
        QMessageBox.warning(self, t("Dự án"), message)
