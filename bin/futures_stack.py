#!/usr/bin/env python3
"""
=============================================================================
EDUCATIONAL TEMPLATE: FUTURES MATCHING WORKER RUNNER (STACK WORKER)
=============================================================================
Vị trí trong hệ thống: backend/bin/futures_stack.py
Mục đích:
  - Hướng dẫn sinh viên cách viết tiến trình Worker độc lập chuyên trách khớp lệnh.
  - Tương tự như `backend/bin/stack.py` của Spot nhưng phục vụ các cặp Futures.
  - Các nguyên lý thiết kế then chốt:
      1. `concurrency = 1`: Xử lý tuần tự từng lệnh, triệt tiêu Race Condition.
      2. `Distributed Lock (Redis)`: Đảm bảo tại một thời điểm chỉ có DUY NHẤT
         1 tiến trình Worker xử lý cho 1 cặp hợp đồng.
      3. `In-Memory State`: Nạp toàn bộ vị thế và lệnh đang mở vào RAM khi bật máy.
=============================================================================
"""

import sys
import os
import time
import logging
import click

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FuturesStackWorker")


class MockFuturesLock:
    """Mô phỏng cơ chế Distributed Lock trên Redis (tương tự StackLock trong lib/oneinstlock.py)"""
    def __init__(self, pairs):
        self.pairs = pairs

    def acquire(self):
        logger.info(f"[STACK_LOCK] Đang yêu cầu khóa phân tán Redis cho các cặp: {self.pairs}...")
        time.sleep(0.2)
        logger.info(f"[STACK_LOCK] THÀNH CÔNG: Đã giữ khóa phân tán độc quyền. Không worker nào khác có thể can thiệp.")
        return True

    def release(self):
        logger.info(f"[STACK_LOCK] Đã giải phóng khóa phân tán.")


def simulate_worker_startup(pairs: list):
    """
    Quy trình chuẩn khi khởi động một Matching Worker trong kiến trúc OpenCEX.
    """
    logger.info("=" * 65)
    logger.info("KHỞI ĐỘNG TIẾN TRÌNH: FUTURES ORDER MATCHING WORKER")
    logger.info("=" * 65)

    # Bước 1: Khóa phân tán
    lock = MockFuturesLock(pairs)
    lock.acquire()

    # Bước 2: Thiết lập Queue
    queues = [f"futures.orders.{p.upper()}" for p in pairs]
    logger.info(f"[CELERY_WORKER] Cấu hình tham số Worker:")
    logger.info(f"   -> Hàng đợi lắng nghe (Queues): {queues}")
    logger.info(f"   -> Mức độ đồng thời (Concurrency): 1 (Bắt buộc tuần tự chống Race Condition)")
    logger.info(f"   -> Worker Prefetch Multiplier: 100")

    # Bước 3: Nạp dữ liệu từ Database vào RAM (Warm-up Cache)
    logger.info(f"[CACHE_WARMUP] Truy vấn PostgreSQL nạp các Vị thế & Lệnh OPENED vào RAM...")
    time.sleep(0.3)
    logger.info(f"[CACHE_WARMUP] Hoàn tất nạp: 45 vị thế đang mở và 120 lệnh chờ vào OrderBook RAM.")

    # Bước 4: Sẵn sàng nhận lệnh
    logger.info(f"[READY] Futures Stack Worker đã sẵn sàng tiêu thụ lệnh từ hàng đợi Redis!")
    logger.info("=" * 65)


@click.command()
@click.option("--pairs", default="BTC-USDT-PERP", help="Danh sách cặp phái sinh (phân cách bằng dấu phẩy)")
@click.option("--simulate", is_flag=True, default=True, help="Chạy ở chế độ mô phỏng hiển thị log cho sinh viên")
def cli(pairs, simulate):
    pair_list = pairs.split(",")
    if simulate:
        simulate_worker_startup(pair_list)
        logger.info("[DEMO_MODE] Worker đang ở trạng thái trực tuyến (Ctrl+C để dừng).")
    else:
        # Trong môi trường Production thực tế kết nối Celery:
        # from exchange.celery_app import app
        # from celery.apps.worker import Worker
        # wrk = Worker(app=app, queues=[f'futures.orders.{p}' for p in pair_list], concurrency=1)
        # wrk.start()
        pass


if __name__ == "__main__":
    cli()
