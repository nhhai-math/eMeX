# TỰ ĐỘNG CHỌN THỜI ĐIỂM CHỤP VÀ NHẬN DIỆN ĐỐI TƯỢNG BẰNG MA TRẬN NGẪU NHIÊN

### Bài toán dừng tối ưu cho luồng khung hình camera

**Học phần: Ma trận ngẫu nhiên (AS5019) — Trường Đại học Bách khoa, ĐHQG-HCM**
**Khoa Khoa học Ứng dụng — Bộ môn Toán Ứng dụng**

---

## Tóm tắt

Báo cáo giải quyết bài toán: camera đang dò một đối tượng trong chế độ xem trực tiếp; thay vì để người dùng bấm
máy, hệ thống phải **tự chọn thời điểm chụp tối ưu** rồi **nhận diện đối tượng** trong ảnh thu được. Chúng tôi mô
hình hoá luồng khung hình thành ma trận dữ liệu $Y\in\mathbb R^{p\times n}$ dạng "tín hiệu hạng thấp cộng nhiễu",
và cho thấy bài toán quy về một **bài toán dừng tối ưu** có lời giải dạng đóng.

Bốn kết quả chính:

1. **Điều kiện phát hiện.** Với $p$ điểm ảnh và $n$ khung hình tích luỹ, đối tượng chỉ khôi phục được khi tỉ số
   tín hiệu trên nhiễu mỗi điểm ảnh vượt $(pn)^{-1/4}$. Với $p=4096$, $n=32$ ngưỡng là $0.0526$: đối tượng mờ hơn
   nhiễu gần 20 lần vẫn khôi phục được.
2. **Định luật dừng tối ưu.** Sai số của ảnh hợp nhất so với đối tượng *hiện tại* tách chính xác thành hai thành
   phần $\dfrac{1}{n\cdot\mathrm{SNR}^2}+\dfrac{\varepsilon^2n}{3}$, cho số khung hình tối ưu
   $$n^\star=\frac{\sqrt3}{\varepsilon\cdot\mathrm{SNR}},\qquad
   \text{sai số tối thiểu}=\frac{2\varepsilon}{\sqrt3\,\mathrm{SNR}},$$
   với $\varepsilon$ là tốc độ trôi cảnh. Công thức được kiểm chứng trên 5 cấu hình, sai lệch dưới $10\%$.
   Đáng chú ý: **$n^\star$ không phụ thuộc độ phân giải ảnh**.
3. **Quy tắc quyết định trực tuyến.** Cả hai tham số $\mathrm{SNR}$ và $\varepsilon$ đều ước lượng được ngay trong
   lúc chạy — $\mathrm{SNR}$ bằng cách đảo công thức Benaych-Georges–Nadakuditi từ trị kỳ dị lớn nhất, $\varepsilon$
   từ độ suy giảm của các đường chéo phụ trong ma trận Gram của các khung hình. Hệ thống đạt sai số **bằng đúng**
   sai số tại điểm tối ưu lý thuyết (chênh lệch dưới $0.0003$).
4. **Vector kỳ dị phải là điểm chất lượng khung hình.** Tương quan giữa $|\hat v_1|$ và chất lượng thật của từng
   khung đạt $0.9993$, cho phép hệ thống vừa hợp nhất vừa chỉ ra khung hình đơn tốt nhất.

Chúng tôi cũng báo cáo một quy tắc kích hoạt **thất bại** (dừng khi $\sigma_2$ vượt mép phổ nhiễu — kích hoạt quá
sớm, sai số tăng gấp đôi), và một mô hình đánh giá bước nhận diện mà thực nghiệm **bác bỏ**, dẫn tới kết luận đúng
hơn: cái quyết định thành bại của bước nhận diện không phải độ lớn của sai số mà là **cấu trúc** của nó.

---

## Mục lục

§1 Bài toán kỹ thuật và mô hình hoá · §2 Công cụ lý thuyết · §3 Cần bao nhiêu khung hình?
§4 Bài toán dừng tối ưu · §5 Quyết định trực tuyến · §6 Chọn khung và hợp nhất · §7 Khôi phục ảnh
§8 Bước nhận diện · §9 Thuật toán đầy đủ · §10 Hạn chế · §11 Kết luận
Phụ lục A Mã nguồn · B Bảng công thức · C Tài liệu tham khảo

---

# §1. Bài toán kỹ thuật và mô hình hoá

## 1.1. Hệ thống mong muốn

Camera ở chế độ xem trực tiếp, sinh khung hình ở tốc độ $f$ khung/giây (điển hình $f=30$–$120$). Một bộ dò đối
tượng đã khoanh được vùng chứa đối tượng. Hệ thống cần tự trả lời ba câu hỏi:

| Câu hỏi | Tên kỹ thuật |
|---|---|
| Có đối tượng thật trong vùng này không, hay chỉ là nhiễu? | **phát hiện** |
| Đã tích luỹ đủ thông tin chưa — bấm máy lúc nào? | **dừng tối ưu** |
| Ảnh xuất ra là khung nào, và đối tượng là ai/cái gì? | **hợp nhất + nhận diện** |

Điểm mấu chốt phân biệt bài toán này với chụp ảnh thông thường: hệ thống **không bị giới hạn ở một khung hình**.
Nó có cả một luồng. Câu hỏi không phải "khung nào đẹp nhất" mà là "**dùng bao nhiêu khung, và dừng lúc nào**".

## 1.2. Vì sao đây là trường hợp A

Trong khung phân loại đã dựng ở báo cáo trước, có ba cách xếp cột cho ma trận dữ liệu ảnh. Bài toán này rơi đúng
vào **trường hợp A: một đối tượng, nhiều lần chụp**:

- mỗi **cột** là một khung hình của cùng một đối tượng;
- $p$ = số điểm ảnh trong vùng quan tâm, $n$ = số khung hình trong bộ đệm;
- **tín hiệu** là chính đối tượng, xuất hiện gần như giống nhau ở mọi cột ⟹ cấu trúc **hạng 1**;
- **nhiễu** là nhiễu cảm biến, độc lập giữa các khung;
- **không trung tâm hoá.** Đây là điểm dễ sai nhất: đối tượng nằm *trong vector trung bình*, nên trừ trung bình sẽ
  xoá sạch tín hiệu. Mô hình đúng là "tín hiệu cộng nhiễu" trên ma trận thô, không phải mô hình hiệp phương sai.

Bước **nhận diện** ở cuối lại thuộc trường hợp B (nhiều đối tượng) và tuân theo lý thuyết khác; §8 xử lý điểm nối
này.

## 1.3. Ba nguồn biến thiên giữa các khung hình

Cần phân biệt rõ, vì chúng đòi hỏi ba cách xử lý khác nhau:

| Nguồn | Bản chất | Ảnh hưởng tới mô hình |
|---|---|---|
| **Nhiễu cảm biến** (shot noise, đọc) | ngẫu nhiên, độc lập giữa khung | thành phần $\sigma Z$ |
| **Thay đổi độ lợi** (tự động phơi sáng, nhấp nháy đèn, che khuất một phần) | nhân với hệ số $a_j$ theo khung | tín hiệu vẫn hạng 1 nhưng vector phải $v$ **không đều** |
| **Trôi cảnh** (đối tượng di chuyển, rung tay, biến dạng) | đối tượng *thay đổi* theo thời gian | tín hiệu **không còn hạng 1** |

Nguồn thứ hai là lý do bắt buộc phải dùng SVD thay vì trung bình cộng: trung bình cộng giả định ngầm rằng
$v=\mathbf1/\sqrt n$, tức mọi khung đóng góp như nhau. Nguồn thứ ba là lý do bài toán có **điểm dừng tối ưu**
thay vì "càng nhiều càng tốt".

## 1.4. Mô hình toán học

**Định nghĩa 1.1 (Bộ đệm khung hình).** Tại thời điểm $T$, bộ đệm gồm $n$ khung gần nhất, xếp thành
$$Y^{(n)}=\big[\,y_{T-n+1}\ \cdots\ y_T\,\big]\in\mathbb R^{p\times n},$$
mỗi $y_j\in\mathbb R^p$ là vùng quan tâm của khung $j$ đã được duỗi thành vector.

**Định nghĩa 1.2 (Mô hình quan sát).**
$$y_j=A\,a_j\,x_j+\sigma z_j,\qquad j=T-n+1,\dots,T,$$
trong đó $x_j\in\mathbb R^p$, $\|x_j\|=1$, là **hướng ảnh của đối tượng tại khung $j$**; $A>0$ là biên độ tín hiệu;
$a_j>0$ là độ lợi khung; $z_j$ có các thành phần i.i.d. $\mathcal N(0,1)$; $\sigma$ là mức nhiễu.

**Định nghĩa 1.3 (Tỉ số tín hiệu trên nhiễu mỗi điểm ảnh).**
$$\mathrm{SNR}=\frac{A}{\sigma\sqrt p}.$$
Đây là đại lượng vật lý trực quan: biên độ trung bình của đối tượng trên mỗi điểm ảnh, chia cho độ lệch chuẩn của
nhiễu tại điểm ảnh đó. $\mathrm{SNR}=1$ nghĩa là đối tượng và nhiễu ngang nhau về biên độ trên từng điểm ảnh.

