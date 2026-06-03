# Đặc tả tích hợp card “Đường quay lại”

## 1. Mục tiêu của card

Thêm một card mới trong bảng chọn `Ctrl+Shift+T`:

```text
ĐƯờng quay lại
```

Card này mô phỏng cách robot quay lại khi bị mặt kẹt trong quá trình tìm đường đến đích, cho phép
1) Chọn lại đường cũ để quay lại
2) CHọn theo thuật toán quay lại khác: dựa trên bài báo **“Multiple shooting approach for finding approximately shortest paths for autonomous robots in unknown environments in 2D”**.

Ý tưởng chính:

> Robot di chuyển trong môi trường chưa biết, chỉ có tầm nhìn hữu hạn. Trong quá trình khám phá, robot có thể cần quay lại một điểm đã đánh dấu trước đó. Thay vì quay lại theo đường trên graph $G$, ứng dụng dựng một dãy **bó đoạn thẳng** và dùng **MMS — Multiple Shooting Method** để tìm một đường quay lại ngắn hơn.

Bài báo nêu rõ rằng robot có tầm nhìn hữu hạn, tránh vật cản đa giác, và khi cần quay lại các vị trí đã đánh dấu, vùng robot từng đi qua được mô hình hóa thành **sequences of bundles of line segments**; MMS được dùng để tìm đường ngắn xấp xỉ theo các bó đoạn này.

---

# 2. Vị trí trong UI

Hiện `Ctrl+Shift+T` mở `TransformChooserDialog`, sau đó `MainWindow._run_transform_feature()` định tuyến theo `feature.key`. Các chức năng hiện có cùng dùng quy ước: chọn chức năng, quét vùng nếu cần, lăn chuột để thay đổi tham số/thời gian, `Esc` để chốt, `Delete` để huỷ và phục hồi phiên.

Thiết kế mới là bảng card trực quan. Card MMS đặt trong nhóm **Robot tìm đường**:

```text
Ctrl+Shift+T — Chọn mô phỏng

Ảnh & biến đổi
[ Biến đổi ảnh f(z) ]        [ Một chất điểm chuyển động ]

Robot chuyển động
[ Nhiều robot chuyển động ]

Robot tìm đường
[ A* — bản đồ đã biết        ] [ Dijkstra — bản đồ đã biết ]
[ A* quét dần bằng LiDAR     ] [ D* quét dần bằng LiDAR    ]
[ D* Lite quét dần bằng LiDAR]
[ MMS — tối ưu đường quay lại]
```

Card mới không nằm dưới cây con nào. Người dùng bấm vào card là chạy luôn.

---

# 3. Nội dung card

## Tên card

```text
MMS — tối ưu đường quay lại
```

## Mô tả ngắn

```text
Robot có tầm nhìn hữu hạn; khi cần quay lại điểm đã đánh dấu, dùng MMS để thay đường graph bằng đường ngắn hơn.
```

## Badge

```text
Bản đồ chưa biết
Bó đoạn thẳng
Bài báo 2024
```

## Key kỹ thuật

```python
key = "path_unknown_mms_bundles"
path_mode = "unknown"
algorithm = "mms_bundles"
```

---

# 4. Ảnh minh họa trên card

Card này bắt buộc có ảnh minh họa riêng, vì người dùng cuối khó hiểu “MMS” nếu chỉ đọc chữ.

Ảnh minh họa nên có:

```text
- Điểm p: điểm đã đánh dấu trước đó.
- Điểm q: vị trí robot hiện tại.
- Đường quay lại trên graph G: nét đứt đỏ.
- Các bó đoạn thẳng: chùm đoạn màu tím tại các điểm a_i.
- Đường MMS: nét liền xanh lá, ngắn hơn đường đỏ.
- Vòng tròn tầm nhìn quanh robot q.
```

Mẫu trực quan:

```text
p ● - - - a1 - - - a2 - - - q      đường đỏ nét đứt: graph G
 \        | \      | \      /
  \       |  \     |  \    /
   ───────●───●────●────●          các bó đoạn màu tím

đường xanh lá: đường MMS ngắn hơn
```

Gợi ý hàm vẽ icon:

