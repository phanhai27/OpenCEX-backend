<p align="center">
  <a href="https://polygant.net/opencex/" target="_blank">
    <img alt="OpenCEX Logo" width="500" src="https://github.com/Polygant/OpenCEX/blob/master/logo.png">
  </a>
</p>

<p align="center">
OpenCEX is a free and open source cryptocurrency exchange platform.<br>
Developed by <a href="https://polygant.net" target="_blank">Polygant</a>.  

<p align="center">
<a href="https://polygant.notion.site/OpenCEX-Help-Center-8cf8c842bde947c3818a615a88ceef9c" target="_blank">OpenCEX documentation</a> | <a href="https://t.me/opencex" target="_blank">Telegram chat</a>
</p>

> [!CAUTION]
> This repository is not maintained.  
> The code is provided as-is.

<p align="center"><b>Please go to the main repo to install OpenCEX <a href="https://github.com/Polygant/OpenCEX/">https://github.com/Polygant/OpenCEX/</a></b></p>

## Can I hire you guys?

OpenCEX was created and backed by Polygant, and is supported through all the years. You can request a consultation or order web and mobile development services by Polygant, just visit our site. 😎

Say hi: [hello@polygant.net](mailto:hello@polygant.net) . We will be happy to work with you!

## License
Apache License, Version 2.0

---

## 📚 KIẾN TRÚC & HƯỚNG DẪN MÔ PHỎNG LONG / SHORT (FUTURES EXCHANGE)
> *Tài liệu hướng dẫn đào tạo sinh viên về kiến trúc mở rộng từ sàn Spot sang Phái sinh (Futures).*

### 1. Bản Đồ Vị Trí Các Module Phái Sinh Mới

| Module / Thành phần | Vị trí File trong Backend | Nhiệm vụ Kiến trúc (Sinh viên học được gì) |
| :--- | :--- | :--- |
| **Matching Engine** | `core/orderbook/futures_book.py` | Sổ lệnh phái sinh, thuật toán khớp Long/Short, tính Margin, Giá thanh lý và Lãi/Lỗ (PnL) trên RAM. |
| **Worker Khớp Lệnh** | `bin/futures_stack.py` | Celery Worker độc lập (`concurrency=1`), lấy khóa phân tán `FuturesStackLock` trên Redis và nạp vị thế từ DB vào RAM. |
| **Background Tasks** | `core/tasks/futures.py` | 4 Celery tasks cốt lõi: Nhận lệnh (`place_futures_order`), Quét thanh lý (`check_liquidations`), Oracle giá (`update_mark_price`), Tính phí Funding (`settle_funding_rate`). |
| **Market Maker Bot** | `bots/futures_mm.py` | Bot tạo thanh khoản mồi: tự động treo 2 nhánh Bid (Long) và Ask (Short) quanh giá tham chiếu Mark Price. |
| **WebSocket Notifier** | `exchange/futures_notifications.py` | Đẩy dữ liệu thời gian thực ra giao diện: Cập nhật vị thế/PnL cho user, nhịp giá Mark Price và cảnh báo cháy vị thế. |
| **Master Simulation** | `bin/run_futures_simulation.py` | Script All-in-One chạy kịch bản hoàn chỉnh qua 6 giai đoạn để sinh viên quan sát toàn bộ vòng đời lệnh Futures. |

---

### 2. Hướng Dẫn Chạy Thử Nghiệm Mô Phỏng (Console / Log)

Sinh viên đứng tại thư mục `backend/` và thực thi các câu lệnh:

#### a. Chạy Toàn Bộ Vòng Đời Lệnh Futures (Khuyến nghị):
```bash
python3 bin/run_futures_simulation.py
```
> **Kịch bản tự động diễn ra qua 6 giai đoạn với log màu trực quan**:
> * **Giai đoạn 1**: Worker `futures_stack.py` khởi động, acquire Distributed Lock trên Redis.
> * **Giai đoạn 2**: Bot MM treo thanh khoản Short ở giá 65,032.50 USDT.
> * **Giai đoạn 3**: Trader đặt Long x20 $\rightarrow$ Khớp lệnh $\rightarrow$ Tạo `Position` $\rightarrow$ Bắn WebSocket PnL.
> * **Giai đoạn 4**: Oracle cập nhật giá tăng lên 66,500 $\rightarrow$ Bắn WebSocket PnL xanh (+45.13% ROE).
> * **Giai đoạn 5**: Celery Beat 8h kích hoạt trừ phí Funding Rate cấn trừ giữa 2 phe.
> * **Giai đoạn 6**: Thị trường rơi tự do xuống 61,900 $\rightarrow$ Liquidation Worker phát hiện chạm ngưỡng cháy $\rightarrow$ Ép bán đóng vị thế.