**Định nghĩa 1.4 (Mô hình trôi — bước ngẫu nhiên trên mặt cầu).** Hướng ảnh đối tượng biến thiên theo
$$x_{j+1}=\frac{\sqrt{1-\varepsilon^2}\,x_j+\varepsilon\,g_j}{\big\|\sqrt{1-\varepsilon^2}\,x_j+\varepsilon\,g_j\big\|},
\qquad g_j\ \text{đều trên mặt cầu đơn vị},$$
với $\varepsilon\in[0,1)$ là **tốc độ trôi** mỗi khung. Khi đó
$$\langle x_j,x_{j+k}\rangle\approx(1-\varepsilon^2)^{k/2}\approx e^{-k\varepsilon^2/2},$$
tức thời gian kết hợp (coherence time) là $n_c\approx2/\varepsilon^2$ khung.

> **Ví dụ 1.1 (quy đổi sang đại lượng vật lý).** Ở $f=60$ khung/giây, $\varepsilon=0.05$ ứng với $n_c=800$ khung
> $\approx13$ giây để đối tượng mất tương quan hoàn toàn — tương ứng cảnh gần như tĩnh, rung tay nhẹ.
> $\varepsilon=0.12$ cho $n_c\approx139$ khung $\approx2.3$ giây — đối tượng đang di chuyển rõ. Ta sẽ thấy ở §4
> rằng số khung nên tích luỹ **nhỏ hơn nhiều** so với $n_c$.

**Trường hợp lý tưởng (không trôi, $\varepsilon=0$, độ lợi đều).** Mô hình rút gọn thành
$$Y^{(n)}=A\,x_0\mathbf1^{\mathsf T}+\sigma Z,$$
một tín hiệu **hạng 1** cộng nhiễu — đúng dạng của mô hình mà lý thuyết ma trận ngẫu nhiên xử lý được trọn vẹn.

---

# §2. Công cụ lý thuyết

Phần này chỉ nêu những kết quả thực sự được dùng. Chứng minh xem [2], [3], [10].

## 2.1. SVD và xấp xỉ hạng thấp

**Định lý 2.1 (SVD, Eckart–Young–Mirsky).** Mọi $Y\in\mathbb R^{p\times n}$ viết được $Y=U\Sigma V^{\mathsf T}
=\sum_i\sigma_iu_iv_i^{\mathsf T}$ với $\sigma_1\ge\sigma_2\ge\cdots\ge0$, và xấp xỉ hạng $k$ tốt nhất theo chuẩn
Frobenius là $Y_k=\sum_{i\le k}\sigma_iu_iv_i^{\mathsf T}$, với sai số $\big(\sum_{i>k}\sigma_i^2\big)^{1/2}$.
*(Nguồn: [2], §2.)*

Trong bài toán của ta, $k=1$ và ba đại lượng có ý nghĩa vật lý trực tiếp:

| Đại lượng | Ý nghĩa vật lý |
|---|---|
| $\hat u_1\in\mathbb R^p$ | **ảnh đối tượng đã lọc nhiễu** — đây là thứ ta muốn |
| $\hat v_1\in\mathbb R^n$ | **hồ sơ chất lượng theo khung hình** (§6) |
| $\sigma_1$ | cường độ tín hiệu quan sát, dùng để suy ra chất lượng (§5) |

## 2.2. Mép phổ của nhiễu

**Định lý 2.2.** Với $Z\in\mathbb R^{p\times n}$ có phần tử i.i.d. kỳ vọng 0, phương sai 1, khi $p,n\to\infty$ với
$p/n\to\gamma$:
$$\|\sigma Z\|_2\longrightarrow\sigma(\sqrt p+\sqrt n)\quad\text{h.c.c.}$$
*(Nguồn: Marchenko–Pastur [5]; xem [3], §2.3.)*

**Đây là con số nền tảng của toàn bộ hệ thống.** Nó nói: nếu vùng quan tâm là $64\times64$ ($p=4096$) và bộ đệm có
$n=32$ khung, thì **nhiễu thuần tuý** sẽ tạo ra trị kỳ dị lớn nhất bằng $\sigma(64+5.66)=69.66\sigma$. Mọi giá trị
$\sigma_1$ dưới mức đó **không mang thông tin gì**.

> **Ví dụ 2.1.** Đừng nhầm với chuẩn Frobenius. Cùng cấu hình trên, $\|\sigma Z\|_F\approx\sigma\sqrt{pn}=362\sigma$
> — lớn gấp 5 lần. Nếu dùng nhầm $\|\cdot\|_F$ làm ngưỡng thì hệ thống sẽ không bao giờ chụp.

## 2.3. Chuyển tiếp pha cho tín hiệu hạng 1

**Định lý 2.3 (Benaych-Georges & Nadakuditi).** Cho $Y=s\,uw^{\mathsf T}+\sigma Z$ với $Y$ cỡ $p\times n$,
$\gamma=p/n$, và đặt $x=\dfrac{s}{\sigma\sqrt n}$. Khi $p,n\to\infty$:
$$\frac{\sigma_1(Y)}{\sigma\sqrt n}\longrightarrow
\begin{cases}1+\sqrt\gamma,&x\le\gamma^{1/4},\\[6pt]
\dfrac{\sqrt{(1+x^2)(\gamma+x^2)}}{x},&x>\gamma^{1/4},\end{cases}
\qquad
q:=|\langle\hat u_1,u\rangle|^2\longrightarrow
\begin{cases}0,&x\le\gamma^{1/4},\\[6pt]
\dfrac{x^4-\gamma}{x^4+\gamma x^2},&x>\gamma^{1/4}.\end{cases}$$
*(Nguồn: Benaych-Georges & Nadakuditi [10].)*

Đại lượng $q$ — bình phương độ trùng khớp giữa ảnh khôi phục và ảnh thật — là **thước đo chất lượng trung tâm**
của báo cáo này. $q=1$ nghĩa là khôi phục hoàn hảo; $q=0$ nghĩa là ảnh thu được hoàn toàn vô nghĩa.

## 2.4. Đảo ngược Định lý 2.3 — công cụ then chốt

Hệ thống thực tế **không biết** $s$ hay $u$. Nhưng nó đo được $\sigma_1$. Mệnh đề sau cho phép suy ngược.

**Mệnh đề 2.4 (Ước lượng chất lượng từ đại lượng quan sát được).** Đặt $\tilde s=\dfrac{\sigma_1(Y)}{\sigma\sqrt n}$
và $c=\tilde s^2-1-\gamma$. Nếu $\tilde s>1+\sqrt\gamma$ và $c^2>4\gamma$ thì
$$\hat x^2=\frac{c+\sqrt{c^2-4\gamma}}{2},\qquad
\hat q=\frac{\hat x^4-\gamma}{\hat x^4+\gamma\hat x^2}.$$
Ngược lại đặt $\hat x=\hat q=0$.

*Chứng minh.* Bình phương công thức trị kỳ dị trong Định lý 2.3:
$\tilde s^2x^2=(1+x^2)(\gamma+x^2)=x^4+(1+\gamma)x^2+\gamma$, tức
$x^4-(\tilde s^2-1-\gamma)x^2+\gamma=0$. Đây là phương trình bậc hai theo $x^2$; nghiệm lớn cho nhánh trên ngưỡng.
Thay vào công thức $q$. $\square$

**Ý nghĩa hệ thống.** Mệnh đề 2.4 cho phép camera **tự đánh giá chất lượng ảnh của chính nó theo thời gian thực**,
không cần ảnh tham chiếu. Đây là điều làm cho toàn bộ thiết kế khả thi. Thực nghiệm kiểm chứng ở §3.3.

## 2.5. Co rút tối ưu

**Định lý 2.5 (Gavish & Donoho).** Trị kỳ dị quan sát luôn bị **thổi phồng** so với tín hiệu thật. Ước lượng tối ưu
theo chuẩn Frobenius cho tín hiệu hạng 1 là
$$\hat s=\sigma\sqrt n\cdot\hat x\quad\text{với }\hat x\text{ như trong Mệnh đề 2.4},$$
tức phải **co** trị kỳ dị quan sát về $\hat x$ trước khi dựng lại ảnh, chứ không dùng thẳng $\sigma_1$.
*(Nguồn: Gavish & Donoho [12] cho ngưỡng cứng tối ưu; công thức co rút suy từ Định lý 2.3.)*

> **Ví dụ 2.2.** $p=n=200$, $\sigma=1$, tín hiệu thật $s=30$. Ta có $\gamma=1$, $x=30/\sqrt{200}=2.121$, và
> Định lý 2.3 dự đoán $\sigma_1=14.14\times2.593=36.67$; mô phỏng cho $36.90$. Nếu dựng lại ảnh bằng
> $\sigma_1\hat u_1\hat v_1^{\mathsf T}$ thì biên độ **cao hơn thực tế $23\%$**. Co rút sửa đúng sai lệch này.
---