```python
def draw_icon_mms_bundles(p: QPainter, r: QRectF):
    # 1. Vẽ nền lưới mờ.
    # 2. Vẽ vài đa giác vật cản màu xám nhạt.
    # 3. Vẽ p và q.
    # 4. Vẽ trajectory graph G bằng nét đứt đỏ.
    # 5. Vẽ các bundle: chùm đoạn tím tại a_i.
    # 6. Vẽ đường MMS bằng nét liền xanh lá.
    # 7. Vẽ vòng tròn tầm nhìn quanh q.
    # 8. Thêm nhãn nhỏ "MMS".
```

---

# 5. Luồng người dùng

Khi người dùng bấm card:

```text
1. Chọn card “MMS — tối ưu đường quay lại”.
2. Khoanh robot hoặc chọn robot từ ảnh/vùng.
3. Nhấp điểm đích cuối cùng.
4. Khoanh vùng môi trường 2D.
5. Ứng dụng nhận diện vật cản trong vùng bản đồ.
6. Robot mô phỏng quá trình khám phá với tầm nhìn hữu hạn.
7. Tại mỗi vị trí, ứng dụng hiển thị:
   - vùng nhìn thấy,
   - open sights,
   - closed sights,
   - open points,
   - rank của open points,
   - graph G.
8. Khi robot cần quay lại một điểm p đã đánh dấu nhưng p không nằm trong vùng nhìn hiện tại:
   - tìm đường quay lại trên graph G,
   - hiển thị đường graph bằng nét đứt đỏ,
   - dựng dãy bó đoạn thẳng dọc đường này,
   - chạy MMS,
   - hiển thị đường MMS bằng nét liền xanh lá.
9. Lăn chuột để chạy mô phỏng theo tham số t.
10. Shift + lăn để đi chậm từng bước.
11. Esc để chốt trạng thái.
12. Delete để huỷ và phục hồi slide trước phiên.
```

Điểm khác với D* Lite: D* Lite cập nhật đường trên grid khi phát hiện vật cản mới; card MMS mô phỏng riêng cơ chế trong bài báo: **limited vision → open/closed sights → open points → graph G → đường quay lại → bó đoạn thẳng → MMS shortcut**.

---

# 6. Các lớp hiển thị trên canvas

Card MMS cần các overlay riêng, không nên dùng chung hoàn toàn với `_path_*` của A*/D*/D* Lite.

## 6.1. Vùng nhìn thấy

Bài báo dùng vùng nhìn của robot là hình tròn (B(a, r)) tâm tại vị trí hiện tại $a$, bán kính $r$.

Hiển thị:

```python
self._mms_vision_layer
```

Màu:

```python
QColor(0, 180, 255, 45)   # cyan nhạt
```

---

## 6.2. Open sights và closed sights

Bài báo phân biệt:

```text
open sights   : hướng robot có thể đi tiếp
closed sights : hướng cảnh báo va chạm hoặc cụt
```

Hiển thị:

```python
self._mms_open_sight_layer
self._mms_closed_sight_layer
```

Màu:

```python
MMS_COLORS = {
    "open_sight": QColor(0, 200, 80, 70),
    "closed_sight": QColor(255, 80, 160, 80),
}
```

---

## 6.3. Open points và rank

Mỗi open sight có một open point. Bài báo xếp hạng open point theo khoảng cách đến goal và góc giữa hướng đi tới open point với hướng đi tới goal; trong phần triển khai, $\alpha = \beta = 1$.

Hiển thị:

```text
- Chấm vàng tại mỗi open point.
- Rank nhỏ bên cạnh.
- Open point được chọn: viền cam hoặc màu nổi bật.
```

State:

```python
self._mms_open_points = []
self._mms_selected_open_point = None
```

---

## 6.4. Graph $G$

Graph $G$ lưu thông tin địa phương robot đã biết: các node là tâm robot đã đi qua và đầu mút các sight; cạnh là các đoạn bán kính. Khi cần quay lại, robot tìm đường trên graph $G$, nhưng đường này thường dài hơn đường MMS.

Hiển thị:

```text
Graph G: nét mảnh xám
Đường quay lại trên graph G: nét đứt đỏ
```