#### b. Chạy Thử Nghiệm Độc Lập Từng Module:
* **Kiểm tra thuật toán khớp lệnh & tính Margin**:
  ```bash
  python3 core/orderbook/futures_book.py
  ```
* **Kiểm tra quy trình khởi động Worker Khớp lệnh**:
  ```bash
  python3 bin/futures_stack.py --pairs=BTC-USDT-PERP
  ```
* **Kiểm tra các Celery Tasks nền (Quét thanh lý & Funding)**:
  ```bash
  python3 core/tasks/futures.py
  ```
* **Kiểm tra Bot tạo thanh khoản MM**:
  ```bash
  python3 bots/futures_mm.py
  ```
* **Kiểm tra Bộ phát tin WebSocket**:
  ```bash
  python3 exchange/futures_notifications.py
  ```

---

### 3. Sơ Đồ Tóm Tắt Điểm Nối Giữa Code Cũ và Code Mới (Bridging Map)

Sơ đồ dưới đây minh họa chi tiết cách mà các file hệ thống CŨ bắt tay và kích hoạt các module MỚI:

```mermaid
flowchart TD
    Client["Trader / Web Client"]

    subgraph APILayer["1. Tầng API (Định tuyến & Tiếp nhận)"]
        OldUrls["core/api_urls/orders.py (CŨ)\n[Đăng ký url: futures/orders/]"]
        NewView["core/views/futures.py (MỚI)\n[FuturesOrdersView tiếp nhận lệnh]"]
    end

    subgraph BrokerLayer["2. Tầng Broker & Lập Lịch (Celery)"]
        OldCelery["exchange/celery_app.py (CŨ)\n[Cấu hình Queues & Beat Schedule]"]
        NewTasks["core/tasks/futures.py (MỚI)\n[place_futures_order, liquidation, funding]"]
        QueueFutures[("Queue: futures.orders.<PAIR>")]
    end

    subgraph WorkerLayer["3. Tầng Matching Worker Độc Lập"]
        NewWorker["bin/futures_stack.py (MỚI)\n[Celery Worker concurrency=1 & Redis Lock]"]
        NewBook["core/orderbook/futures_book.py (MỚI)\n[OrderBook & Matching Engine trên RAM]"]
    end

    subgraph AccountingLayer["4. Tầng Kế Toán & Giao Dịch"]
        OldTx["core/models/inouts/transaction.py (CŨ)\n[Ghi nhận mã REASON_FUTURES_*]"]
    end

    subgraph RealtimeLayer["5. Tầng Realtime WebSocket"]
        NewWS["exchange/futures_notifications.py (MỚI)\n[FuturesPositionNotificator broadcast]"]
        OldConsumer["core/websockets/consumers.py (CŨ)\n[LiveNotificationsConsumer: add_futures_*]"]
    end

    %% Luồng tương tác
    Client -->|1. POST /api/v1/futures/orders/| OldUrls
    OldUrls --> NewView
    NewView -->|2. apply_async đẩy task| QueueFutures
    OldCelery -.->|Đăng ký Queue & Beat Schedule| NewTasks
    QueueFutures -->|3. Tiêu thụ lệnh tuần tự| NewWorker
    NewWorker --> NewBook
    NewBook -->|4. Khớp lệnh: Cấn trừ phí & PnL| OldTx
    NewBook -->|5. Bắn sự kiện vị thế & PnL| NewWS
    NewWS -->|6. group_send| OldConsumer
    OldConsumer -.->|7. WebSocket Push kết quả về UI| Client
```

#### Bảng Đối Chiếu Điểm Nối Trực Tiếp:

| File CŨ Được Cập Nhật | Đoạn Code Can Thiệp | Gọi / Kích Hoạt File MỚI Nào? | Mục Đích Kết Nối |
| :--- | :--- | :--- | :--- |
| **`core/api_urls/orders.py`** | Cuối file `urlpatterns` | `core/views/futures.py` | Mở endpoint tiếp nhận `POST /api/v1/futures/orders/`. |
| **`exchange/celery_app.py`** | Khối `if is_section_enabled('futures'):` | `core/tasks/futures.py` | Đăng ký hàng đợi `futures_liquidation`, `futures_funding` và kích hoạt lịch Celery Beat chạy Funding Rate 8h/lần. |
| **`core/models/inouts/transaction.py`** | Khối hằng số `REASON_*` (dòng 50+) | Được gọi từ `core/orderbook/futures_book.py` | Cho phép hệ thống kế toán ghi nhận các loại giao dịch ký quỹ, funding, lãi/lỗ và thanh lý. |
| **`core/websockets/consumers.py`** | Hàm `receive_json()` trong `LiveNotificationsConsumer` | Được bắn tới bởi `exchange/futures_notifications.py` | Cho phép Client đăng ký nghe kênh `user_positions_{user_id}` và nhận nhịp giá `futures_mark_price`. |

---

### 4. Các Bài Toán Cốt Lõi Cần Giải Quyết Khi Triển Khai Long / Short Thực Tế

Khi phát triển tính năng Long/Short vào thực tế, bắt buộc phải giải quyết các bài toán kỹ thuật sau để tránh sập hệ thống hoặc sàn bị vỡ nợ:

* **Bài toán 1: Thanh khoản & Đối tác khớp lệnh (Counterparty & Hedging)**:
  * Khi sàn mới mở, không có người Short đối ứng khi người dùng muốn Long.
  * Nếu sàn tự đứng ra ôm lệnh (mô hình B-Book), khi thị trường tăng mạnh thì toàn bộ user Long thắng tiền $\rightarrow$ Sàn sẽ vỡ nợ nếu không có hàng chục triệu USD dự phòng.
  * *Giải pháp*: Cần xây dựng **Hedging Engine (A-Book)** tự động forward khối lượng mở ròng (Net Open Interest) sang Binance/Bybit để phòng hộ rủi ro, kết hợp Bot MM tạo thanh khoản hai đầu.

* **Bài toán 2: Hiệu năng tính PnL và Quét thanh lý trên In-Memory/Redis (Tránh nghẽn DB)**:
  * Khác với Spot, ở Futures chỉ cần giá thị trường nhích $1, hàng ngàn vị thế đang mở đều biến động Lãi/Lỗ và tỷ lệ ký quỹ.
  * Nếu mỗi tick giá đều truy vấn `SELECT` / `UPDATE` vào PostgreSQL $\rightarrow$ Database sẽ quá tải (CPU 100%, cạn kiệt IOPS).
  * *Giải pháp*: Toàn bộ vị thế và mức giá thanh lý (`liquidation_price`) phải được lập chỉ mục trong RAM hoặc `Sorted Set (ZSET)` của Redis. Chỉ quét trên Redis, khi vị thế bị đóng mới ghi log xuống DB.

* **Bài toán 3: Nguồn cấp giá đánh dấu (Mark Price Oracle) Chống Thao Túng Giá**:
  * Tuyệt đối không dùng giá khớp nội bộ trên sàn để tính thanh lý vì sổ lệnh sàn mới mỏng, kẻ xấu có thể nạp ít tiền xả mạnh để cố tình săn thanh lý (Liquidation Hunting) của người khác.
  * *Giải pháp*: Kết nối WebSocket lấy giá Spot từ 3 sàn lớn (Binance, OKX, Bybit), tính giá trung vị (Median Index Price) và cộng EMA Basis để sinh ra **Mark Price**.

* **Bài toán 4: Cơ chế Thanh lý (Liquidation), Quỹ Bảo Hiểm (Insurance Fund) & ADL**:
  * Khi thị trường rơi tự do (Flash Crash), việc bán tháo vị thế cháy có thể bị trượt giá sâu làm tài khoản user bị âm tiền (Bad Debt).
  * *Giải pháp*: Bắt buộc phải có **Quỹ Bảo Hiểm** để bù đắp các khoản lỗ trượt giá này, và cơ chế **ADL (Auto-Deleveraging)** tự động giảm bớt vị thế của phe đang có lãi nhiều nhất để bảo toàn sàn nếu Quỹ Bảo Hiểm cạn tiền.

* **Bài toán 5: Phân tách Ví An toàn (Isolated Wallet vs Spot Wallet)**:
  * Tuyệt đối không dùng chung bảng `Balance` của Spot cho Futures.
  * Phải tách riêng bảng `FuturesBalance`. Người dùng muốn chơi Long/Short phải bấm "Chuyển tiền" từ ví Spot sang ví Futures để bảo vệ tài sản không bị thanh lý chéo.