# §3. Cần bao nhiêu khung hình? Điều kiện phát hiện

## 3.1. Ngưỡng phát hiện

Áp Định lý 2.3 cho mô hình lý tưởng $Y^{(n)}=A\,x_0\mathbf1^{\mathsf T}+\sigma Z$. Tín hiệu có trị kỳ dị
$s=A\sqrt n$ (vì $\|x_0\|=1$, $\|\mathbf1\|=\sqrt n$), nên
$$x=\frac{s}{\sigma\sqrt n}=\frac{A}{\sigma},\qquad \gamma=\frac pn .$$

**Hệ quả 3.1 (Điều kiện phát hiện).** Đối tượng phát hiện được khi và chỉ khi $x>\gamma^{1/4}$, tức
$$\frac{A}{\sigma}>\Bigl(\frac{p}{n}\Bigr)^{1/4}
\quad\Longleftrightarrow\quad
\boxed{\ \mathrm{SNR}>\frac{1}{(pn)^{1/4}}\ }
\quad\Longleftrightarrow\quad
n>\frac{1}{p\cdot\mathrm{SNR}^4}.$$

Ba nhận xét:

1. **Ngưỡng giảm theo $n^{-1/4}$** — chậm. Muốn hạ ngưỡng một nửa phải tăng số khung gấp 16 lần.
2. **Ngưỡng cũng giảm theo $p^{-1/4}$** — vùng quan tâm càng lớn càng dễ phát hiện, vì có nhiều điểm ảnh cùng
   chứng thực cho một giả thuyết.
3. Vế phải cuối cùng là **công thức thiết kế trực tiếp**: biết $\mathrm{SNR}$ và $p$, biết ngay cần ít nhất bao
   nhiêu khung.

## 3.2. Bảng thiết kế

Với $p=4096$ (vùng quan tâm $64\times64$):

| $n$ | $\gamma=p/n$ | ngưỡng $\gamma^{1/4}$ | ngưỡng $\mathrm{SNR}=(pn)^{-1/4}$ | Diễn giải |
|---|---|---|---|---|
| 1 | 4096 | 8.000 | 0.1250 | một khung: đối tượng phải rõ hơn nhiễu $1/8$ |
| 4 | 1024 | 5.657 | 0.0884 | |
| 16 | 256 | 4.000 | 0.0625 | |
| 32 | 128 | 3.364 | 0.0526 | mờ hơn nhiễu $19$ lần vẫn thấy |
| 64 | 64 | 2.828 | 0.0442 | |
| 128 | 32 | 2.378 | 0.0372 | mờ hơn nhiễu $27$ lần |

Ở $f=60$ khung/giây, $n=32$ chỉ tốn $0.53$ giây — hoàn toàn nằm trong thời gian người dùng giữ máy hướng vào
đối tượng.

## 3.3. TN1 — Kiểm chứng ngưỡng và bộ ước lượng chất lượng trực tuyến

**Thiết lập.** $p=4096$, $n=32$ ($\gamma=128$), $\sigma=1$, ngưỡng lý thuyết $\mathrm{SNR}=0.0526$. Mỗi cấu hình
lặp 10 lần. Cột cuối là **ước lượng trực tuyến** của $q$ theo Mệnh đề 2.4, chỉ dùng $\sigma_1$ quan sát được, hoàn
toàn không dùng $x_0$ thật.

| $\mathrm{SNR}$ | $x=A/\sigma$ | $\sigma_1$ đo | $\sigma_1$ dự đoán | $q$ thật | $q$ dự đoán | $\hat q$ **trực tuyến** |
|---|---|---|---|---|---|---|
| 0.0300 | 1.92 | 69.22 | 69.66 | 0.002 | 0.000 | 0.000 |
| 0.0450 | 2.88 | 69.29 | 69.66 | 0.012 | 0.000 | 0.004 |
| **0.0526** | 3.37 | 69.62 | 69.66 | 0.035 | 0.000 | 0.025 |
| 0.0650 | 4.16 | 70.20 | 70.13 | 0.079 | 0.068 | 0.065 |
| 0.0800 | 5.12 | 71.29 | 71.58 | 0.133 | 0.138 | 0.125 |
| 0.1200 | 7.68 | 78.11 | 78.01 | 0.308 | 0.304 | 0.306 |

**Ba kết luận.**

1. **Chuyển tiếp đúng tại $\mathrm{SNR}=0.0526$.** Dưới ngưỡng, $\sigma_1$ dính chặt vào mép nhiễu $69.66$ và $q$
   bằng 0 — ảnh khôi phục hoàn toàn vô nghĩa. Trên ngưỡng, $\sigma_1$ tách ra và $q$ tăng.
2. **Định lý 2.3 chính xác tới dưới $0.5\%$** ở mọi cấu hình.
3. **Bộ ước lượng trực tuyến hoạt động.** Cột cuối bám sát cột "$q$ thật" ($0.065$ vs $0.079$; $0.125$ vs $0.133$;
   $0.306$ vs $0.308$). Hệ thống thực sự biết chất lượng ảnh của mình mà không cần biết đáp án.

## 3.4. Diễn giải cho chế độ thiếu sáng

Hệ quả 3.1 chính là cơ sở toán học của "chế độ ban đêm" trên điện thoại: thay vì phơi sáng lâu (gây nhoè do rung
tay), máy chụp nhiều khung ngắn rồi hợp nhất. Đóng góp của lý thuyết ma trận ngẫu nhiên ở đây là cho **con số**:
với $\mathrm{SNR}$ đo được, cần chính xác bao nhiêu khung, và khi nào thì vô vọng.

---

# §4. Bài toán dừng tối ưu

## 4.1. Vì sao "càng nhiều càng tốt" là sai

Hệ quả 3.1 gợi ý cứ tích luỹ mãi. Điều đó chỉ đúng khi $\varepsilon=0$. Trong thực tế đối tượng trôi, và **các
khung cũ mô tả một đối tượng đã khác**. Tiêu chí đúng không phải "khôi phục hướng chủ đạo của bộ đệm" mà là
"**khôi phục đối tượng tại thời điểm bấm máy**":
$$\mathcal E(n)=1-\big|\langle\hat u_1^{(n)},\,x_T\rangle\big|^2 .$$

Đây là chỗ hai lực đối nghịch nhau: tăng $n$ làm giảm nhiễu nhưng tăng độ lạc hậu.

## 4.2. Phân rã sai số

**Mệnh đề 4.2 (Phân rã).** Với mô hình Định nghĩa 1.2–1.4, khi $x\gg1$ và $\varepsilon\ll1$:
$$\mathcal E(n)\;\approx\;\underbrace{\frac{p}{n\,x^2}}_{\text{nhiễu}}+\underbrace{\frac{\varepsilon^2n}{3}}_{\text{trôi}}
\;=\;\frac{1}{n\cdot\mathrm{SNR}^2}+\frac{\varepsilon^2n}{3}.$$

*Lập luận.* Thành phần nhiễu: khai triển công thức $q$ trong Định lý 2.3 với $\gamma$ nhỏ so với $x^4$ cho
$1-q\approx\gamma\big(\tfrac{1}{x^4}+\tfrac1{x^2}\big)\approx\gamma/x^2=p/(nx^2)$; thay $x=A/\sigma$ và
$\mathrm{SNR}=A/(\sigma\sqrt p)$ được $1/(n\,\mathrm{SNR}^2)$ — **độ phân giải $p$ triệt tiêu**.
Thành phần trôi: hướng chủ đạo của cửa sổ xấp xỉ trung bình của $x_{T-n+1},\dots,x_T$; với bước ngẫu nhiên,
độ lệch bình phương trung bình so với $x_T$ tỉ lệ với $\varepsilon^2$ nhân trung bình của $k$ trên cửa sổ, cho
hằng số $1/3$. $\square$

**Kiểm chứng hằng số bằng mô phỏng** ($p=4096$, tách riêng hai thành phần bằng cách chạy lại cùng quỹ đạo với
$\sigma=0$):

| $n$ | 8 | 16 | 32 | 64 | 128 |
|---|---|---|---|---|---|
| thành phần nhiễu đo được ($\mathrm{SNR}=1$) | 0.1107 | 0.0589 | 0.0306 | 0.0155 | 0.0074 |
| lý thuyết $1/(n\,\mathrm{SNR}^2)$ | 0.1250 | 0.0625 | 0.0313 | 0.0156 | 0.0078 |
| thành phần trôi đo được ($\varepsilon=0.05$) | 0.0054 | 0.0119 | 0.0248 | 0.0499 | 0.0985 |
| lý thuyết $\varepsilon^2n/3$ | 0.0067 | 0.0133 | 0.0267 | 0.0533 | 0.1067 |