State:

```python
self._mms_graph_nodes = []
self._mms_graph_edges = []
self._mms_graph_return_path = []
```

---

## 6.5. Dãy bó đoạn thẳng

Đây là lớp quan trọng nhất.

Một bundle có dạng:

```text
{[a, b1], [a, b2], ..., [a, bm]}
```

Các đoạn cùng chung đỉnh $a$. Bài toán MMS là tìm đường ngắn đi qua một dãy bó đoạn thẳng theo thứ tự.

Hiển thị:

```text
Bundle: chùm đoạn tím
Cutting segments: tím đậm
Shooting points: chấm vàng hoặc đen
```

State:

```python
self._mms_bundles = []
self._mms_cutting_segments = []
self._mms_shooting_points = []
```

---

## 6.6. Đường MMS

Hiển thị kết quả chính:

```text
Đường graph G: đỏ nét đứt
Đường MMS: xanh lá nét liền
```

State:

```python
self._mms_optimized_path = []
```

---

# 7. Màu hiển thị đề xuất

```python
MMS_COLORS = {
    "vision": QColor(0, 180, 255, 45),
    "open_sight": QColor(0, 200, 80, 70),
    "closed_sight": QColor(255, 80, 160, 80),
    "open_point": QColor(255, 210, 0, 230),
    "selected_open_point": QColor(255, 140, 0, 255),
    "graph_edge": QColor(90, 90, 90, 110),
    "graph_return": QColor(220, 40, 40, 220),
    "bundle": QColor(150, 70, 220, 150),
    "cutting_segment": QColor(100, 30, 180, 230),
    "shooting_point": QColor(20, 20, 20, 230),
    "mms_path": QColor(0, 180, 80, 240),
}
```

---

# 8. Cấu trúc `TransformFeature`

Thêm card vào danh sách card:

```python
TransformFeature(
    key="path_unknown_mms_bundles",
    title="MMS — tối ưu đường quay lại",
    subtitle="Dùng Multiple Shooting để thay đường quay lại trên graph bằng đường ngắn hơn.",
    category="Robot tìm đường",
    icon_kind="mms_bundles",
    path_mode="unknown",
    algorithm="mms_bundles",
    badges=("Bản đồ chưa biết", "Bó đoạn", "Bài báo 2024"),
    recommended=False,
    default_options={
        "vision_radius": 10,
        "alpha": 1.0,
        "beta": 1.0,
        "bundle_partition_size": 5,
        "max_iterations": 100,
        "tolerance": 1e-4,
        "show_vision": True,
        "show_open_closed_sights": True,
        "show_open_points": True,
        "show_graph": True,
        "show_available_trajectory": True,
        "show_bundles": True,
        "show_cutting_segments": True,
        "show_shooting_points": True,
        "show_mms_path": True,
        "show_length_history": True,
    },
)
```

Trong `_run_transform_feature()`:

```python
def _run_transform_feature(self, feature):
    if feature.key == "path_unknown_mms_bundles":
        return self._run_path_planning_mms_bundles(
            options=feature.default_options,
        )
```

---

# 9. Tuỳ chọn nâng cao trên card

Bấm thân card: chạy ngay với mặc định.

Bấm nút `⚙`: mở dialog tuỳ chọn nâng cao.

Các tuỳ chọn nên có:

```text
Tầm nhìn robot
- Bán kính nhìn thấy r

Ranking open point
- alpha
- beta

MMS
- Kích thước phân hoạch bundle c
- Sai số dừng epsilon
- Số vòng lặp tối đa
- Hiện shooting points
- Hiện cutting segments
- Hiện từng bước cập nhật MMS
- Hiện biểu đồ độ dài theo iteration

Hiển thị
[x] Vùng nhìn thấy
[x] Open sights / closed sights
[x] Open points + rank
[x] Graph G
[x] Đường quay lại trên graph
[x] Dãy bó đoạn thẳng
[x] Đường MMS
```

Mặc định nên dùng:

```python
vision_radius = 10
alpha = 1.0
beta = 1.0
bundle_partition_size = 5
max_iterations = 100
tolerance = 1e-4
```

