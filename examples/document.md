# Tài liệu mẫu eMeX

Đây là tài liệu mẫu để kiểm tra nhanh Markdown, công thức, TikZ, bảng, code và danh sách trong eMeX.

## Công thức

Inline: $E = mc^2$.

Block:

$$
\int_a^b f(x)\,dx = F(b) - F(a)
$$

Phân thức và căn:

$$
x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}
$$

## TikZ

```tikz
\begin{tikzpicture}
  \draw[->] (-1,0) -- (4,0) node[right] {$x$};
  \draw[->] (0,-1) -- (0,4) node[above] {$y$};
  \draw[domain=-1:3, smooth, variable=\x] plot ({\x},{(\x-1)^2});
\end{tikzpicture}
```

## Bảng

| Mục | Giá trị |
| --- | ---: |
| Số câu | 10 |
| Thời gian | 45 phút |

## Code

```python
def hello():
    print("Xin chào từ eMeX")
```

## Checklist

- [x] Soạn Markdown
- [x] Compile preview bằng `Ctrl+Enter`
- [ ] Xuất PDF/DOCX
- [ ] Kiểm tra Trợ lý eMeX bằng `Ctrl+G`