* **Bài toán 6: Chống Race Condition / Double Settlement Trên Vị Thế**:
  * Nguy cơ người dùng bấm đóng lệnh bằng tay đúng vào tích tắc Liquidation Worker cũng đang ép thanh lý.
  * *Giải pháp*: Áp dụng khóa `select_for_update()` kết hợp trường `version` (Optimistic Locking) trên bảng `Position` để đảm bảo không bị thanh lý trùng lặp.

* **Bài toán 7: Lựa chọn Mô hình Ký Quỹ Ban Đầu (Isolated Margin Trước)**:
  * Khi mới phát triển, chỉ nên triển khai **Isolated Margin** (ký quỹ cô lập trên từng lệnh: cháy lệnh nào mất tiền lệnh đó). Chưa nên làm Cross Margin ngay để tránh rủi ro sụp đổ dây chuyền tài khoản.

---

### 5. Chiến Lược Cơ Sở Dữ Liệu (Database): Sửa Bảng Cũ Hay Thêm Bảng Mới?

Khi mở rộng hệ thống từ Spot sang Long/Short, **chiến lược tối ưu là Mô Hình Kết Hợp (Hybrid Model)**: Sửa đổi tối thiểu ở các bảng kế toán dùng chung và Tạo mới hoàn toàn các bảng nghiệp vụ phái sinh độc lập.

#### A. Các Bảng CŨ Cần Sửa (Modifications)
Hệ thống cũ cần được bổ sung để hiểu được các dòng tiền và phân loại lệnh mới mà không làm vỡ logic Spot:

1. **Bảng `Transaction` ([`core/models/inouts/transaction.py`](file:///home/apollai/Documents/GitHub/opencex/backend/core/models/inouts/transaction.py))**:
   * **Cách sửa**: Bổ sung các hằng số enum `REASON_*` mới (không cần sửa cấu trúc schema bảng):
     * `REASON_FUTURES_MARGIN_HOLD = 60`: Tạm giữ tiền ký quỹ khi mở lệnh Long/Short.
     * `REASON_FUTURES_MARGIN_RELEASE = 61`: Hoàn trả ký quỹ khi đóng vị thế hoặc hủy lệnh.
     * `REASON_FUTURES_REALIZED_PNL = 62`: Cộng/trừ tiền Lãi/Lỗ thực tế khi chốt vị thế.
     * `REASON_FUTURES_FUNDING_FEE = 63`: Khấu trừ/cộng phí Funding Rate định kỳ mỗi 8h.
     * `REASON_FUTURES_LIQUIDATION_LOSS = 64`: Trừ tiền lỗ khi vị thế bị cưỡng chế thanh lý.
   * **Mục đích**: Giúp module kế toán tài sản ghi nhận vết tiền biến động rõ ràng.

2. **Bảng `Order` ([`core/models/orders/__init__.py`](file:///home/apollai/Documents/GitHub/opencex/backend/core/models/orders/__init__.py))**:
   * **Cách sửa**: Bổ sung các trường phái sinh (hoặc tách riêng thành `FuturesOrder`):
     * `position_effect`: Phân biệt lệnh Mở vị thế (`OPEN`) hay Đóng vị thế (`CLOSE`).
     * `leverage`: Mức đòn bẩy áp dụng cho lệnh (ví dụ: 10x, 20x, 50x).
     * `margin_mode`: Chế độ ký quỹ (`ISOLATED` hoặc `CROSS`).
     * `reduce_only`: Cờ chỉ cho phép giảm khối lượng vị thế, không cho mở thêm.

---

#### B. Các Bảng MỚI Bắt Buộc Phải Thêm (New Tables)
Tuyệt đối **KHÔNG nhồi nhét** các khái niệm phái sinh vào bảng dữ liệu Spot, bắt buộc phải tạo mới 5 bảng sau:

1. **Bảng `FuturesBalance` (Ví Ký Quỹ Phái Sinh)**:
   * **Tại sao không dùng chung bảng `Balance` của Spot?**
     * *Lý do an toàn sống còn*: Nếu dùng chung ví, khi người dùng bị cháy một lệnh Futures x50, Liquidation Engine có thể quét sạch toàn bộ Bitcoin và USDT người dùng đang lưu trữ ở ví Spot.
     * *Cấu trúc trường*: `user_id`, `currency`, `wallet_balance` (số dư ví Futures), `margin_locked` (ký quỹ đang bị khóa trong vị thế và lệnh chờ).
     * *Quy trình*: Người dùng muốn đánh Long/Short phải bấm "Chuyển tiền" (Internal Transfer) từ ví Spot sang ví Futures.

2. **Bảng `Position` (Bảng Quản Lý Vị Thế - Cốt Lõi Nhất)**:
   * **Tại sao không thể dùng bảng `Order` cũ?**
     * Trong Spot, sau khi khớp lệnh là xong (`Order` đóng). Nhưng trong Futures, sau khi khớp lệnh thì **bắt đầu sinh ra một Vị thế (Position) tồn tại theo thời gian thực** chịu ảnh hưởng của giá thị trường.
     * *Cấu trúc trường*:
       * `user_id`, `pair`: Tài khoản và cặp hợp đồng (VD: `BTC-USDT-PERP`).
       * `side`: Chiều vị thế (`LONG` hoặc `SHORT`).
       * `size`: Khối lượng hợp đồng đang nắm giữ.
       * `entry_price`: Giá vào lệnh trung bình.
       * `initial_margin`: Số tiền ký quỹ gốc bỏ ra.
       * `leverage`, `margin_mode`: Mức đòn bẩy và chế độ ký quỹ.
       * `liquidation_price`: Giá thanh lý ước tính.
       * `is_closed`: Trạng thái vị thế (Đang mở hay Đã đóng).
       * `version`: **Khóa lạc quan (Optimistic Lock)** chống Race Condition / Double Settlement.

3. **Bảng `FuturesContract` / `FuturesPair` (Đặc Tả Cặp Hợp Đồng)**:
   * Tách riêng khỏi bảng `Pair` của Spot để quản lý các tham số phái sinh đặc thù:
     * `code`: Tên hợp đồng (VD: `BTC-USDT-PERP`).
     * `max_leverage`: Đòn bẩy tối đa cho phép (VD: BTC cho 100x, Altcoin cho 20x).
     * `maintenance_margin_rate` (MMR): Tỷ lệ ký quỹ duy trì tối thiểu (VD: 0.5%).
     * `mark_price` & `index_price`: Giá tham chiếu cập nhật từ Oracle bên ngoài.
     * `funding_rate` & `next_funding_time`: Tỷ lệ và thời điểm thanh toán funding.

4. **Bảng `LiquidationHistory` (Lịch Sử Thanh Lý & Quỹ Bảo Hiểm)**:
   * Lưu lại chi tiết từng vụ cháy tài khoản: vị thế bị đóng ở giá nào, khoản lỗ thực tế, số tiền thu về Quỹ bảo hiểm (`Insurance Fund`), hoặc mức lỗ thâm hụt (Bad Debt) mà sàn phải gánh.

5. **Bảng `FundingRateHistory` (Lịch Sử Phí Funding)**:
   * Lưu lịch sử trả phí mỗi 8 tiếng: cặp hợp đồng, tỷ lệ funding, thời gian, tổng tiền phe Long trả cho phe Short (hoặc ngược lại).

---

#### C. Bảng So Sánh Nhanh: Sửa Cũ vs Thêm Mới

| Thực Thể Dữ Liệu | Chiến Lược | Vị Trí / Bảng | Lý Do Kiến Trúc |
| :--- | :---: | :--- | :--- |
| **Mã lý do giao dịch** | **SỬA CŨ** | `core/models/inouts/transaction.py` | Tái sử dụng bảng `Transaction` hiện có để ghi nhận lịch sử dòng tiền thống nhất. |
| **Lệnh đặt Mua/Bán** | **SỬA CŨ** | `core/models/orders/__init__.py` | Bổ sung các cờ phái sinh (`leverage`, `position_effect`) vào model lệnh. |
| **Ví tiền người dùng** | **THÊM MỚI** | Bảng mới `FuturesBalance` | **Bắt buộc cô lập ví**: Bảo vệ tài sản ví Spot không bị thanh lý chéo khi cháy Futures. |
| **Vị thế Long/Short** | **THÊM MỚI** | Bảng mới `Position` | Spot không có khái niệm vị thế duy trì theo thời gian thực; bắt buộc phải có bảng riêng. |
| **Cặp hợp đồng** | **THÊM MỚI** | Bảng mới `FuturesContract` | Cần các trường tham số đòn bẩy, tỷ lệ MMR, Mark Price và Funding Rate. |
| **Lịch sử thanh lý & Funding** | **THÊM MỚI** | `LiquidationHistory`, `FundingRateHistory` | Kiểm toán nợ xấu, quỹ bảo hiểm và đối soát phí định kỳ mỗi 8 tiếng. |


