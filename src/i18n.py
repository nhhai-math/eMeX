"""Runtime translation helper for eMeX UI labels.

The Vietnamese text is the source language. English is provided through a
small dictionary, matching the approach used by eDraw.
"""
from __future__ import annotations

from .config import DEFAULT_EDITOR_CONFIG, load_editor_config, save_editor_config

DEFAULT_LANGUAGE = "vi"
SUPPORTED_LANGUAGES = ("vi", "en")
_current_language: str | None = None


def normalize_language(language: str | None) -> str:
    value = (language or "").strip().lower()
    return value if value in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def current_language() -> str:
    global _current_language
    if _current_language is None:
        _current_language = normalize_language(load_editor_config().get("language"))
    return _current_language


def set_language(language: str) -> str:
    global _current_language
    _current_language = normalize_language(language)
    cfg = load_editor_config()
    cfg["language"] = _current_language
    save_editor_config(cfg)
    return _current_language


def supported_languages() -> tuple[str, ...]:
    return SUPPORTED_LANGUAGES


def language_name(language: str) -> str:
    code = normalize_language(language)
    if current_language() == "en":
        return {"vi": "Vietnamese", "en": "English"}.get(code, code)
    return {"vi": "Tiếng Việt", "en": "Tiếng Anh"}.get(code, code)


def reset_language() -> str:
    return set_language(DEFAULT_EDITOR_CONFIG.get("language", DEFAULT_LANGUAGE))


def t(text: str, **kwargs) -> str:
    value = _EN.get(text, text) if current_language() == "en" else text
    if kwargs:
        return value.format(**kwargs)
    return value