Trong phần thí nghiệm của bài báo, tác giả dùng phân hoạch đều với $c=5$; $c=6$ cũng được thử nhưng kết quả tổng thể không khác đáng kể.

---

# 10. Module lõi cần thêm

Không nên nhét toàn bộ vào `core.path_planning.py`, vì MMS có nhiều khái niệm hình học riêng.

Đề xuất thêm 2 file:

```text
core/
├── path_planning.py              # A*, Dijkstra, repeated A*, D* Lite
├── local_visibility_planning.py  # open/closed sights, open points, graph G
└── mms_bundles.py                # thuật toán MMS theo bài báo
```

Hiện tài liệu dự án đã phân tách các service trong `core/` theo từng trách nhiệm độc lập, nên cách tách này phù hợp với kiến trúc hiện có.

---

# 11. `core/local_visibility_planning.py`

File này xử lý phần robot tầm nhìn hữu hạn.

## Dataclass

```python
@dataclass
class SightSector:
    center: QPointF
    radius: float
    start_angle: float
    end_angle: float
    kind: Literal["open", "closed"]
    open_point: QPointF | None = None


@dataclass
class OpenPoint:
    point: QPointF
    rank: float
    distance_to_goal: float
    angle_to_goal: float
    parent_center: QPointF


@dataclass
class VisibilityStep:
    center: QPointF
    open_sights: list[SightSector]
    closed_sights: list[SightSector]
    open_points: list[OpenPoint]
    selected_open_point: OpenPoint | None
```

## Hàm chính

```python
def compute_sights(
    position: QPointF,
    radius: float,
    polygon_obstacles: list[QPolygonF],
) -> tuple[list[SightSector], list[SightSector]]:
    ...


def compute_open_points(
    open_sights: list[SightSector],
) -> list[QPointF]:
    ...


def rank_open_points(
    open_points: list[QPointF],
    position: QPointF,
    goal: QPointF,
    alpha: float = 1.0,
    beta: float = 1.0,
) -> list[OpenPoint]:
    ...


def update_visibility_graph(
    graph: VisibilityGraph,
    step: VisibilityStep,
) -> None:
    ...


def select_next_open_point(
    open_points: list[OpenPoint],
) -> OpenPoint | None:
    ...
```

---

# 12. `core/mms_bundles.py`

File này xử lý bài toán hình học MMS.

## Dataclass

```python
@dataclass
class Segment:
    a: QPointF
    b: QPointF


@dataclass
class Bundle:
    vertex: QPointF
    segments: list[Segment]


@dataclass
class MMSProblem:
    p: QPointF
    q: QPointF
    bundles: list[Bundle]


@dataclass
class MMSIteration:
    index: int
    shooting_points: list[QPointF]
    path: list[QPointF]
    length: float
    converged: bool


@dataclass
class MMSResult:
    path: list[QPointF]
    shooting_points: list[QPointF]
    cutting_segments: list[Segment]
    iterations: int
    converged: bool
    length_history: list[float]
    iteration_history: list[MMSIteration]
```

## Hàm chính

```python
def construct_bundles_from_return_trajectory(
    trajectory: list[QPointF],
    sight_history: list[VisibilityStep],
    radius: float,
) -> list[Bundle]:
    ...


def preprocess_bundles(
    bundles: list[Bundle],
    trajectory: list[QPointF],
) -> list[Bundle]:
    ...


def solve_mms_shortest_path(
    p: QPointF,
    q: QPointF,
    bundles: list[Bundle],
    partition_size: int = 5,
    max_iterations: int = 100,
    tolerance: float = 1e-4,
) -> MMSResult:
    ...
```

---

# 13. Thuật toán MMS cần triển khai

Bài báo mô tả MMS theo 3 yếu tố:

```text
1. Chia dãy bundle thành các đoạn con và chọn cutting segments.
2. Tạo đường qua các shooting points.
3. Kiểm tra điều kiện thẳng hàng; nếu chưa đạt, cập nhật shooting points.
```

Nếu điều kiện thẳng hàng thỏa tại tất cả shooting points thì thu được đường ngắn đúng; nếu không, dãy độ dài đường sau các bước cập nhật hội tụ.

Pseudo-code triển khai:

