# -*- mode: python ; coding: utf-8 -*-

import os
import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


ROOT = Path(os.path.abspath(SPECPATH))
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

block_cipher = None


def _append_file_if_exists(items: list[tuple[str, str]], source: Path, destination: str) -> None:
    if source.exists():
        items.append((str(source), destination))


def _read_app_version() -> str:
    config_py = ROOT / "src" / "config.py"
    if not config_py.exists():
        return "0.0.0"
    match = re.search(
        r'APP_VERSION\s*=\s*["\']([^"\']+)["\']',
        config_py.read_text(encoding="utf-8"),
    )
    return match.group(1) if match else "0.0.0"


pathex = [str(ROOT)]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

hiddenimports = (
    [
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "PyQt6.QtNetwork",
        "PyQt6.QtPositioning",
        "PyQt6.QtPrintSupport",
        "PyQt6.QtQml",
        "PyQt6.QtQuick",
        "PyQt6.QtWebChannel",
        "PyQt6.QtWebEngineCore",
        "PyQt6.QtWebEngineQuick",
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.sip",
        "certifi",
        "requests",
        "urllib3",
        "idna",
        "charset_normalizer",
    ]
    + collect_submodules("markdown")
    + collect_submodules("docx")
    + collect_submodules("lxml")
    + collect_submodules("src")
)

EXCLUDES = [
    "tkinter",
    "IPython",
    "notebook",
    "matplotlib",
    "pandas",
    "numpy.tests",
    "test",
    "unittest",
    "pydoc_data",
    "lib2to3",
    "PyQt6.QtBluetooth",
    "PyQt6.QtDBus",
    "PyQt6.QtDesigner",
    "PyQt6.QtHelp",
    "PyQt6.QtLocation",
    "PyQt6.QtMultimedia",
    "PyQt6.QtMultimediaWidgets",
    "PyQt6.QtNetworkAuth",
    "PyQt6.QtNfc",
    "PyQt6.QtOpenGL",
    "PyQt6.QtOpenGLWidgets",
    "PyQt6.QtPdf",
    "PyQt6.QtPdfWidgets",
    "PyQt6.QtQuick3D",
    "PyQt6.QtQuickWidgets",
    "PyQt6.QtRemoteObjects",
    "PyQt6.QtScxml",
    "PyQt6.QtSensors",
    "PyQt6.QtSerialPort",
    "PyQt6.QtSpatialAudio",
    "PyQt6.QtSql",
    "PyQt6.QtSvg",
    "PyQt6.QtSvgWidgets",
    "PyQt6.QtTest",
    "PyQt6.QtTextToSpeech",
    "PyQt6.QtWebSockets",
    "PyQt6.QtWebView",
    "PyQt6.QtXml",
    "PyQt6.Qt3DCore",
    "PyQt6.Qt3DRender",
    "PyQt6.Qt3DInput",
    "PyQt6.Qt3DLogic",
    "PyQt6.Qt3DAnimation",
    "PyQt6.Qt3DExtras",
    "PyQt6.QtCharts",
    "PyQt6.QtDataVisualization",
]


datas = []
datas += collect_data_files("certifi")
for asset_name in ("icon_eMeX.png", "icon_eMeX_256.png", "icon_eMeX.ico", "icon_eMeX.icns"):
    _append_file_if_exists(datas, ROOT / "docs" / "assets" / asset_name, "docs/assets")

bundle_icon = None
if IS_WIN:
    icon_ico = ROOT / "docs" / "assets" / "icon_eMeX.ico"
    if not icon_ico.exists():
        raise FileNotFoundError(f"Windows build requires executable icon: {icon_ico}")
    bundle_icon = str(icon_ico)
elif IS_MAC:
    icon_icns = ROOT / "docs" / "assets" / "icon_eMeX.icns"
    if not icon_icns.exists():
        raise FileNotFoundError(f"macOS build requires bundle icon: {icon_icns}")
    bundle_icon = str(icon_icns)

a = Analysis(
    [str(ROOT / "eMeX.py")],
    pathex=pathex,
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)


def _drop_unused_qt_binaries(items):
    blocked = (
        "Qt6WebView",
        "Qt6Multimedia",
        "Qt6Bluetooth",
        "Qt6Pdf",
        "Qt6Sensors",
        "Qt6Charts",
        "Qt63D",
        "Qt6Designer",
        "Qt6Help",
        "Qt6Test",
        "Qt6Location",
        "Qt6SerialPort",
        "Qt6Sql",
        "Qt6Svg",
    )
    out = []
    for entry in items:
        path = entry[0] if isinstance(entry, tuple) else entry
        name = os.path.basename(str(path))
        if any(part.lower() in name.lower() for part in blocked):
            continue
        out.append(entry)
    return out


a.binaries = _drop_unused_qt_binaries(a.binaries)
a.datas = _drop_unused_qt_binaries(a.datas)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="eMeX",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=bundle_icon,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if IS_MAC:
    app = BUNDLE(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        name="eMeX.app",
        icon=bundle_icon,
        bundle_identifier="io.github.nhhai_math.emex",
        info_plist={
            "CFBundleName": "eMeX",
            "CFBundleDisplayName": "eMeX",
            "CFBundleVersion": _read_app_version(),
            "CFBundleShortVersionString": _read_app_version(),
            "NSHighResolutionCapable": True,
        },
    )
else:
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name="eMeX",
    )
