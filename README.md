# eMeX

eMeX is a lightweight Markdown editor for math documents. It includes live MathJax/TikZ preview, export tools, and a Gemini-powered AI chat panel for drafting and editing.

## Run from source

```bash
python -m pip install -r requirements.txt
python eMeX.py
```

## Build desktop packages

Install build tools, generate platform icons, then run PyInstaller:

```bash
python -m pip install -r requirements.txt pyinstaller pillow certifi
python scripts/prepare_icons.py
pyinstaller build.spec --noconfirm --clean
```

The GitHub Actions workflow builds Windows, macOS Intel, macOS Apple Silicon, and Linux packages on pushes to `main`, tags beginning with `v`, or manual dispatch.