```python
def solve_mms_shortest_path(
    p: QPointF,
    q: QPointF,
    bundles: list[Bundle],
    partition_size: int = 5,
    max_iterations: int = 100,
    tolerance: float = 1e-4,
) -> MMSResult:
    # 1. Partition bundles into sub-sequences
    partitions, cutting_segments = partition_bundles(
        bundles,
        partition_size=partition_size,
    )

    # 2. Initial shooting points
    shooting_points = init_shooting_points(
        p=p,
        q=q,
        cutting_segments=cutting_segments,
    )

    history = []

    for iteration in range(max_iterations):
        # 3. Build current path from shooting points
        current_path = build_path_from_shooting_points(
            shooting_points=shooting_points,
            partitions=partitions,
        )

        current_length = polyline_length(current_path)

        # 4. Compute next shooting points
        next_points = update_shooting_points(
            shooting_points=shooting_points,
            partitions=partitions,
            cutting_segments=cutting_segments,
        )

        # 5. Check collinear / convergence condition
        max_delta = max(
            distance(a, b)
            for a, b in zip(shooting_points, next_points)
        )

        converged = max_delta < tolerance

        history.append(
            MMSIteration(
                index=iteration,
                shooting_points=shooting_points,
                path=current_path,
                length=current_length,
                converged=converged,
            )
        )

        if converged:
            return MMSResult(
                path=current_path,
                shooting_points=shooting_points,
                cutting_segments=cutting_segments,
                iterations=iteration + 1,
                converged=True,
                length_history=[h.length for h in history],
                iteration_history=history,
            )

        shooting_points = next_points

    return MMSResult(
        path=current_path,
        shooting_points=shooting_points,
        cutting_segments=cutting_segments,
        iterations=max_iterations,
        converged=False,
        length_history=[h.length for h in history],
        iteration_history=history,
    )
```

Trong bài báo, Algorithm 1 khởi tạo shooting points, tạo path hiện tại, gọi `Collinear_Update`, rồi dừng nếu điều kiện thẳng hàng thỏa; nếu chưa, cập nhật path và lặp lại.

---

# 14. Tiền xử lý bundle

Cần có bước `preprocess_bundles(...)` trước khi gọi MMS.

Mục tiêu:

```text
- Giữ lại bundle nằm trong sector có góc không vượt quá π.
- Rút ngắn / xử lý để hai bundle khác nhau không giao nhau.
- Đảm bảo đường tìm được tránh vật cản.
```

Bài báo có Procedure `Preprocessing(F*)` để biến dãy bundle ban đầu thành dãy bundle không giao nhau; Proposition 5 khẳng định dãy thu được có các bundle phân biệt không giao nhau và đường ngắn theo dãy đó tránh vật cản.

---

# 15. Pha khám phá môi trường

Luồng thuật toán cấp cao:

```python
def run_mms_robot_planning(start, goal, obstacles, options):
    a = start
    G = VisibilityGraph()
    OP = []
    P = [start]

    while True:
        if reached(a, goal):
            return P

        open_sights, closed_sights = compute_sights(
            position=a,
            radius=options.vision_radius,
            polygon_obstacles=obstacles,
        )

        open_points = compute_open_points(open_sights)

        ranked_open_points = rank_open_points(
            open_points=open_points,
            position=a,
            goal=goal,
            alpha=options.alpha,
            beta=options.beta,
        )

        ranked_open_points = filter_seen_open_points(
            ranked_open_points,
            G,
        )

        G.add_sights(a, open_sights, closed_sights)
        OP.extend(ranked_open_points)

        anext = select_next_open_point(OP)

        if anext is None:
            return None

        if not inside_vision(anext.point, a, options.vision_radius):
            return_path = shortest_path_in_graph(G, a, anext.point)

            bundles = construct_bundles_from_return_trajectory(
                trajectory=return_path,
                sight_history=sight_history,
                radius=options.vision_radius,
            )

            bundles = preprocess_bundles(
                bundles=bundles,
                trajectory=return_path,
            )

            mms_result = solve_mms_shortest_path(
                p=anext.point,
                q=a,
                bundles=bundles,
                partition_size=options.bundle_partition_size,
                max_iterations=options.max_iterations,
                tolerance=options.tolerance,
            )

            P.extend(mms_result.path)
            a = anext.point
        else:
            P.append(anext.point)
            a = anext.point

        OP.remove(anext)
```

