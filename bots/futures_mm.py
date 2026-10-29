#!/usr/bin/env python3
"""
=============================================================================
EDUCATIONAL TEMPLATE: FUTURES MARKET MAKER BOT (LIQUIDITY PROVIDER)
=============================================================================
Vị trí trong hệ thống: backend/bots/futures_mm.py
Mục đích:
  - Hướng dẫn sinh viên cách giải quyết bài toán "Ai là người khớp lệnh?" khi sàn mới mở.
  - Bot đóng vai trò Nhà tạo lập thị trường (Market Maker - MM):
      1. Lấy giá tham chiếu (Mark Price từ Oracle / Binance).
      2. Tự động treo lệnh Long (Bid) ở dưới giá tham chiếu.
      3. Tự động treo lệnh Short (Ask) ở trên giá tham chiếu.
      4. Thu lợi nhuận từ độ chênh lệch giá (Bid-Ask Spread) và cung cấp thanh khoản mồi.
=============================================================================
"""

import time
import logging
from decimal import Decimal

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FuturesMMBot")


class FuturesMarketMakerBot:
    def __init__(self, pair: str = "BTC-USDT-PERP", spread_pct: Decimal = Decimal("0.001"), order_size: Decimal = Decimal("2.0")):
        self.pair = pair
        self.spread_pct = spread_pct    # Độ giãn cách giá (VD: 0.1% = 0.001)
        self.order_size = order_size    # Khối lượng mỗi lệnh treo
        self.is_running = True

    def calculate_quotes(self, mark_price: Decimal) -> tuple:
        """
        Tính toán mức giá Bid (Long) và Ask (Short) dựa trên Mark Price:
        - Bid Price = MarkPrice * (1 - Spread/2)
        - Ask Price = MarkPrice * (1 + Spread/2)
        """
        half_spread = self.spread_pct / Decimal("2")
        bid_price = round(mark_price * (Decimal("1") - half_spread), 2)
        ask_price = round(mark_price * (Decimal("1") + half_spread), 2)
        return bid_price, ask_price

    def sync_liquidity(self, mark_price: Decimal):
        """
        Thực hiện một chu kỳ cập nhật thanh khoản (Market Making Cycle):
        Hủy các lệnh cũ xa giá và đặt các lệnh mới bám sát giá thị trường.
        """
        bid_price, ask_price = self.calculate_quotes(mark_price)
        spread_usd = ask_price - bid_price

        logger.info(f"[MM_BOT] [TICK] Giá tham chiếu: {mark_price} USDT | Spread: {spread_usd} USDT ({self.spread_pct * 100}%)")
        logger.info(f"   -> Đặt lệnh Treo LONG (Bid): {self.order_size} BTC @ {bid_price} USDT")
        logger.info(f"   -> Đặt lệnh Treo SHORT (Ask): {self.order_size} BTC @ {ask_price} USDT")
        logger.info(f"[MM_BOT] Thanh khoản hai đầu đã được bơm vào OrderBook. Người dùng có thể khớp lệnh ngay lập tức!")


if __name__ == "__main__":
    print("=" * 70)
    print("DEMO: KIỂM THỬ BOT TẠO THANH KHOẢN PHÁI SINH (MM BOT)")
    print("=" * 70)

    bot = FuturesMarketMakerBot(pair="BTC-USDT-PERP", spread_pct=Decimal("0.001"), order_size=Decimal("2.5"))
    current_market_price = Decimal("65000")

    bot.sync_liquidity(current_market_price)
    print("=" * 70)
