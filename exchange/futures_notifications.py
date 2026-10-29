#!/usr/bin/env python3
"""
=============================================================================
EDUCATIONAL TEMPLATE: FUTURES WEBSOCKET NOTIFICATOR MODULE
=============================================================================
Vị trí trong hệ thống: backend/exchange/futures_notifications.py
Mục đích:
  - Hướng dẫn sinh viên cách nối kết quả từ Engine/Worker ra giao diện người dùng
    thông qua kênh truyền thời gian thực (WebSocket - Django Channels).
  - Tương tự như `backend/exchange/notifications.py` của Spot.
  - Bao gồm 3 bộ phát tin (Notificators):
      1. `FuturesPositionNotificator`: Bắn cập nhật PnL và vị thế riêng cho từng User.
      2. `MarkPriceNotificator`: Bắn giá Mark Price realtime cho toàn bộ người xem.
      3. `LiquidationNotificator`: Bắn thông báo nổ cháy vị thế ra kênh công khai.
=============================================================================
"""

import logging
from typing import Dict, Any

logger = logging.getLogger("FuturesWSNotificator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class BaseFuturesNotificator:
    """Khung sườn phát tin nhắn WebSocket kế thừa mô hình của OpenCEX"""
    CHANNEL_PREFIX: str = ""

    def gen_channel(self, identifier: str) -> str:
        return f"{self.CHANNEL_PREFIX}_{identifier}"

    def broadcast(self, channel: str, payload: Dict[str, Any]):
        """
        Trong thực tế OpenCEX dùng:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            async_to_sync(get_channel_layer().group_send)(channel, {'type': 'exchange.message', 'data': payload})
        """
        logger.info(f"[WS_BROADCAST] -> Kênh [#{channel}] | Gói tin: {payload}")


class FuturesPositionNotificator(BaseFuturesNotificator):
    CHANNEL_PREFIX = "user_positions"

    def notify_position_update(self, user_id: int, position_data: Dict[str, Any]):
        channel = self.gen_channel(str(user_id))
        payload = {
            "event": "POSITION_UPDATE",
            "pair": position_data.get("pair"),
            "side": position_data.get("side"),
            "size": str(position_data.get("size")),
            "entry_price": str(position_data.get("entry_price")),
            "unrealized_pnl": str(position_data.get("unrealized_pnl")),
            "roe_percent": str(position_data.get("roe")),
            "liq_price": str(position_data.get("liq_price")),
        }
        self.broadcast(channel, payload)


class MarkPriceNotificator(BaseFuturesNotificator):
    CHANNEL_PREFIX = "futures_mark_price"

    def notify_mark_price(self, pair: str, mark_price: str):
        channel = self.gen_channel(pair)
        payload = {
            "event": "MARK_PRICE_TICK",
            "pair": pair,
            "mark_price": mark_price
        }
        self.broadcast(channel, payload)


class LiquidationNotificator(BaseFuturesNotificator):
    CHANNEL_PREFIX = "futures_public"

    def notify_liquidation(self, pair: str, side: str, size: str, price: str):
        channel = self.gen_channel("liquidations")
        payload = {
            "event": "FORCE_LIQUIDATION",
            "pair": pair,
            "side": side,
            "size": size,
            "executed_price": price,
            "msg": f"Cảnh báo: Lệnh {side} {size} {pair} vừa bị thanh lý ở mức giá {price} USDT!"
        }
        self.broadcast(channel, payload)


# =============================================================================
# CHẠY TEST ĐỘC LẬP
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("DEMO: KIỂM THỬ BẮN TIN WEBSOCKET REALTIME CHO PHÁI SINH")
    print("=" * 70)

    # 1. Test bắn PnL riêng cho User #2
    pos_notifier = FuturesPositionNotificator()
    sample_pos = {
        "pair": "BTC-USDT-PERP", "side": "LONG", "size": "1.0",
        "entry_price": "65000", "unrealized_pnl": "+350.50", "roe": "+10.78", "liq_price": "62075"
    }
    pos_notifier.notify_position_update(user_id=2, position_data=sample_pos)

    # 2. Test bắn nhịp giá Mark Price
    mark_notifier = MarkPriceNotificator()
    mark_notifier.notify_mark_price("BTC-USDT-PERP", "65350.50")

    # 3. Test bắn thông báo thanh lý ra toàn sàn
    liq_notifier = LiquidationNotificator()
    liq_notifier.notify_liquidation("BTC-USDT-PERP", "LONG", "2.0", "62075")

    print("=" * 70)