Đây là phiên bản triển khai theo tinh thần Algorithm 2 của bài báo: tại mỗi vị trí, robot lấy open/closed sights, thêm open points vào tập (OP), chọn open point rank cao nhất, tìm đường trên graph $G$ khi cần quay lại, dựng dãy bundle và gọi MMS.

---

# 16. State trên canvas

Không dùng chung hoàn toàn `_astar_*`. Tạo nhóm state riêng:

```python
self._mms_motion_active = False
self._mms_phase = None

self._mms_robot_pixmap = None
self._mms_start_pos = None
self._mms_goal_pos = None
self._mms_current_pos = None
self._mms_vision_radius = 10

self._mms_truth_obstacles = []
self._mms_sight_history = []
self._mms_open_points = []
self._mms_selected_open_point = None

self._mms_visibility_graph = None
self._mms_graph_return_path = []

self._mms_bundles = []
self._mms_cutting_segments = []
self._mms_shooting_points = []
self._mms_optimized_path = []
self._mms_iteration_history = []
self._mms_length_history = []

self._mms_t = 0.0
self._mms_iteration_view = 0
self._mms_backup = None
```

Hiện canvas đã có nhiều state machine riêng cho các phiên `Ctrl+Shift+T`, gồm single transform, multi-robot, A*/Dijkstra; tất cả dùng chung quy ước `Esc` chốt và `Delete` huỷ. Vì vậy thêm state machine riêng cho MMS là phù hợp.

---

# 17. Pha hoạt động của MMS

Dùng biến:

```python
self._mms_phase = "capture_robot"
```

Các pha:

```text
capture_robot
capture_goal
capture_map
explore
return_graph
build_bundles
mms_optimize
move_mms
finished
```

Ý nghĩa:

```text
capture_robot  : khoanh robot.
capture_goal   : nhấp goal.
capture_map    : khoanh vùng bản đồ.
explore        : robot đi theo open points.
return_graph   : hiển thị đường quay lại trên graph G.
build_bundles  : hiển thị dãy bó đoạn thẳng.
mms_optimize   : hiển thị từng vòng lặp MMS.
move_mms       : robot chạy theo đường MMS.
finished       : chờ Esc/Delete hoặc kết thúc.
```

---

# 18. Điều khiển bằng tham số `t`

Lăn chuột tăng/giảm `self._mms_t`.

Trong pha `explore`:

```text
t tăng
→ robot đi tới open point được chọn
→ vùng nhìn thấy cập nhật
→ open/closed sights xuất hiện
→ graph G mở rộng
```

Trong pha `return_graph`:

```text
t tăng
→ đường graph G đỏ nét đứt hiện dần
```

Trong pha `build_bundles`:

```text
t tăng
→ các bundle tím xuất hiện dần theo thứ tự
```

Trong pha `mms_optimize`:

```text
t tăng hoặc Shift+lăn
→ xem từng iteration MMS
→ shooting points cập nhật
→ length giảm dần
```

Trong pha `move_mms`:

```text
t tăng
→ robot di chuyển theo đường MMS xanh lá
```

---

# 19. Hàm vẽ overlay

Thêm vào canvas:

```python
def _draw_mms_overlays(self, painter: QPainter):
    if not self._mms_motion_active:
        return

    if self._mms_show_vision:
        self._draw_mms_vision(painter)

    if self._mms_show_open_closed_sights:
        self._draw_mms_open_closed_sights(painter)

    if self._mms_show_open_points:
        self._draw_mms_open_points(painter)

    if self._mms_show_graph:
        self._draw_mms_graph(painter)

    if self._mms_show_available_trajectory:
        self._draw_mms_graph_return_path(painter)

    if self._mms_show_bundles:
        self._draw_mms_bundles(painter)

    if self._mms_show_cutting_segments:
        self._draw_mms_cutting_segments(painter)

    if self._mms_show_shooting_points:
        self._draw_mms_shooting_points(painter)

    if self._mms_show_mms_path:
        self._draw_mms_optimized_path(painter)

    if self._mms_show_length_history:
        self._draw_mms_length_history_label(painter)

    self._draw_mms_robot_pose(painter)
```