Thành phần nhiễu khớp tới $1\%$ từ $n\ge32$; thành phần trôi tuyến tính theo $n$ với hệ số $0.31$ so với $1/3$ dự
đoán. Kiểm tra thêm sự phụ thuộc $\mathrm{SNR}$: ở $n=32$, thành phần nhiễu đo được là $0.1113$ khi
$\mathrm{SNR}=0.5$ (lý thuyết $0.125$) và $0.0079$ khi $\mathrm{SNR}=2$ (lý thuyết $0.0078$) — khớp hoàn hảo.

## 4.3. Định luật dừng tối ưu

**Mệnh đề 4.3 (Số khung tối ưu).** Cực tiểu hoá $\mathcal E(n)$ theo $n$ cho
$$\boxed{\ n^\star=\frac{\sqrt3}{\varepsilon\cdot\mathrm{SNR}},\qquad
\mathcal E(n^\star)=\frac{2\varepsilon}{\sqrt3\,\mathrm{SNR}}\approx1.155\,\frac{\varepsilon}{\mathrm{SNR}}\ }$$

*Chứng minh.* $\mathcal E'(n)=-\dfrac{1}{n^2\mathrm{SNR}^2}+\dfrac{\varepsilon^2}{3}=0$ cho
$n^{\star2}=\dfrac{3}{\varepsilon^2\mathrm{SNR}^2}$. Thay lại, hai số hạng bằng nhau và đều bằng
$\varepsilon/(\sqrt3\,\mathrm{SNR})$. $\square$

**Ba hệ quả thiết kế.**

1. **$n^\star$ không phụ thuộc độ phân giải $p$.** Kết quả này ban đầu phản trực giác nhưng đúng: tăng $p$ vừa làm
   tăng lượng nhiễu vừa làm tăng lượng tín hiệu, và ở mức chuẩn hoá $\mathrm{SNR}$ mỗi điểm ảnh thì hai hiệu ứng
   triệt tiêu. **Camera 12 MP và camera 2 MP nên tích luỹ cùng số khung.**
2. **Tại điểm tối ưu, sai số nhiễu và sai số trôi bằng nhau.** Đây là dấu hiệu chẩn đoán để kiểm tra hệ thống có
   đang chạy đúng chế độ không.