_EN: dict[str, str] = {
    "Ngôn ngữ:": "Language:",
    "Tiếng Việt": "Vietnamese",
    "Tiếng Anh": "English",
    "Sẵn sàng": "Ready",
    "Dòng {line}, Cột {col}": "Line {line}, Column {col}",
    "{words} từ · {chars} ký tự": "{words} words · {chars} chars",
    "Tìm...": "Find...",
    "Thay bằng...": "Replace with...",
    "Tìm:": "Find:",
    "Thay:": "Replace:",
    "Thay": "Replace",
    "Thay tất cả": "Replace all",
    "Trang trống (Ctrl+N)": "Blank page (Ctrl+N)",
    "Mở (Ctrl+O)": "Open (Ctrl+O)",
    "Lưu (Ctrl+S)": "Save (Ctrl+S)",
    "Lưu thành... (Ctrl+Shift+S)": "Save as... (Ctrl+Shift+S)",
    "In đậm (Ctrl+B)": "Bold (Ctrl+B)",
    "In nghiêng (Ctrl+I)": "Italic (Ctrl+I)",
    "Gạch ngang": "Strikethrough",
    "Mã trong dòng": "Inline code",
    "Toán trong dòng (Ctrl+M)": "Inline math (Ctrl+M)",
    "Toán khối (Ctrl+Shift+M)": "Block math (Ctrl+Shift+M)",
    "Trích dẫn": "Quote",
    "Đường ngang": "Horizontal rule",
    "Chèn liên kết": "Insert link",
    "Chèn ảnh": "Insert image",
    "Bảng (Ctrl+T)": "Table (Ctrl+T)",
    "Khối mã": "Code block",
    "Bình luận HTML (Ctrl+/)": "HTML comment (Ctrl+/)",
    "Tìm (Ctrl+F)": "Find (Ctrl+F)",
    "Thay (Ctrl+H)": "Replace (Ctrl+H)",
    "Biên dịch xem trước (Ctrl+Enter)": "Compile preview (Ctrl+Enter)",
    "Trợ lý eMeX (Ctrl+G)": "eMeX Assistant (Ctrl+G)",
    "Bật/Tắt xem trước (Ctrl+P)": "Toggle preview (Ctrl+P)",
    "Bật/Tắt bảng ký hiệu": "Toggle symbol palette",
    "Chế độ tập trung (F11)": "Focus mode (F11)",
    "Cài đặt": "Settings",
    "Giới thiệu": "About",
    "Tạo trang Markdown mới từ trang trống hoặc mẫu": "Create a Markdown page from a blank page or template",
    "Mở tệp Markdown / tệp gần đây": "Open Markdown file / recent files",
    "Lưu tệp Markdown hiện tại (Ctrl+S)": "Save current Markdown file (Ctrl+S)",
    "Chèn nội dung": "Insert content",
    "Công cụ soạn thảo": "Editing tools",
    "Tùy chọn hiển thị": "View options",
    "Mở tệp vừa xuất": "Open last exported file",
    "Trang trống": "Blank page",
    "Tạo trang mới từ mẫu {name}": "Create a new page from template {name}",
    "Mẫu của bạn": "Your templates",
    "Tạo trang mới từ mẫu của bạn: {name}": "Create a new page from your template: {name}",
    "Thêm mẫu từ trang hiện tại": "Add template from current page",
    "Mở...": "Open...",
    "(Chưa có tệp gần đây)": "(No recent files)",
    "Xoá danh sách": "Clear list",
    "Chưa đặt tên.md": "Untitled.md",
    "Mẫu mới": "New template",
    "Đã tạo trang mới từ mẫu: {name}": "Created new page from template: {name}",
    "Trang trống": "Blank page",
    "Trang hiện tại đang trống, chưa có nội dung để lưu thành mẫu.": "The current page is blank; there is no content to save as a template.",
    "Thêm mẫu": "Add template",
    "Tên mẫu:": "Template name:",
    "Thiếu tên mẫu": "Missing template name",
    "Vui lòng nhập tên mẫu.": "Enter a template name.",
    "Mẫu đã tồn tại": "Template already exists",
    "Mẫu '{name}' đã tồn tại. Ghi đè bằng trang hiện tại?": "Template '{name}' already exists. Overwrite it with the current page?",
    "Lỗi lưu mẫu": "Template save error",
    "Không thể lưu mẫu mới vào cấu hình.": "Cannot save the new template to settings.",
    "Đã {action} mẫu: {name}": "{action} template: {name}",
    "cập nhật": "updated",
    "thêm": "added",
    "Mở file Markdown": "Open Markdown file",
    "Markdown (*.md *.markdown *.mdown *.txt);;Tất cả (*)": "Markdown (*.md *.markdown *.mdown *.txt);;All files (*)",
    "Markdown (*.md);;Tất cả (*)": "Markdown (*.md);;All files (*)",
    "Không tìm thấy file": "File not found",
    "Không đọc được file": "Cannot read file",
    "Chưa lưu": "Unsaved changes",
    "File '{name}' chưa được lưu. Lưu trước khi đóng?": "File '{name}' has unsaved changes. Save before closing?",
    "File '{name}' có thay đổi. Lưu trước khi thoát?": "File '{name}' has changes. Save before exiting?",
    "Đã lưu: {path}": "Saved: {path}",
    "Lỗi lưu": "Save error",
    "Lưu thành .md": "Save as .md",
    "Đang xuất {kind}...": "Exporting {kind}...",
    "Đang xuất {kind}…": "Exporting {kind}...",
    "Lỗi xuất {kind}: {message}": "{kind} export error: {message}",
    "Mở tệp": "Open file",
    "Xuất HTML": "Export HTML",
    "Xuất LaTeX": "Export LaTeX",
    "Xuất Word": "Export Word",
    "Xuất PDF": "Export PDF",
    "Tài liệu Markdown": "Markdown Document",
    "Đang chờ MathJax/TikZ render rồi in PDF...": "Waiting for MathJax/TikZ to render before printing PDF...",
    "Đang chuẩn bị PDF…": "Preparing PDF...",
    "Lỗi render preview, không xuất được PDF.": "Preview render failed; cannot export PDF.",
    "Preview render quá lâu, không xuất được PDF.": "Preview render timed out; cannot export PDF.",
    "Đã xuất PDF: {path}": "Exported PDF: {path}",
    "Đã xuất PDF: {name}": "Exported PDF: {name}",
    "Xuất PDF thất bại.": "PDF export failed.",
    "Không thể tạo PDF từ preview. Kiểm tra preview đang hiển thị đúng.": "Cannot create PDF from preview. Check that the preview is displayed correctly.",
    "Chưa có tệp nào được xuất trong phiên này.": "No file has been exported in this session.",
    "Không tìm thấy: {path}": "Not found: {path}",
    "Chọn ảnh": "Choose image",
    "Hình ảnh (*.png *.jpg *.jpeg *.svg *.gif *.webp)": "Images (*.png *.jpg *.jpeg *.svg *.gif *.webp)",
    "ảnh": "image",
    "Đã chèn ảnh từ clipboard: {name}": "Inserted image from clipboard: {name}",
    "Không dán được ảnh: {message}": "Could not paste image: {message}",
    "Không lưu được ảnh clipboard.": "Could not save clipboard image.",
    "URL:": "URL:",
    "Ngôn ngữ (ví dụ: python, javascript, tikz):": "Language (for example: python, javascript, tikz):",
    "Đang biên dịch xem trước...": "Compiling preview...",
    "Đã biên dịch xem trước.": "Preview compiled.",
    "Đã đồng bộ tới dòng {line}.": "Synced to line {line}.",
    "Đã thay {count} chỗ.": "Replaced {count} matches.",
    "Đã cập nhật cấu hình.": "Settings updated.",
    "Có bản cập nhật mới: eMeX v{version}": "New update available: eMeX v{version}",
    "Có bản cập nhật mới: eMeX v{version}\nNhấp để cập nhật.": "New update available: eMeX v{version}\nClick to update.",
    "Tự động lưu lỗi: {names}": "Auto-save error: {names}",
    "Không mở được {count} tệp: {names}": "Could not open {count} files: {names}",
    "Lỗi khôi phục phiên: {message}": "Session restore error: {message}",
    "Đóng tab": "Close tab",
    "Đóng các tab khác": "Close other tabs",
    "Đóng các tab bên phải": "Close tabs to the right",
    "Mở thư mục chứa": "Open containing folder",
    "Sao chép đường dẫn": "Copy path",
    "Đã mở {count} tệp": "Opened {count} files",

    "Cài đặt eMeX": "eMeX Settings",
    "Trình soạn thảo": "Editor",
    "Font soạn thảo:": "Editor font:",
    "Cỡ chữ:": "Font size:",
    "Số khoảng trắng / Tab:": "Spaces per tab:",
    "Tự xuống dòng": "Wrap lines",
    "Tự đóng cặp { } [ ] ( ) \" \" $ $ ` `": "Auto-pair { } [ ] ( ) \" \" $ $ ` `",
    "Tự động lưu sau 60 giây (chỉ tệp đã đặt tên)": "Auto-save every 60 seconds (named files only)",
    "Kích thước thanh công cụ && biểu tượng": "Toolbar && icon sizes",
    "Cỡ biểu tượng thanh công cụ:": "Toolbar icon size:",
    "Đệm nút thanh công cụ:": "Toolbar button padding:",
    "Nút bảng ký hiệu:": "Symbol button:",
    "Cỡ chữ ký hiệu:": "Symbol font size:",
    "Kích thước biểu tượng emoji trên thanh công cụ chính": "Emoji icon size on the main toolbar",
    "Đệm bên trong mỗi nút trên thanh công cụ": "Inner padding of each toolbar button",
    "Kích thước mỗi nút ký hiệu ở bảng bên trái": "Size of each symbol button in the left panel",
    "Cỡ chữ trên các nút ký hiệu": "Font size on symbol buttons",
    "Mẹo: Ctrl+G mở Trợ lý eMeX · Ctrl+P bật/tắt xem trước · Ctrl+/ bình luận · Ctrl+Enter biên dịch xem trước.": "Tip: Ctrl+G opens eMeX Assistant · Ctrl+P toggles preview · Ctrl+/ comments · Ctrl+Enter compiles preview.",
    "Cấu hình Gemini dùng cho Trợ lý eMeX. Lấy khóa API tại <a href='https://aistudio.google.com/app/apikey'>aistudio.google.com/app/apikey</a>.": "Configure Gemini for eMeX Assistant. Get an API key at <a href='https://aistudio.google.com/app/apikey'>aistudio.google.com/app/apikey</a>.",
    "Khóa API Gemini:": "Gemini API key:",
    "Dán khóa API Gemini": "Paste Gemini API key",
    "Mô hình Gemini": "Gemini model",
    "Tải danh sách mô hình": "Load model list",
    "Mô hình mặc định:": "Default model:",
    "Thiếu khóa API": "Missing API key",
    "Hãy nhập khóa API trong tab Gemini AI trước khi tải danh sách mô hình.": "Enter the API key in the Gemini AI tab before loading the model list.",
    "Đang tải...": "Loading...",
    "Đang gọi Gemini API...": "Calling Gemini API...",
    "Không tải được mô hình": "Could not load models",
    "Chi tiết:\n{error}": "Details:\n{error}",
    "Không có mô hình nào hỗ trợ generateContent.": "No model supports generateContent.",
    "Đã tải {count} mô hình (sắp xếp mới → cũ).": "Loaded {count} models (newest → oldest).",
    "Giới thiệu {app}": "About {app}",
    "Phiên bản {version} · Trình soạn thảo Markdown": "Version {version} · Markdown Editor",
    "Đóng": "Close",

    "Xem trước": "Preview",
    "Đang chuẩn bị xem trước...": "Preparing preview...",
    "Đang render TikZ...": "Rendering TikZ...",
    "TikZ render quá lâu hoặc mã TikZ có lỗi.": "TikZ rendering took too long or the TikZ code has errors.",
    "Không tải được TikZJax. Kiểm tra kết nối mạng hoặc quyền tải CDN.": "Could not load TikZJax. Check network connection or CDN loading permissions.",
    "Auto: đoạn hiện tại": "Auto: current block",
    "Auto: dòng {line}": "Auto: line {line}",
    "Biên dịch: toàn tài liệu": "Compile: whole document",

    "Ảnh": "Image",
    "Không mở được ảnh.": "Cannot open image.",
    "Trợ lý eMeX": "eMeX Assistant",
    "Thu gọn Trợ lý eMeX sang cột trái": "Dock eMeX Assistant to the left panel",
    "Đưa Trợ lý eMeX trở lại cửa sổ nổi": "Return eMeX Assistant to the floating window",
    "Mình hỗ trợ cách dùng eMeX, các lệnh trong ứng dụng, và soạn/chỉnh Markdown, công thức, TikZ cho tài liệu trong eMeX. Khóa API và mô hình được cấu hình trong bảng Cài đặt.": "I can help with eMeX usage, app commands, and drafting/editing Markdown, formulas, and TikZ for documents in eMeX. The API key and model are configured in Settings.",
    "Nhập yêu cầu... Enter để gửi, Shift+Enter để xuống dòng, Ctrl+V để dán ảnh.": "Type a request... Enter to send, Shift+Enter for a new line, Ctrl+V to paste an image.",
    "Ảnh": "Image",
    "Gửi": "Send",
    "Đính kèm: {count} mục": "Attachments: {count} items",
    "Đính kèm ảnh": "Attach image",
    "Hình ảnh (*.png *.jpg *.jpeg *.webp)": "Images (*.png *.jpg *.jpeg *.webp)",
    "Nhập khóa API Gemini trong Cài đặt > Gemini AI trước khi gửi.": "Enter the Gemini API key in Settings > Gemini AI before sending.",
    "Trống": "Empty",
    "Hãy nhập yêu cầu hoặc dán nội dung trước.": "Enter a request or paste content first.",
    "(tệp văn bản)": "(text file)",
    "(ảnh)": "(image)",
    "Đang gửi...": "Sending...",
    "Lỗi: ": "Error: ",

    "Cập nhật eMeX": "Update eMeX",
    "Có phiên bản mới": "New version available",
    "eMeX v{version} đã sẵn sàng để cài đặt": "eMeX v{version} is ready to install",
    "Nội dung cập nhật:": "Update notes:",
    "Không nhắc lại": "Do not remind again",
    "Nhắc lại sau": "Later",
    "Cập nhật ngay": "Update now",
    "Đang cập nhật...": "Updating...",
    "Đang kết nối...": "Connecting...",
    "Đang tải: {done:.1f} / {total:.1f} MB": "Downloading: {done:.1f} / {total:.1f} MB",
    "Đang tải: {done:.1f} MB...": "Downloading: {done:.1f} MB...",
    "Hoàn tất. Ứng dụng sẽ khởi động lại sau vài giây...": "Done. The app will restart in a few seconds...",
    "Không thể cập nhật.": "Cannot update.",
    "Thử lại": "Retry",
    "- Bản cập nhật v{version} đã sẵn sàng để cài đặt.": "- Update v{version} is ready to install.",
    "Đang chạy từ mã nguồn nên không hỗ trợ tự cập nhật.": "Auto-update is not supported when running from source.",
    "Không tìm thấy gói cập nhật phù hợp ({asset}).": "No matching update package found ({asset}).",
    "Đã hủy cập nhật.": "Update cancelled.",
    "Không tìm thấy '{expected}' trong gói cập nhật.": "Could not find '{expected}' in the update package.",

    # Late additions / normalized Vietnamese source strings.
    "Đang khởi động...": "Starting...",
    "Đang chuẩn bị giao diện...": "Preparing interface...",
    "Đang mở tài liệu...": "Opening documents...",
    "v{version} · Trình soạn thảo Markdown": "v{version} · Markdown Editor",
    "Biên dịch": "Compile",
    "Xuất tài liệu": "Export document",
    "TikZ kết xuất quá lâu hoặc mã TikZ có lỗi.": "TikZ rendering took too long or the TikZ code has errors.",
    "Đang kết xuất TikZ...": "Rendering TikZ...",
    "Tự động: đoạn hiện tại": "Auto: current block",
    "Tự động: dòng {line}": "Auto: line {line}",
    "Lưu": "Save",
    "Hủy": "Cancel",
    "Mặc định": "Defaults",
    "Phông chữ soạn thảo:": "Editor font:",
    "Chưa đặt tên": "Untitled",
    "Mở tệp Markdown": "Open Markdown file",
    "Không tìm thấy tệp": "File not found",
    "Không đọc được tệp": "Cannot read file",
    "Tệp '{name}' chưa được lưu. Lưu trước khi đóng?": "File '{name}' has unsaved changes. Save before closing?",
    "Tệp '{name}' có thay đổi. Lưu trước khi thoát?": "File '{name}' has changes. Save before exiting?",
    "Đã xuất HTML: {path}": "Exported HTML: {path}",
    "Đã xuất LaTeX: {path}": "Exported LaTeX: {path}",
    "Đã xuất Word: {path}": "Exported Word: {path}",
    "Đang chờ MathJax/TikZ kết xuất rồi in PDF...": "Waiting for MathJax/TikZ to render before printing PDF...",
    "Lỗi kết xuất xem trước, không xuất được PDF.": "Preview render failed; cannot export PDF.",
    "Xem trước kết xuất quá lâu, không xuất được PDF.": "Preview render timed out; cannot export PDF.",
    "Không thể tạo PDF từ khung xem trước. Kiểm tra khung xem trước đang hiển thị đúng.": "Cannot create PDF from the preview pane. Check that the preview is displayed correctly.",
    "Đang gọi Gemini API...": "Calling Gemini API...",
    "Phản hồi không hợp lệ: {data}": "Invalid response: {data}",
    "Lỗi kết nối: {error}": "Connection error: {error}",
    "Văn bản đã dán": "Pasted text",
    "Tài liệu cơ bản": "Basic document",
    "Ghi chú nhanh": "Quick note",
    "Bài học": "Lesson",
    "Bài tập toán": "Math exercise",
    "Báo cáo ngắn": "Short report",
    "Markdown nhanh": "Quick Markdown",
    "Hy Lạp thường": "Greek lowercase",
    "Hy Lạp hoa": "Greek uppercase",
    "Quan hệ": "Relations",
    "Phép toán": "Operators",
    "Mũi tên": "Arrows",
    "Logic & Tập hợp": "Logic & Sets",
    "Chưa có thư viện python-docx. Cài bằng:\n  pip install python-docx": "python-docx is not installed. Install with:\n  pip install python-docx",
    "[Ảnh: {url}]": "[Image: {url}]",
}