Gọi trong `_draw_full` sau `_draw_element_overlays(...)`, trước floating image / selection overlay.

Canvas hiện render theo thứ tự: nền, lưới, `_stroke_pixmap`, element overlays, rồi các lớp tương tác; vì vậy overlay MMS nên nằm sau element overlays để người dùng thấy rõ mô phỏng, nhưng chưa bake vào slide cho đến khi `Esc`.

---

# 20. Không paint trực tiếp vào `_stroke_pixmap` khi đang chạy

Trong khi phiên MMS đang active, chỉ dùng overlay tạm. Khi `Esc` mới bake kết quả nếu cần.

Lý do: theo quy ước hiện có, `Delete` phải huỷ phiên và phục hồi slide trước phiên. Ngoài ra tài liệu maintenance cũng nhấn mạnh không nên phá lifecycle ảnh nổi và các thao tác canvas hiện có.

Khi `Esc`:

```python
def _mms_commit(self):
    if self._mms_show_graph:
        self._bake_mms_graph_if_needed()

    if self._mms_show_bundles:
        self._bake_mms_bundles_if_needed()

    if self._mms_show_mms_path:
        self._bake_mms_path_to_slide()

    self._commit_mms_robot_pose()
    self._clear_mms_session()
```

Khi `Delete`:

```python
def _mms_cancel(self):
    if self._mms_backup is not None:
        self._restore_mms_backup()

    self._clear_mms_session()
    self.update()
```

---

# 21. Bản đồ và vật cản

Bài báo làm việc với vật cản đa giác. Vì vậy card MMS nên ưu tiên pipeline polygon thay vì chỉ occupancy grid.

Giai đoạn đầu có thể dùng cách thực dụng:

```text
vùng bản đồ người dùng khoanh
→ lấy pixmap
→ trích contour vật cản bằng OpenCV
→ xấp xỉ contour thành polygon
→ dùng polygon để tính open/closed sights
```

Hàm đề xuất:

```python
def extract_obstacle_polygons_from_map_pixmap(
    pixmap: QPixmap,
    map_lasso: QPainterPath,
    simplify_epsilon: float = 2.0,
) -> list[QPolygonF]:
    ...
```

---

# 22. Giai đoạn triển khai khuyến nghị

## Giai đoạn 1 — UI card + ảnh minh họa

Mục tiêu: card xuất hiện và bấm được.

Việc làm:

```text
- Thêm card “MMS — tối ưu đường quay lại”.
- Thêm icon_kind = "mms_bundles".
- Vẽ ảnh minh họa bằng QPainter.
- Thêm nhánh trong `_run_transform_feature()`.
- Khi click, tạm hiển thị thông báo hoặc chạy demo giả.
```

---

## Giai đoạn 2 — Demo thủ công MMS

Mục tiêu: kiểm thử thuật toán MMS trước khi tự động hóa robot visibility.

Luồng demo:

```text
- Người dùng khoanh/chọn robot q.
- Người dùng nhấp điểm p cần quay lại.
- Người dùng vẽ hoặc chọn polyline đỏ làm đường graph G.
- App dựng bundle đơn giản quanh các đỉnh polyline.
- Chạy MMS.
- Hiển thị đường xanh ngắn hơn.
```

Giai đoạn này giúp kiểm tra:

```text
- dựng bundle,
- partition,
- cutting segments,
- shooting points,
- MMS iteration,
- hiển thị length history.
```

---

## Giai đoạn 3 — Tự động hóa visibility

Mục tiêu: mô phỏng phần open/closed sights.

Việc làm:

```text
- Trích obstacle polygon từ vùng bản đồ.
- Tính vùng nhìn B(a, r).
- Phân loại open sights / closed sights.
- Sinh open points.
- Tính rank.
- Tạo graph G.
```

---

## Giai đoạn 4 — Tự động gọi MMS khi quay lại

Mục tiêu: hoàn thiện đúng tinh thần bài báo.

Việc làm:

```text
- Khi robot chọn một open point p không nằm trong vùng nhìn hiện tại:
    + tìm đường q → p trên graph G,
    + hiển thị đường đỏ nét đứt,
    + dựng bundles theo trajectory này,
    + preprocess bundles,
    + chạy MMS,
    + hiển thị đường xanh,
    + cho robot đi theo đường MMS.
```

---

## Giai đoạn 5 — Hiển thị từng iteration MMS

Mục tiêu: tăng giá trị dạy học.

Việc làm:

```text
- Lưu iteration_history.
- Shift + wheel tua từng iteration.
- Hiển thị shooting points tại iteration k.
- Hiển thị length k.
- Hiển thị mini chart độ dài giảm dần.
```

---

# 23. Cập nhật tài liệu

## `shortcuts.md`

Dòng hiện tại của `Ctrl+Shift+T` vẫn mô tả robot tìm đường A*. Cần cập nhật vì bảng card sẽ có thêm A*/D*/D* Lite và MMS.

Câu mới:

```text
Ctrl+Shift+T | Mở bảng chọn chức năng dạng hộp: biến đổi ảnh f(z),
một chất điểm, nhiều robot, A*/Dijkstra với bản đồ đã biết,
A*/D*/D* Lite với bản đồ chưa biết quét dần bằng LiDAR,
và MMS — tối ưu đường quay lại theo dãy bó đoạn thẳng.
Shift+lăn để tinh chỉnh; Esc chốt, Delete huỷ.
```

## `complex-transform.md`

Thêm mục:

```text
## MMS — tối ưu đường quay lại

Key: path_unknown_mms_bundles

Mô phỏng thuật toán trong bài báo “Multiple shooting approach for finding
approximately shortest paths for autonomous robots in unknown environments in 2D”.

Robot có tầm nhìn hữu hạn, lưu open points và graph G. Khi cần quay lại một điểm
đã đánh dấu ngoài vùng nhìn hiện tại, app dựng dãy bó đoạn thẳng và dùng MMS
để thay đường quay lại trên graph bằng đường ngắn hơn.
```

---

# 24. Checklist nghiệm thu

## UI

```text
[ ] Card “MMS — tối ưu đường quay lại” xuất hiện trong nhóm Robot tìm đường.
[ ] Card có ảnh minh họa riêng: graph đỏ, bundle tím, MMS xanh.
[ ] Click card chạy workflow.
[ ] Nút ⚙ mở tuỳ chọn nâng cao.
[ ] Card không nằm trong cây phân cấp.
```

## Canvas lifecycle

```text
[ ] Lăn chuột điều khiển tham số t.
[ ] Shift+lăn đi chậm từng bước.
[ ] Esc chốt trạng thái.
[ ] Delete huỷ và phục hồi slide.
[ ] Đổi tool/đổi slide không làm mất trạng thái bất ngờ.
```

## Visibility

```text
[ ] Vẽ được vòng nhìn B(a, r).
[ ] Phân biệt open sights và closed sights.
[ ] Sinh open points.
[ ] Hiển thị rank.
[ ] Chọn open point có rank cao nhất.
```

## Graph G

```text
[ ] Lưu được node và edge của graph G.
[ ] Hiển thị graph G bằng nét xám.
[ ] Khi cần quay lại, tìm được đường trên graph G.
[ ] Đường quay lại graph hiển thị bằng nét đứt đỏ.
```

## Bundle + MMS

```text
[ ] Dựng được dãy bundles từ đường quay lại.
[ ] Preprocess để các bundle khác nhau không giao nhau.
[ ] Chọn cutting segments.
[ ] Khởi tạo shooting points.
[ ] Cập nhật shooting points qua từng iteration.
[ ] Dừng khi sai số nhỏ hơn tolerance.
[ ] Lưu length_history.
[ ] Hiển thị đường MMS xanh lá.
```

## So sánh trực quan

```text
[ ] Người dùng thấy rõ đường graph đỏ dài hơn.
[ ] Người dùng thấy rõ đường MMS xanh ngắn hơn.
[ ] Có label độ dài graph path và MMS path.
[ ] Có thể bật/tắt graph, bundles, shooting points, MMS path.
```

---