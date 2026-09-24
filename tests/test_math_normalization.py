import html
import unittest
from unittest.mock import patch

from src.text_normalizer import (
    normalize_external_paste_text,
    normalize_markdown_for_compile,
)


COROLLARY = r"""**Hệ quả 3.1 (Điều kiện phát hiện).** Đối tượng phát hiện được khi và chỉ khi $x>\gamma^{1/4}$, tức
$$\frac A\sigma>\Big(\frac{p}{n}\Big)^{1/4}
\quad\Longleftrightarrow\quad
\boxed{\ \mathrm{SNR}>\frac{1}{(pn)^{1/4}}\ }
\quad\Longleftrightarrow\quad
n>\frac{1}{p\cdot\mathrm{SNR}^4}.$$"""
BROKEN_COROLLARY = COROLLARY.replace(r"\Big(", r"\Big$").replace(r"\Big)", r"\Big$")
OPTIMAL_FRAMES = r"""**Mệnh đề 4.3 (Số khung tối ưu).** Cực tiểu hoá $\mathcal E(n)$ theo $n$ cho
$$\boxed{\ n^\star=\frac{\sqrt3}{\varepsilon\cdot\mathrm{SNR}},\qquad
\mathcal E(n^\star)=\frac{2\varepsilon}{\sqrt3\,\mathrm{SNR}}\approx1.155\,\frac{\varepsilon}{\mathrm{SNR}}\ }$$"""
SINGULAR_VALUES = r"""$$\frac{\sigma_1(Y)}{\sigma\sqrt n}\longrightarrow
\begin{cases}1+\sqrt\gamma,&x\le\gamma^{1/4},\\[6pt]
\dfrac{\sqrt{(1+x^2)(\gamma+x^2)}}{x},&x>\gamma^{1/4},\end{cases}
\qquad
q:=|\langle\hat u_1,u\rangle|^2\longrightarrow
\begin{cases}0,&x\le\gamma^{1/4},\\[6pt]
\dfrac{x^4-\gamma}{x^4+\gamma x^2},&x>\gamma^{1/4}.\end{cases}$$"""


class ClipboardPreservationTests(unittest.TestCase):
    def test_original_report_math_is_pasted_verbatim(self):
        for source in (COROLLARY, OPTIMAL_FRAMES, SINGULAR_VALUES):
            with self.subTest(source=source):
                self.assertEqual(normalize_external_paste_text(source), source)

    def test_formula_fragments_and_ordinary_parentheses_are_not_reinterpreted(self):
        for source in (r"\mathcal E(n^\star)", r"\sigma_1(Y)",
                       r"\sqrt{(1+x^2)(\gamma+x^2)}", "Item (a), option (x=1).",
                       BROKEN_COROLLARY):
            with self.subTest(source=source):
                self.assertEqual(normalize_external_paste_text(source), source)

    def test_whitespace_code_and_unicode_are_preserved(self):
        source = "```python\n\tvalue = '(x)'  \n```\nCafe\u0301\u00a0\u200b\n"
        self.assertEqual(normalize_external_paste_text(source), source)

    def test_only_line_endings_are_adapted(self):
        self.assertEqual(normalize_external_paste_text("a\r\nb\rc\n"), "a\nb\nc\n")
        self.assertEqual(normalize_external_paste_text(""), "")


class MathNormalizationTests(unittest.TestCase):
    def test_paste_then_compile_preserves_detection_formula(self):
        pasted = normalize_external_paste_text(COROLLARY)
        self.assertEqual(pasted, COROLLARY)
        self.assertEqual(normalize_markdown_for_compile(pasted), COROLLARY)

    def test_existing_corruption_is_repaired_without_changing_line_numbers(self):
        repaired = normalize_markdown_for_compile(BROKEN_COROLLARY)
        self.assertEqual(repaired, COROLLARY)
        self.assertEqual(repaired.count("\n"), BROKEN_COROLLARY.count("\n"))
        self.assertEqual(normalize_markdown_for_compile(repaired), repaired)

    def test_display_delimiters_on_formula_or_separate_lines(self):
        formula = r"\Big(\frac{p}{n}\Big)^{1/4}"
        for opener, closer in (("$$", "$$"), (r"\[", r"\]")):
            for before, after in (("", ""), ("\n", "\n"), ("", "\n"), ("\n", "")):
                with self.subTest(opener=opener, before=before, after=after):
                    source = opener + before + formula + after + closer
                    expected = "$$" + before + formula + after + "$$"
                    self.assertEqual(normalize_markdown_for_compile(source), expected)

    def test_entire_multiline_formula_is_protected(self):
        source = r"""$$f(x)=
\Big(\frac{p}{n}\Big)^{1/4}
+ (a_i) + (y)
$$
Text (z)."""
        self.assertEqual(normalize_markdown_for_compile(source), source.replace("Text (z)", "Text $z$"))

    def test_unfinished_display_math_does_not_become_prose(self):
        source = r"$$f(x)=" + "\n" + r"\Big(\frac{p}{n}\Big)"
        self.assertEqual(normalize_markdown_for_compile(source), source)

    def test_matching_sized_pairs_only(self):
        for size in ("big", "Big", "bigg", "Bigg"):
            for left, right in ((size, size), (size + "l", size + "r")):
                with self.subTest(left=left, right=right):
                    formula = "\\" + left + r"$\frac{p}{n}" + "\\" + right + "$"
                    expected = "\\" + left + r"(\frac{p}{n}" + "\\" + right + ")"
                    self.assertEqual(normalize_markdown_for_compile("$$" + formula + "$$"),
                                     "$$" + expected + "$$")
        for formula in (r"\Big$ x", r"\Big$ x \big$", r"\Big\$ x \Big\$"):
            source = "$$" + formula + "$$"
            self.assertEqual(normalize_markdown_for_compile(source), source)

    def test_code_links_and_valid_inline_math_are_preserved(self):
        for source in (
            "```latex\n" + BROKEN_COROLLARY + "\n```",
            "~~~latex\n" + BROKEN_COROLLARY + "\n~~~",
            r"`$$\Big$ x \Big$$$`",
            r"$\Big(\frac{p}{n}\Big)^{1/4}$",
            r"\(\Big(\frac{p}{n}\Big)^{1/4}\)",
            "[Example](https://example.com/math)",
            "![Plot](plot.png)",
        ):
            with self.subTest(source=source):
                self.assertEqual(normalize_markdown_for_compile(source), source)

    def test_legacy_math_blocks_still_normalize(self):
        source = "[\n" + r"\frac p n" + "\n]\nText (x)."
        expected = "$$\n" + r"\frac{p}{n}" + "\n$$\nText $x$."
        self.assertEqual(normalize_markdown_for_compile(source), expected)


class EditorClipboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load WebEngine before QApplication, as in the real application.
        from src import preview  # noqa: F401
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_text_from_rich_clipboard_is_inserted_verbatim_and_undoable(self):
        from PyQt6.QtCore import QMimeData
        from PyQt6.QtGui import QTextCursor
        from src.editor import CodeEditor

        editor = CodeEditor()
        try:
            editor.setPlainText("Before\nreplace me\nAfter")
            cursor = editor.textCursor()
            cursor.setPosition(len("Before\n"))
            cursor.setPosition(len("Before\nreplace me"), QTextCursor.MoveMode.KeepAnchor)
            editor.setTextCursor(cursor)
            mime = QMimeData()
            mime.setText(OPTIMAL_FRAMES)
            mime.setHtml("<p>Rendered clipboard alternative</p>")
            editor.insertFromMimeData(mime)
            expected = "Before\n" + OPTIMAL_FRAMES + "\nAfter"
            self.assertEqual(editor.toPlainText(), expected)
            editor.undo()
            self.assertEqual(editor.toPlainText(), "Before\nreplace me\nAfter")
            editor.redo()
            self.assertEqual(editor.toPlainText(), expected)
        finally:
            editor.close()
            editor.deleteLater()


class PreviewMathTests(unittest.TestCase):
    def test_report_parentheses_survive_paste_full_and_fragment_preview(self):
        from src.preview import markdown_fragment_to_html, markdown_to_html

        with patch("src.preview._ensure_tikzjax_server", return_value=""):
            for source, expected in (
                (OPTIMAL_FRAMES, (r"\mathcal E(n^\star)",)),
                (SINGULAR_VALUES, (r"\sigma_1(Y)", r"\sqrt{(1+x^2)(\gamma+x^2)}")),
            ):
                pasted = normalize_external_paste_text(source)
                for render in (markdown_to_html, markdown_fragment_to_html):
                    with self.subTest(source=source, render=render.__name__):
                        rendered = html.unescape(render(pasted))
                        for formula in expected:
                            self.assertIn(formula, rendered)
                        self.assertEqual(rendered.count('<div class="emex-math-block">'), 1)
                self.assertEqual(pasted, source)

    def test_full_and_fragment_preview_receive_valid_formula(self):
        from src.preview import markdown_fragment_to_html, markdown_to_html

        # Building preview HTML does not need the unrelated TikZ asset server.
        with patch("src.preview._ensure_tikzjax_server", return_value=""):
            for source in (COROLLARY, BROKEN_COROLLARY):
                for render in (markdown_to_html, markdown_fragment_to_html):
                    with self.subTest(source=source, render=render.__name__):
                        rendered = html.unescape(render(source))
                        self.assertEqual(rendered.count('<div class="emex-math-block">'), 1)
                        self.assertIn(r"\Big(\frac{p}{n}\Big)^{1/4}", rendered)
                        self.assertIn(r"\boxed{\ \mathrm{SNR}>\frac{1}{(pn)^{1/4}}\ }", rendered)
                        self.assertNotIn(r"\Big$", rendered)
                        self.assertIn("<strong>Hệ quả 3.1 (Điều kiện phát hiện).</strong>", rendered)

    def test_latex_export_receives_repaired_math(self):
        from src.exporters import markdown_to_latex

        rendered = markdown_to_latex(BROKEN_COROLLARY)
        self.assertIn(r"\Big(\frac{p}{n}\Big)^{1/4}", rendered)
        self.assertNotIn(r"\Big$", rendered)


if __name__ == "__main__":
    unittest.main()
