#!/usr/bin/env python3
"""
=============================================================================
EDUCATIONAL TEMPLATE: FUTURES BACKGROUND TASKS & CELERY WORKERS
=============================================================================
Vị trí trong hệ thống: backend/core/tasks/futures.py
Mục đích:
  - Hướng dẫn sinh viên cách định nghĩa các Celery Tasks nền cho hệ thống Phái sinh.
  - Bao gồm 4 tác vụ cốt lõi:
      1. `place_futures_order`: Nhận lệnh Mua/Bán phái sinh từ hàng đợi.
      2. `check_liquidations`: Quét vị thế và ép thanh lý (Liquidation Worker).
      3. `update_mark_price`: Lấy giá từ Oracle và cập nhật Mark Price.
      4. `settle_funding_rate`: Thanh toán phí Funding Rate định kỳ mỗi 8h.
=============================================================================
"""

import logging
import random
from decimal import Decimal
from typing import Dict, Any

logger = logging.getLogger("FuturesTasks")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

try:
    from celery import shared_task
except ImportError:
    # Giả lập decorator nếu sinh viên chạy môi trường standalone không có Celery
    def shared_task(func):
        return func


@shared_task
def place_futures_order(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Task xử lý lệnh Long/Short được bốc ra từ hàng đợi `futures.orders.<PAIR>`.
    Worker gọi đến Singleton FuturesOrderBook để tiến hành so khớp.
    """
    pair = order_data.get("pair", "BTC-USDT-PERP")
    side = order_data.get("side", "LONG")
    price = Decimal(str(order_data.get("price", "65000")))
    size = Decimal(str(order_data.get("size", "1.0")))
    leverage = order_data.get("leverage", 20)
    user_id = order_data.get("user_id", 1)

    logger.info(f"[TASK: place_futures_order] Bắt đầu xử lý lệnh #{order_data.get('id', 'NEW')} "
                f"cho User #{user_id} | {side} {size} {pair} @ {price} ({leverage}x)")

    # Trong thực tế: import FuturesOrderBook từ core.orderbook.futures_book
    # và gọi book.place_order(order)
    result = {
        "status": "PROCESSED",
        "user_id": user_id,
        "pair": pair,
        "side": side,
        "executed_price": str(price),
        "executed_size": str(size),
        "leverage": leverage
    }
    logger.info(f"[TASK: place_futures_order] Hoàn tất khớp lệnh: {result}")
    return result


@shared_task
def check_liquidations(current_mark_price: Decimal, simulated_positions: list = None) -> list:
    """
    Liquidation Task: Quét liên tục danh sách các vị thế đang mở.
    Nếu Mark Price chạm ngưỡng Liquidation Price, kích hoạt đóng vị thế khẩn cấp.
    """
    logger.info(f"[TASK: check_liquidations] Bắt đầu quét thanh lý với MarkPrice: {current_mark_price} USDT...")

    liquidated_positions = []
    positions = simulated_positions or [
        {"user_id": 10, "pair": "BTC-USDT-PERP", "side": "LONG", "size": Decimal("2.0"),
         "entry": Decimal("65000"), "liq_price": Decimal("62075")},
        {"user_id": 11, "pair": "BTC-USDT-PERP", "side": "SHORT", "size": Decimal("1.5"),
         "entry": Decimal("65000"), "liq_price": Decimal("67925")}
    ]

    for pos in positions:
        user_id = pos["user_id"]
        side = pos["side"]
        liq_price = pos["liq_price"]

        is_liquidated = False
        if side == "LONG" and current_mark_price <= liq_price:
            is_liquidated = True
        elif side == "SHORT" and current_mark_price >= liq_price:
            is_liquidated = True

        if is_liquidated:
            logger.warning(
                f"[LIQUIDATION_ALERT] VỊ THẾ BỊ CHÁY! User #{user_id} | {side} {pos['size']} BTC | "
                f"Giá vào: {pos['entry']} | Giá thanh lý: {liq_price} | Giá thị trường hiện tại: {current_mark_price}"
            )
            # Thực thi Market Close vị thế
            logger.warning(f"[FORCE_CLOSE] Bắn lệnh Market {side}_CLOSE để thu hồi vốn đưa vào Quỹ bảo hiểm.")
            liquidated_positions.append(pos)
        else:
            logger.info(f"[SAFE] Vị thế User #{user_id} an toàn (Liq: {liq_price} vs Mark: {current_mark_price})")

    return liquidated_positions


@shared_task
def update_mark_price(pair: str = "BTC-USDT-PERP") -> Decimal:
    """
    Oracle Task: Lấy giá từ 3 sàn lớn (Binance, Bybit, OKX) để tính Mark Price.
    Giúp chống thao túng giá trên sàn nội bộ.
    """
    # Mô phỏng lấy dữ liệu từ 3 sàn
    binance_price = Decimal("65000") + Decimal(str(random.randint(-10, 10)))
    bybit_price = Decimal("65005") + Decimal(str(random.randint(-10, 10)))
    okx_price = Decimal("64995") + Decimal(str(random.randint(-10, 10)))

    prices = sorted([binance_price, bybit_price, okx_price])
    index_price = prices[1] # Lấy giá trung vị (Median)
    mark_price = index_price # Trong thực tế cộng thêm EMA Basis

    logger.info(f"[ORACLE] Cập nhật giá {pair}: Binance={binance_price}, Bybit={bybit_price}, OKX={okx_price} "
                f"===> MarkPrice: {mark_price} USDT")
    return mark_price


@shared_task
def settle_funding_rate(pair: str = "BTC-USDT-PERP", current_rate: Decimal = Decimal("0.0001")) -> Dict[str, Any]:
    """
    Funding Rate Scheduler Task (Celery Beat chạy mỗi 8h: 00:00, 08:00, 16:00 UTC).
    Cân bằng giá phái sinh với giá Spot:
    - Nếu Funding Rate dương (> 0): Phe Long trả tiền cho phe Short.
    - Nếu Funding Rate âm (< 0): Phe Short trả tiền cho phe Long.
    """
    rate_percent = current_rate * Decimal("100")
    logger.info(f"[FUNDING_RATE] Kích hoạt kỳ tính phí cho {pair}. Tỷ lệ hiện tại: {rate_percent:+.4f}%")

    if current_rate > 0:
        action_msg = "Phe LONG trả phí cho phe SHORT."
    else:
        action_msg = "Phe SHORT trả phí cho phe LONG."

    logger.info(f"[FUNDING_SETTLEMENT] {action_msg} Bắt đầu cấn trừ ví Futures của các tài khoản.")
    return {
        "pair": pair,
        "rate": str(current_rate),
        "action": action_msg
    }


# =============================================================================
# CHẠY TEST ĐỘC LẬP
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("DEMO: KIỂM THỬ CÁC CELERY TASKS CỦA LONG / SHORT")
    print("=" * 70)

    # 1. Test Task Đặt Lệnh
    sample_order = {"id": 1, "user_id": 101, "pair": "BTC-USDT-PERP", "side": "LONG",
                    "price": 65000, "size": 1.5, "leverage": 20}
    place_futures_order(sample_order)

    # 2. Test Task Oracle cập nhật giá
    print("-" * 50)
    mark_price = update_mark_price()

    # 3. Test Task Funding Rate
    print("-" * 50)
    settle_funding_rate(current_rate=Decimal("0.0001"))

    # 4. Test Task Quét Thanh Lý (Giả lập giá rơi xuống 62,000 USDT)
    print("-" * 50)
    crash_price = Decimal("62000")
    check_liquidations(current_mark_price=crash_price)

    print("=" * 70)