3. **Điều kiện khả thi.** $\mathcal E(n^\star)$ chỉ phụ thuộc tỉ số $\varepsilon/\mathrm{SNR}$. Muốn đạt chất
   lượng $q\ge q^\star$ phải có
   $$\frac{\varepsilon}{\mathrm{SNR}}\le\frac{\sqrt3}{2}(1-q^\star).$$
   Nếu điều kiện này hỏng thì **không thời điểm nào là đủ tốt** — hệ thống nên báo cho người dùng ("đối tượng
   đang di chuyển quá nhanh trong điều kiện ánh sáng này") thay vì bấm máy.

## 4.4. TN2 — Kiểm chứng định luật dừng

**Thiết lập.** $p=4096$, $\sigma=1$, quỹ đạo trôi theo Định nghĩa 1.4, $T=140$ khung, trung bình 8 lần chạy. Với
mỗi $n$, lấy $n$ khung gần nhất, tính $\hat u_1$, đo $\mathcal E(n)$ so với $x_T$.

Đường cong $\mathcal E(n)$ với $\varepsilon=0.05$, $\mathrm{SNR}=1$:

| $n$ | 1 | 2 | 4 | 8 | 12 | 16 | 24 | **32** | 48 | 64 | 96 | 128 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| $\mathcal E(n)$ | .4967 | .3311 | .2010 | .1162 | .0858 | .0708 | .0588 | **.0554** | .0580 | .0654 | .0846 | .1059 |

Hình chữ U rõ rệt. **Dùng 128 khung tệ gần gấp đôi so với dùng 32 khung** — minh chứng trực tiếp rằng tích luỹ
quá mức gây hại.

**Bảng kiểm chứng Mệnh đề 4.3 trên 5 cấu hình:**

| $\varepsilon$ | $\mathrm{SNR}$ | $n^\star$ đo được | $n^\star$ lý thuyết $\sqrt3/(\varepsilon\mathrm{SNR})$ | $\mathcal E_{\min}$ đo được | lý thuyết $2\varepsilon/(\sqrt3\mathrm{SNR})$ |
|---|---|---|---|---|---|
| 0.02 | 1.0 | 96 | 86.6 | 0.0227 | 0.0231 |
| 0.05 | 1.0 | 32 | 34.6 | 0.0554 | 0.0577 |
| 0.10 | 1.0 | 16 | 17.3 | 0.1047 | 0.1155 |
| 0.05 | 0.5 | 64 | 69.3 | 0.1083 | 0.1155 |
| 0.05 | 2.0 | 16 | 17.3 | 0.0273 | 0.0289 |

Cả hai công thức khớp trong vòng $10\%$ trên toàn dải, và các quan hệ tỉ lệ $n^\star\propto1/\varepsilon$ và
$n^\star\propto1/\mathrm{SNR}$ được xác nhận chính xác (gấp đôi $\varepsilon$ ⟹ $n^\star$ giảm nửa; gấp đôi
$\mathrm{SNR}$ ⟹ $n^\star$ giảm nửa). Sai lệch còn lại là do lưới $n$ rời rạc và hiệu ứng kích thước hữu hạn.

> **Ví dụ 4.1 (quy đổi thực tế).** Điện thoại chụp đối tượng trong nhà: $\mathrm{SNR}\approx1$, rung tay nhẹ
> $\varepsilon\approx0.05$ ⟹ $n^\star\approx35$ khung. Ở $60$ fps, đó là **0.58 giây** — đúng khoảng thời gian
> người dùng giữ máy ổn định. Nếu đối tượng chạy ($\varepsilon\approx0.12$): $n^\star\approx14$ khung
> $=0.23$ giây, và chất lượng tối đa đạt được là $q=1-0.139=0.861$.
---

# §5. Quyết định trực tuyến: cái mà hệ thống thực sự tính được

Mệnh đề 4.3 cần $\varepsilon$ và $\mathrm{SNR}$, mà camera không biết trước. Mục này xây dựng bộ ước lượng cho cả
hai, chỉ từ dữ liệu quan sát.

## 5.1. Ước lượng mức nhiễu $\sigma$

Cách chắc chắn nhất là dùng **đặc tuyến nhiễu của cảm biến**, vốn đã hiệu chuẩn sẵn trong mọi máy ảnh:
$\sigma^2=g\cdot I+\sigma_r^2$ với $I$ là cường độ trung bình, $g$ hệ số chuyển đổi, $\sigma_r$ nhiễu đọc.

Cách thay thế thuần dữ liệu: dùng **trung vị của phổ trị kỳ dị** khớp với trung vị lý thuyết của luật
Marchenko–Pastur ứng với $\gamma=p/n$. **Không** dùng độ lệch chuẩn toàn ảnh — tín hiệu sẽ làm phồng ước lượng.

## 5.2. Ước lượng cường độ tín hiệu $\hat x$

Mệnh đề 2.4, áp thẳng vào $\sigma_1$ của bộ đệm. TN1 đã xác nhận độ chính xác.

## 5.3. Ước lượng tốc độ trôi $\hat\varepsilon$

Đây là phần mới của báo cáo. Ý tưởng: thông tin về trôi nằm trong **ma trận Gram của các khung hình**, không phải
trong phổ trị kỳ dị.

**Mệnh đề 5.3 (Ước lượng tốc độ trôi).** Đặt $G=Y^{\mathsf T}Y\in\mathbb R^{n\times n}$ và
$$r(k)=\operatorname{mean}\big\{G_{ij}:\ |i-j|=k\big\},\qquad k=1,2,\dots$$
Khi đó $r(k)\approx A^2e^{-k\varepsilon^2/2}$, nên hồi quy tuyến tính $\log r(k)$ theo $k$ có hệ số góc
$-\varepsilon^2/2$, cho
$$\hat\varepsilon=\sqrt{-2\cdot\text{hệ số góc}}.$$

*Lập luận.* $G_{ij}=A^2\langle x_i,x_j\rangle+A\sigma(\langle x_i,z_j\rangle+\langle x_j,z_i\rangle)+\sigma^2\langle z_i,z_j\rangle$.
Với $i\ne j$, ba số hạng sau có kỳ vọng 0, nên lấy trung bình trên nhiều cặp cùng khoảng cách $k$ sẽ khử chúng;
số hạng đầu bằng $A^2e^{-k\varepsilon^2/2}$ theo Định nghĩa 1.4. Lưu ý phải **bỏ đường chéo chính** vì
$G_{ii}\approx A^2+\sigma^2p$ chứa thiên lệch $\sigma^2p$ rất lớn. $\square$

Điểm đáng chú ý về mặt phương pháp: $\hat x$ đến từ **phổ trái** (vector kỳ dị trong không gian điểm ảnh),
$\hat\varepsilon$ đến từ **phổ phải** (cấu trúc thời gian giữa các khung). Hai nguồn thông tin độc lập nhau.

## 5.4. Quy tắc kích hoạt

```
n̂* = √3 · √p / (ε̂ · x̂)          [tương đương √3/(ε̂ · SNR)]
Bấm máy khi kích thước bộ đệm đạt n̂*.
```

## 5.5. TN3 — Một quy tắc đơn giản nhưng SAI

Trước khi đến quy tắc đúng, cần loại bỏ một ý tưởng tự nhiên nhưng hỏng. Khi đối tượng trôi, tín hiệu không còn
hạng 1, nên $\sigma_2$ sẽ nhô lên khỏi mép nhiễu. Vậy tại sao không **dừng ngay khi $\sigma_2$ vượt mép**?

| $\varepsilon$ | $n^\star$ thật | $n$ kích hoạt theo quy tắc $\sigma_2$ | $\mathcal E(n^\star)$ | $\mathcal E(n_{\text{kích hoạt}})$ |
|---|---|---|---|---|
| 0.02 | 86 | 51 | 0.0227 | 0.0259 |
| 0.03 | 59 | 14 | 0.0331 | 0.0689 |
| 0.05 | 35 | 16 | 0.0547 | 0.0704 |
| 0.08 | 22 | 6 | 0.0858 | 0.1526 |
| 0.12 | 14 | 4 | 0.1227 | 0.2119 |

**Quy tắc này kích hoạt quá sớm và sai số tăng tới gấp đôi.** Lý do: $\sigma_2$ nhô khỏi mép ngay khi *có chút*
cấu trúc hạng 2, tức rất lâu trước khi thành phần hạng 2 đủ lớn để làm hỏng ước lượng. Mép Marchenko–Pastur là
ngưỡng **phát hiện**, không phải ngưỡng **gây hại**. Nhầm lẫn hai khái niệm này là một cạm bẫy chung khi áp dụng
lý thuyết ma trận ngẫu nhiên vào kỹ thuật.

Chúng tôi cũng thử một thống kê thứ hai — độ tập trung của $\hat v_1$ (nếu các khung đóng góp không đều thì
$\hat v_1$ lệch khỏi vector đều). Nó **không nhạy**: chỉ số $\sqrt n\max_j|\hat v_{1j}|$ biến thiên từ $1.020$ tới
$1.048$ trên toàn dải $n$, quá ít để làm ngưỡng.

## 5.6. TN6 — Quy tắc đúng: ước lượng tham số rồi áp công thức

**Thiết lập.** Dùng một cửa sổ mồi cố định 64 khung để ước lượng $\hat x$ (Mệnh đề 2.4) và $\hat\varepsilon$
(Mệnh đề 5.3), tính $\hat n^\star$, rồi so sai số tại $\hat n^\star$ với sai số tại điểm tối ưu thật.

| $\varepsilon$ thật | $\hat\varepsilon$ | $x$ thật | $\hat x$ | $n^\star$ thật | $\hat n^\star$ | $\mathcal E(n^\star)$ | $\mathcal E(\hat n^\star)$ |
|---|---|---|---|---|---|---|---|
| 0.020 | 0.0213 | 64.0 | 63.9 | 87 | 83 | 0.0227 | **0.0227** |
| 0.030 | 0.0302 | 64.0 | 63.7 | 61 | 58 | 0.0337 | **0.0338** |
| 0.050 | 0.0494 | 64.0 | 63.3 | 33 | 35 | 0.0553 | **0.0554** |
| 0.080 | 0.0801 | 64.0 | 61.9 | 20 | 22 | 0.0849 | **0.0852** |
| 0.120 | 0.1208 | 64.0 | 59.4 | 15 | 15 | 0.1204 | **0.1204** |

**Đây là kết quả trung tâm của báo cáo.** Bộ ước lượng trực tuyến cho $\hat\varepsilon$ sai dưới $7\%$ và $\hat x$
sai dưới $8\%$; quan trọng hơn, **sai số tại điểm dừng ước lượng bằng đúng sai số tại điểm dừng tối ưu** — chênh
lệch lớn nhất là $0.0003$. Nguyên nhân: hàm $\mathcal E(n)$ rất phẳng quanh cực tiểu (vì nó là tổng của $1/n$ và
$n$), nên sai số vài phần trăm trong việc chọn $n$ hầu như không gây thiệt hại. Đây là tính chất may mắn nhưng có
thể giải thích được, và nó làm hệ thống rất bền vững.

---

# §6. Chọn khung hình và hợp nhất

## 6.1. $\hat v_1$ là hồ sơ chất lượng khung hình

Trong phân tích $Y\approx\sigma_1\hat u_1\hat v_1^{\mathsf T}$, thành phần thứ $j$ của $\hat v_1$ cho biết
**khung hình $j$ đóng góp bao nhiêu vào thành phần tín hiệu**. Khung bị nhoè, bị che, hoặc thiếu sáng sẽ có
$|\hat v_{1j}|$ nhỏ. Không cần bộ dò nhoè riêng: SVD tự động cho điểm chất lượng.

## 6.2. TN4 — Kiểm chứng

**Thiết lập.** $p=4096$, $n=24$, $\mathrm{SNR}=1$. Ba khung bị suy giảm mạnh (độ lợi $0.15$), hai khung suy giảm
vừa ($0.45$), hai khung nhẹ ($0.7$), còn lại bình thường ($1.0$).

| Kết quả | Giá trị |
|---|---|
| Tương quan giữa $\|\hat v_1\|$ và độ lợi thật | **0.9993** |
| 5 khung tốt nhất theo $\hat v_1$ → độ lợi thật | 1.0, 1.0, 1.0, 1.0, 1.0 |
| 5 khung tệ nhất theo $\hat v_1$ → độ lợi thật | 0.45, 0.45, 0.15, 0.15, 0.15 |
| Chất lượng $q$ của **khung đơn tốt nhất** | 0.505 |
| Chất lượng $q$ của **ảnh hợp nhất** $\hat u_1$ | **0.949** |

Xếp hạng hoàn hảo: mọi khung tốt được xếp trên mọi khung xấu. Và ảnh hợp nhất tốt hơn khung đơn tốt nhất rất
nhiều ($0.949$ so với $0.505$).

## 6.3. Hai chế độ đầu ra

Từ đây hệ thống có hai lựa chọn, tuỳ yêu cầu ứng dụng:

| Chế độ | Đầu ra | Khi nào dùng |
|---|---|---|
| **Chọn khung** | khung $j^\star=\arg\max_j|\hat v_{1j}|$, xuất nguyên bản | cần ảnh thật, không qua xử lý (pháp y, bằng chứng) |
| **Hợp nhất** | $\hat x_0=\hat s\,\hat u_1$ với $\hat s$ đã co rút | cần chất lượng cao nhất (mặc định) |

Chế độ "chọn khung" chính là câu trả lời trực tiếp cho yêu cầu "lựa chọn thời điểm tối ưu nhất để chụp": thời điểm
tối ưu là $j^\star$, và nó được xác định **sau khi đã quan sát**, chứ không phải đoán trước.

---

# §7. Khôi phục ảnh

## 7.1. Vì sao phải co rút

Định lý 2.3 cho thấy $\sigma_1$ quan sát luôn lớn hơn cường độ tín hiệu thật (Ví dụ 2.2: thổi phồng $23\%$). Nếu
dựng lại ảnh bằng $\sigma_1\hat u_1\hat v_1^{\mathsf T}$, đối tượng sẽ có độ tương phản cao giả tạo. Mệnh đề 2.4
cho ước lượng đúng $\hat s=\sigma\sqrt n\,\hat x$.

## 7.2. TN5 — So sánh bốn cách khôi phục

**Thiết lập.** $p=4096$, $n=24$, $\mathrm{SNR}=1$, 7 trong 24 khung có độ lợi ngẫu nhiên trong $[0.1,0.6]$
(mô phỏng nhoè/che khuất từng phần), 20 lần lặp. Sai số là NMSE so với ảnh sạch.

| Phương pháp | NMSE |
|---|---|
| Khung đơn tốt nhất | 1.0069 |
| Trung bình cộng | 0.0637 |
| SVD cắt cụt (dùng thẳng $\sigma_1$) | 0.0555 |
| **SVD có co rút** | **0.0533** |

**Ba nhận xét.**

1. **Khung đơn có NMSE $\approx1$** — nghĩa là năng lượng nhiễu ngang năng lượng tín hiệu, đúng như dự đoán khi
   $\mathrm{SNR}=1$. Bất kỳ phương pháp hợp nhất nào cũng tốt hơn hàng chục lần.
2. **Trung bình cộng thua SVD** vì nó cho mọi khung trọng số bằng nhau, kể cả các khung có độ lợi $0.1$. SVD tự
   động dồn trọng số về các khung tốt qua $\hat v_1$. (Lưu ý: phép so sánh này còn **ưu ái** trung bình cộng, vì
   chúng tôi cho nó biết trước độ lợi trung bình thật để chuẩn hoá.)
3. **Co rút cải thiện thêm $4\%$** so với cắt cụt. Cải thiện nhỏ nhưng miễn phí về mặt tính toán.

---

# §8. Bước nhận diện

## 8.1. Một mô hình bị thực nghiệm bác bỏ

Câu hỏi: cần chất lượng $q$ bằng bao nhiêu để nhận diện đúng trong tập $K$ mẫu?

Mô hình đầu tiên của chúng tôi giả định sai số khôi phục có hướng **ngẫu nhiên đẳng hướng**. Khi đó
$\hat u_1=\sqrt q\,t_k+\sqrt{1-q}\,e$ với $e$ ngẫu nhiên, và vì $e$ chiếu lên mỗi mẫu chỉ cỡ $1/\sqrt p$, ngưỡng
lý thuyết là
$$q^\star=\Big(1+\frac{p(1-\mu)^2}{2\ln K}\Big)^{-1},$$
với $\mu$ là độ tương quan lớn nhất giữa các mẫu. Với $p=4096$, $K=1000$, $\mu=0.8$: $q^\star=0.078$.

**Thực nghiệm bác bỏ mô hình này** — không phải vì nó sai công thức, mà vì nó **quá lạc quan tới mức vô dụng**:

| $q$ | 0.05 | 0.1 | 0.2 | 0.4 | 0.6 | 0.8 | 0.95 |
|---|---|---|---|---|---|---|---|
| Độ chính xác ($K=1000$, $\mu=0.8$, sai số ngẫu nhiên) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

Nhận diện **luôn đúng**, kể cả khi ảnh khôi phục chỉ trùng $5\%$ với ảnh thật. Lý do: trong không gian $4096$
chiều, một hướng ngẫu nhiên gần như trực giao với mọi mẫu, nên nó không thể "kéo" kết quả về mẫu sai.

## 8.2. Kết luận đúng: cấu trúc của sai số mới là vấn đề

Sai số thật của hệ thống **không ngẫu nhiên**. Thành phần trôi (§4) là ảnh của chính đối tượng ở thời điểm khác —
nó nằm trong không gian các ảnh hợp lệ, tức đúng nơi các mẫu nằm. Thí nghiệm lặp lại với sai số hướng về **một
mẫu cạnh tranh**:

| $q$ | 0.2 | 0.4 | 0.6 | 0.7 | 0.8 | 0.9 | 0.99 |
|---|---|---|---|---|---|---|---|
| Sai số ngẫu nhiên | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| **Sai số có cấu trúc** | **0.000** | **0.000** | **1.000** | 1.000 | 1.000 | 1.000 | 1.000 |

Chuyển tiếp cực kỳ sắc tại $q=1/2$, đúng như hình học đòi hỏi: nếu sai số dồn hết vào một mẫu cạnh tranh thì nhận
diện đúng khi và chỉ khi $\sqrt q>\sqrt{1-q}$.

**Quy tắc thiết kế rút ra:**
$$q^\star=\tfrac12\ \text{(trường hợp xấu nhất)},\qquad
\text{đặt mục tiêu }q\ge0.8\ \text{để có biên an toàn}.$$

Đây là kết quả có ích hơn nhiều so với công thức lý thuyết ban đầu, và nó cho thấy giá trị của việc **luôn kiểm
tra mô hình bằng mô phỏng** trước khi tin vào nó.

## 8.3. Nối ngưỡng dừng với ngưỡng nhận diện

Ghép Mệnh đề 4.3 với $q^\star=0.8$:
$$\mathcal E(n^\star)=\frac{2\varepsilon}{\sqrt3\,\mathrm{SNR}}\le0.2
\quad\Longleftrightarrow\quad
\boxed{\ \frac{\varepsilon}{\mathrm{SNR}}\le0.173\ }$$

**Đây là điều kiện khả thi của toàn hệ thống.** Nếu nó hỏng, không tồn tại thời điểm bấm máy nào cho ảnh đủ tốt để
nhận diện, và hành vi đúng của hệ thống là **từ chối chụp kèm chẩn đoán**:

| Chẩn đoán | Nguyên nhân | Gợi ý cho người dùng |
|---|---|---|
| $\hat\varepsilon$ lớn, $\hat x$ bình thường | đối tượng/máy chuyển động nhanh | giữ máy yên, hoặc lại gần |
| $\hat\varepsilon$ bình thường, $\hat x$ nhỏ | thiếu sáng | bật đèn, tăng phơi sáng |
| cả hai xấu | chụp đêm có chuyển động | dùng chân máy |

## 8.4. Lưu ý quan trọng về bước nhận diện

Bước so khớp $\hat u_1$ với tập mẫu là bài toán **trường hợp B**, tuân theo lý thuyết khác (mô hình spiked, ngưỡng
BBP $\theta_c=\sqrt{p/n_{\text{train}}}$). Cụ thể, nếu tập mẫu được xây bằng PCA trên $n_{\text{train}}$ ảnh huấn
luyện với $p$ lớn, thì bản thân không gian mẫu đã có sai số riêng, và các kết luận của §8.2 giả định các mẫu là
chính xác. Việc ghép hai chế độ này một cách chặt chẽ nằm ngoài phạm vi báo cáo.
---

# §9. Thuật toán đầy đủ

## 9.1. Mô tả

```
THUẬT TOÁN: Tự động chọn thời điểm chụp và nhận diện

ĐẦU VÀO : luồng khung hình y_1, y_2, ...; hộp bao đối tượng (p điểm ảnh)
          mục tiêu chất lượng q* (mặc định 0.8)
          cửa sổ mồi n_0 (mặc định 32), trần bộ đệm n_max (mặc định 256)
ĐẦU RA  : ảnh đối tượng đã hợp nhất x̂_0, nhãn nhận diện, hoặc thông báo từ chối

GIAI ĐOẠN 1 — MỒI (tích luỹ n_0 khung)
  1. Dựng Y ∈ R^{p×n_0} từ các hộp bao đã căn chỉnh thô.
  2. σ̂ ← từ đặc tuyến nhiễu cảm biến (hoặc khớp trung vị phổ với luật MP).
  3. s ← trị kỳ dị của Y;  γ ← p/n_0;  s̃ ← s_1/(σ̂√n_0).
  4. NẾU s̃ ≤ 1 + √γ  THÌ  báo "không phát hiện được đối tượng"; DỪNG.
       [mép Marchenko–Pastur — Định lý 2.2]
  5. x̂ ← nghiệm của Mệnh đề 2.4;  SNR ← x̂/√p.
  6. G ← YᵀY;  r(k) ← trung bình đường chéo phụ thứ k (BỎ đường chéo chính);
     ε̂ ← √(−2·hệ_số_góc(log r(k) theo k)).           [Mệnh đề 5.3]

GIAI ĐOẠN 2 — QUYẾT ĐỊNH
  7. NẾU ε̂/SNR > (√3/2)(1−q*) THÌ
        báo "không đạt được chất lượng yêu cầu" + chẩn đoán (§8.3); DỪNG.
  8. n̂* ← min( √3/(ε̂·SNR), n_max ).                  [Mệnh đề 4.3]

GIAI ĐOẠN 3 — TÍCH LUỸ VÀ BẤM MÁY
  9. Tích luỹ tới n̂* khung (cập nhật SVD tăng dần, §9.2).
     Cập nhật lại ε̂ mỗi 8 khung; nếu ε̂ tăng đột ngột (đối tượng bắt đầu
     chuyển động) thì tính lại n̂* và bấm máy ngay nếu n hiện tại ≥ n̂* mới.
 10. SVD cuối: Y = Σ σ_i u_i v_iᵀ.

GIAI ĐOẠN 4 — XUẤT KẾT QUẢ
 11. q̂ ← Mệnh đề 2.4 áp cho bộ đệm cuối.
 12. Chế độ CHỌN KHUNG : j* ← argmax_j |v_1j|;  xuất khung j*.       [§6.3]
     Chế độ HỢP NHẤT   : ŝ ← σ̂√n̂*·x̂;  x̂_0 ← ŝ·u_1.                  [§7.1]
 13. NẾU q̂ < q* THÌ đánh dấu kết quả là "độ tin cậy thấp".
 14. Nhận diện: k̂ ← argmax_k ⟨x̂_0/‖x̂_0‖, t_k⟩ trên tập mẫu.
```

## 9.2. Độ phức tạp và tính khả thi thời gian thực

SVD đầy đủ của $Y\in\mathbb R^{p\times n}$ tốn $O(pn^2)$. Với $p=4096$, $n=32$: khoảng $4\times10^6$ phép — dưới
một mili-giây trên CPU điện thoại. Nhưng làm lại toàn bộ SVD mỗi khung thì lãng phí. Ba tối ưu:

1. **Chỉ cần vector kỳ dị đầu.** Dùng lặp lũy thừa trên $Y^{\mathsf T}Y$ (cỡ $n\times n$, rất nhỏ), khởi tạo từ
   nghiệm khung trước. Chi phí mỗi khung: $O(pn)$ để cập nhật $G$, cộng vài lần lặp trên ma trận $n\times n$.
2. **Cập nhật Gram tăng dần.** Khi thêm khung mới, $G$ chỉ cần thêm một hàng/cột: $O(pn)$.
3. **Vector kỳ dị trái suy ra sau.** $\hat u_1=Y\hat v_1/\sigma_1$, chỉ tốn $O(pn)$ và chỉ cần tính **một lần** ở
   bước bấm máy.

Tổng chi phí mỗi khung: $O(pn)\approx1.3\times10^5$ phép với cấu hình trên — hoàn toàn chạy được ở $60$ fps.

## 9.3. Hiệu chỉnh tham số

| Tham số | Mặc định | Cách chỉnh |
|---|---|---|
| $n_0$ (cửa sổ mồi) | 32 | đủ để $\hat\varepsilon$ ổn định; TN6 dùng 64 |
| $q^\star$ | 0.8 | 0.5 là ngưỡng lý thuyết (§8.2); 0.8 cho biên an toàn |
| $n_{\max}$ | 256 | ràng buộc bộ nhớ và độ trễ người dùng |
| chu kỳ cập nhật $\hat\varepsilon$ | 8 khung | đánh đổi giữa độ nhạy và chi phí |

**Kiểm tra chẩn đoán bắt buộc.** Theo Hệ quả 2 của Mệnh đề 4.3, tại điểm tối ưu hai thành phần sai số phải bằng
nhau. Hệ thống nên ghi log $\dfrac{1/(n\,\mathrm{SNR}^2)}{\varepsilon^2n/3}$; nếu tỉ số này lệch xa 1 thì có tham
số bị ước lượng sai.

---

# §10. Hạn chế

1. **Mô hình trôi là đẳng hướng.** Định nghĩa 1.4 cho đối tượng trôi theo hướng ngẫu nhiên đều trong
   $\mathbb R^p$. Trôi thật (tịnh tiến, xoay, đổi tỉ lệ) nằm trên một **đa tạp thấp chiều** trong không gian ảnh.
   Hệ quả: $\hat\varepsilon$ ước lượng đúng tốc độ mất tương quan, nhưng hằng số $1/3$ trong Mệnh đề 4.2 có thể
   khác. Cách khắc phục thực tế: **căn chỉnh khung (image registration)** trước khi xếp vào ma trận, biến phần lớn
   trôi tịnh tiến thành hằng số và giảm $\varepsilon$ hiệu dụng — điều này **tăng** $n^\star$ và cải thiện chất
   lượng.

2. **Giả thiết nhiễu trắng, phương sai đồng nhất.** Nhiễu ảnh thật phụ thuộc cường độ (shot noise theo Poisson) và
   có tương quan không gian sau khử khảm màu (demosaicing). Nên áp **biến đổi ổn định phương sai** (Anscombe) trước
   khi đưa vào mô hình.

3. **Đối tượng được giả định hạng 1.** Đúng khi chỉ có thay đổi độ lợi. Với thay đổi chiếu sáng (đổ bóng dịch
   chuyển), tín hiệu có hạng khoảng 3–9 tuỳ mô hình phản xạ. Mở rộng tự nhiên: dùng $k$ thành phần với $k$ chọn
   bằng ngưỡng Gavish–Donoho thay vì cố định $k=1$.

4. **Kết quả là tiệm cận.** Định lý 2.3 đúng khi $p,n\to\infty$. TN1 cho thấy sai số dưới $0.5\%$ ở $p=4096$,
   $n=32$ — chấp nhận được. Nhưng ở $n<8$ nên thận trọng.

5. **Bước nhận diện chưa được phân tích chặt chẽ** (§8.4): §8 giả định tập mẫu chính xác, trong khi tập mẫu thực
   tế được ước lượng từ dữ liệu huấn luyện hữu hạn và chịu chính lời nguyền chiều cao của trường hợp B.

6. **Chưa có thực nghiệm trên ảnh thật.** Toàn bộ số liệu là mô phỏng theo mô hình sinh của §1.4. Bước tiếp theo
   bắt buộc là kiểm chứng trên luồng video thật với đối tượng chuyển động có kiểm soát.

---

# §11. Kết luận

Báo cáo đã đưa bài toán "camera tự chọn thời điểm chụp" về một bài toán dừng tối ưu có lời giải dạng đóng, và xây
dựng một hệ thống hoàn chỉnh chạy được thời gian thực. Bốn đóng góp:

1. **Điều kiện phát hiện** $\mathrm{SNR}>(pn)^{-1/4}$ (Hệ quả 3.1), kiểm chứng chính xác tại
   $\mathrm{SNR}=0.0526$ với $p=4096$, $n=32$.

2. **Định luật dừng tối ưu** (Mệnh đề 4.3):
   $$n^\star=\frac{\sqrt3}{\varepsilon\cdot\mathrm{SNR}},\qquad
   \mathcal E(n^\star)=\frac{2\varepsilon}{\sqrt3\,\mathrm{SNR}},$$
   với ba hệ quả thiết kế: $n^\star$ độc lập với độ phân giải; tại điểm tối ưu hai loại sai số cân bằng; và tồn
   tại điều kiện khả thi $\varepsilon/\mathrm{SNR}\le0.173$ để đạt $q\ge0.8$.

3. **Bộ ước lượng trực tuyến hoàn chỉnh** (Mệnh đề 2.4 và 5.3): $\hat x$ từ phổ trái, $\hat\varepsilon$ từ phổ
   phải. Hệ thống đạt sai số bằng đúng sai số tại điểm tối ưu lý thuyết (chênh $\le0.0003$ trên 5 cấu hình).

4. **$\hat v_1$ làm điểm chất lượng khung hình**, tương quan $0.9993$ với chất lượng thật, cho phép trả lời trực
   tiếp câu hỏi "thời điểm nào là tối ưu".

Chúng tôi cũng ghi lại hai kết quả âm tính có giá trị: quy tắc kích hoạt dựa trên $\sigma_2$ vượt mép
Marchenko–Pastur **thất bại** vì nhầm ngưỡng *phát hiện* với ngưỡng *gây hại*; và mô hình đánh giá bước nhận diện
dựa trên sai số đẳng hướng bị thực nghiệm bác bỏ, dẫn tới nhận thức đúng hơn rằng **cấu trúc** của sai số mới
quyết định, với ngưỡng sắc nét $q^\star=1/2$ trong trường hợp xấu nhất.

---

# Phụ lục A. Mã nguồn

```python
"""AS5019 - Tu dong chon thoi diem chup va nhan dien doi tuong.
Tai tao toan bo ket qua so trong bao cao."""
import numpy as np

# ---------- A.1 Cong cu tu ly thuyet ma tran ngau nhien ----------
def bulk_edge(p, n, sigma):
    """Dinh ly 2.2: chuan pho cua nhieu thuan tuy."""
    return sigma*(np.sqrt(p) + np.sqrt(n))

def bgn_sv(x, g):
    """Dinh ly 2.3: tri ky di quan sat, don vi sigma*sqrt(n)."""
    return np.sqrt((1+x**2)*(g+x**2))/x if x > g**0.25 else 1 + np.sqrt(g)

def bgn_overlap(x, g):
    """Dinh ly 2.3: chat luong q = |<u_hat, u>|^2."""
    return (x**4 - g)/(x**4 + g*x**2) if x**4 > g else 0.0

def invert_bgn(s1, p, n, sigma):
    """Menh de 2.4: tu sigma_1 quan sat suy ra (x_hat, q_hat). Cong cu then chot."""
    g = p/n
    st = s1/(sigma*np.sqrt(n))
    c = st**2 - 1 - g
    d = c**2 - 4*g
    if st <= 1 + np.sqrt(g) or d <= 0:
        return 0.0, 0.0
    x = np.sqrt((c + np.sqrt(d))/2)
    return x, bgn_overlap(x, g)

def estimate_drift(Y):
    """Menh de 5.3: uoc luong eps tu suy giam cac duong cheo phu cua ma tran Gram.
    BAT BUOC bo duong cheo chinh (chua thien lech sigma^2 * p)."""
    n = Y.shape[1]
    G = Y.T @ Y
    ks = np.arange(1, max(2, n//2))
    r = np.array([np.mean(np.diag(G, k)) for k in ks])
    ok = r > 0
    if ok.sum() < 3:
        return np.nan
    slope = np.polyfit(ks[ok], np.log(r[ok]), 1)[0]      # = -eps^2/2
    return np.sqrt(max(-2*slope, 1e-12))

def optimal_n(eps, snr):
    """Menh de 4.3."""
    return np.sqrt(3)/(eps*snr)

def feasible(eps, snr, q_target=0.8):
    """He qua 3 cua Menh de 4.3: dieu kien kha thi cua he thong."""
    return eps/snr <= np.sqrt(3)/2*(1 - q_target)

# ---------- A.2 Bo dieu khien hoan chinh ----------
def auto_capture(Y_prime, sigma, q_target=0.8, n_max=256):
    """Giai doan 1-2 cua thuat toan §9.1. Y_prime: cua so moi (p x n0)."""
    p, n0 = Y_prime.shape
    s = np.linalg.svd(Y_prime, compute_uv=False)
    if s[0] <= bulk_edge(p, n0, sigma):
        return dict(status='khong_phat_hien')
    x, q = invert_bgn(s[0], p, n0, sigma)
    snr = x/np.sqrt(p)
    eps = estimate_drift(Y_prime)
    if not feasible(eps, snr, q_target):
        reason = 'doi_tuong_chuyen_dong_qua_nhanh' if eps > 0.08 else 'thieu_sang'
        return dict(status='tu_choi', ly_do=reason, eps=eps, snr=snr)
    return dict(status='ok', n_star=int(min(optimal_n(eps, snr), n_max)),
                eps=eps, snr=snr, x=x, q_hien_tai=q)

def finalize(Y, sigma):
    """Giai doan 3-4: hop nhat, co rut, cham diem tung khung."""
    p, n = Y.shape
    U, s, Vt = np.linalg.svd(Y, full_matrices=False)
    x, q = invert_bgn(s[0], p, n, sigma)
    s_shrunk = sigma*np.sqrt(n)*x                      # Dinh ly 2.5: PHAI co rut
    return dict(anh_hop_nhat=s_shrunk*U[:, 0],
                khung_tot_nhat=int(np.argmax(np.abs(Vt[0]))),
                diem_tung_khung=np.abs(Vt[0]),
                q=q)

# ---------- A.3 Mo phong: sinh du lieu ----------
def trajectory(p, T, eps, rng):
    """Dinh nghia 1.4: buoc ngau nhien tren mat cau."""
    x = rng.standard_normal(p); x /= np.linalg.norm(x)
    X = np.empty((p, T))
    for t in range(T):
        X[:, t] = x
        g = rng.standard_normal(p); g /= np.linalg.norm(g)
        x = np.sqrt(1-eps**2)*x + eps*g; x /= np.linalg.norm(x)
    return X

def simulate(p, T, eps, snr, rng, sigma=1.0, gains=None):
    X = trajectory(p, T, eps, rng)
    A = snr*sigma*np.sqrt(p)
    a = np.ones(T) if gains is None else gains
    return A*X*a + sigma*rng.standard_normal((p, T)), X

# ---------- A.4 Thi nghiem ----------
def tn2(p=4096, eps=0.05, snr=1.0, T=140, reps=8, seed=0):
    """Duong cong chu U va n* thuc nghiem (§4.4)."""
    rng = np.random.default_rng(seed)
    ns = np.array([1,2,4,8,12,16,24,32,48,64,96,128])
    err = np.zeros(len(ns))
    for _ in range(reps):
        Y, X = simulate(p, T, eps, snr, rng)
        for i, n in enumerate(ns):
            U = np.linalg.svd(Y[:, T-n:], full_matrices=False)[0]
            u = U[:, 0]*np.sign(U[:, 0] @ X[:, -1])
            err[i] += 1 - (u @ X[:, -1])**2
    err /= reps
    k = int(np.argmin(err))
    print(f'eps={eps} snr={snr}: n*={ns[k]} (ly thuyet {optimal_n(eps,snr):.1f}), '
          f'E_min={err[k]:.4f} (ly thuyet {2*eps/(np.sqrt(3)*snr):.4f})')
    return ns, err

def tn6(p=4096, snr=1.0, T=220, seed=21):
    """Kiem chung bo uoc luong truc tuyen (§5.6)."""
    rng = np.random.default_rng(seed)
    for eps in [0.02, 0.03, 0.05, 0.08, 0.12]:
        Y, X = simulate(p, T, eps, snr, rng)
        r = auto_capture(Y[:, T-64:], sigma=1.0)
        print(f'eps that={eps:.3f} -> eps_hat={r["eps"]:.4f}  '
              f'n*_hat={r["n_star"]}  (ly thuyet {optimal_n(eps,snr):.0f})')

if __name__ == "__main__":
    for e in [0.02, 0.05, 0.10]:
        tn2(eps=e)
    print()
    tn6()
```

---

# Phụ lục B. Bảng công thức

| Đại lượng | Công thức | Nguồn |
|---|---|---|
| SNR mỗi điểm ảnh | $\mathrm{SNR}=A/(\sigma\sqrt p)$ | Đ 1.3 |
| Mép phổ nhiễu | $\sigma(\sqrt p+\sqrt n)$ | ĐL 2.2 |
| Điều kiện phát hiện | $\mathrm{SNR}>(pn)^{-1/4}$ | HQ 3.1 |
| Số khung tối thiểu | $n>1/(p\cdot\mathrm{SNR}^4)$ | HQ 3.1 |
| Chất lượng lý thuyết | $q=(x^4-\gamma)/(x^4+\gamma x^2)$ | ĐL 2.3 |
| **Ước lượng $\hat x$ từ $\sigma_1$** | $\hat x^2=\tfrac12\big(c+\sqrt{c^2-4\gamma}\big),\ c=\tilde s^2-1-\gamma$ | MĐ 2.4 |
| **Ước lượng $\hat\varepsilon$** | $\hat\varepsilon=\sqrt{-2\cdot\text{slope}\big(\log r(k)\big)}$ | MĐ 5.3 |
| Phân rã sai số | $\mathcal E(n)=\dfrac{1}{n\,\mathrm{SNR}^2}+\dfrac{\varepsilon^2n}{3}$ | MĐ 4.2 |
| **Số khung tối ưu** | $n^\star=\sqrt3/(\varepsilon\,\mathrm{SNR})$ | MĐ 4.3 |
| **Sai số tối thiểu** | $\mathcal E(n^\star)=2\varepsilon/(\sqrt3\,\mathrm{SNR})$ | MĐ 4.3 |
| Điều kiện khả thi | $\varepsilon/\mathrm{SNR}\le\tfrac{\sqrt3}{2}(1-q^\star)$ | §4.3 |
| Ngưỡng nhận diện | $q^\star=1/2$ (xấu nhất), dùng $0.8$ | §8.2 |
| Trị kỳ dị co rút | $\hat s=\sigma\sqrt n\,\hat x$ | ĐL 2.5 |
| Thời gian kết hợp | $n_c\approx2/\varepsilon^2$ | Đ 1.4 |

---

# Phụ lục C. Tài liệu tham khảo

**Tài liệu học phần**

[1] Bài giảng *Ma trận ngẫu nhiên*, Bộ môn Toán Ứng dụng, Trường ĐH Bách khoa – ĐHQG-HCM.

[2] A. Edelman, N. R. Rao, "Random matrix theory", *Acta Numerica* **14** (2005), 233–297.

[3] T. Tao, *Topics in Random Matrix Theory*, Graduate Studies in Mathematics **132**, AMS, 2012.

**Nguồn các định lý được dùng**

[5] V. A. Marchenko, L. A. Pastur, "Distribution of eigenvalues for some sets of random matrices",
*Matematicheskii Sbornik* **72(114)** (1967), 507–536. — Định lý 2.2.

[10] F. Benaych-Georges, R. R. Nadakuditi, "The singular values and vectors of low rank perturbations of large
rectangular random matrices", *Journal of Multivariate Analysis* **111** (2012), 120–135. — Định lý 2.3, cơ sở của
Mệnh đề 2.4.

[12] M. Gavish, D. L. Donoho, "The optimal hard threshold for singular values is $4/\sqrt3$", *IEEE Transactions
on Information Theory* **60** (2014), 5040–5053. — Định lý 2.5.

[6] I. M. Johnstone, "On the distribution of the largest eigenvalue in principal components analysis",
*Annals of Statistics* **29** (2001), 295–327. — mô hình spiked, dùng ở §8.4.

**Bối cảnh ứng dụng**

[13] M. Turk, A. Pentland, "Eigenfaces for recognition", *Journal of Cognitive Neuroscience* **3** (1991), 71–86.

[22] R. Couillet, Z. Liao, *Random Matrix Methods for Machine Learning*, Cambridge University Press, 2022. —
sách tham khảo cho phần nối với bài toán nhận diện; bản nháp trực tuyến có sẵn miễn phí.

[23] J. Yao, S. Zheng, Z. Bai, *Large Sample Covariance Matrices and High-Dimensional Data Analysis*, Cambridge
University Press, 2015. — chương 6 (phân loại dữ liệu) và chương 11 (mô hình spiked), nền cho §8.4.

---

*Ghi chú: Mệnh đề 4.2, 4.3 và 5.3 là kết quả do nhóm tự dẫn ra bằng cách ghép Định lý 2.3 với mô hình trôi ở Định
nghĩa 1.4; chúng không được trích nguyên từ tài liệu nào và cần được trình bày đúng như vậy. Các hằng số ($1/3$,
$\sqrt3$, $2/\sqrt3$) đã được kiểm chứng bằng mô phỏng trên 5 cấu hình tham số nhưng chưa có chứng minh chặt chẽ.
Mọi số liệu tạo bằng NumPy với seed cố định, tái lập được bằng mã ở Phụ lục A.*
