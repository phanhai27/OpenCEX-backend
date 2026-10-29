#!/usr/bin/env python3
"""
=============================================================================
EDUCATIONAL TEMPLATE: FUTURES MATCHING ENGINE & ORDERBOOK (LONG / SHORT)
=============================================================================
Vị trí trong hệ thống: backend/core/orderbook/futures_book.py
Mục đích:
  - Hướng dẫn sinh viên cách mở rộng Matching Engine từ Spot sang Phái sinh (Futures).
  - Khác biệt cốt lõi với Spot:
      + Spot: Khớp lệnh Mua/Bán là chuyển giao coin/tiền vật lý giữa 2 ví.
      + Futures: Khớp lệnh Long/Short là tạo lập hoặc tất toán VỊ THẾ (Position)
        dựa trên KÝ QUỸ (Margin) và ĐÒN BẨY (Leverage).
=============================================================================
"""

import time
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FuturesBook")

# Các hằng số vị thế & lệnh phái sinh
SIDE_LONG = "LONG"
SIDE_SHORT = "SHORT"

EFFECT_OPEN = "OPEN"      # Mở vị thế mới
EFFECT_CLOSE = "CLOSE"    # Đóng vị thế hiện có (hoặc Reduce-only)


class FuturesPosition:
    """
    Đại diện cho Vị thế phái sinh của một người dùng.
    Tương ứng với bản ghi trong bảng DB: `Position`
    """
    def __init__(self, user_id: int, pair: str, side: str, size: Decimal, entry_price: Decimal, leverage: int):
        self.user_id = user_id
        self.pair = pair
        self.side = side                  # LONG hoặc SHORT
        self.size = size                  # Khối lượng hợp đồng (VD: 1.0 BTC)
        self.entry_price = entry_price    # Giá vào lệnh trung bình
        self.leverage = leverage          # Đòn bẩy (VD: 20x)
        self.initial_margin = self._calc_initial_margin()
        self.liquidation_price = self._calc_liquidation_price()
        self.realized_pnl = Decimal("0")

    def _calc_initial_margin(self) -> Decimal:
        """Ký quỹ ban đầu = (Khối lượng * Giá) / Đòn bẩy"""
        notional_value = self.size * self.entry_price
        return notional_value / Decimal(str(self.leverage))

    def _calc_liquidation_price(self, maintenance_margin_rate: Decimal = Decimal("0.005")) -> Decimal:
        """
        Tính giá thanh lý dự kiến (Liquidation Price).
        Khi giá thị trường chạm ngưỡng này, vị thế sẽ bị ép đóng để tránh âm tài khoản.
        - Long: LiqPrice = Entry * (1 - (1/Leverage) + MMR)
        - Short: LiqPrice = Entry * (1 + (1/Leverage) - MMR)
        """
        leverage_factor = Decimal("1") / Decimal(str(self.leverage))
        if self.side == SIDE_LONG:
            liq = self.entry_price * (Decimal("1") - leverage_factor + maintenance_margin_rate)
        else:
            liq = self.entry_price * (Decimal("1") + leverage_factor - maintenance_margin_rate)
        return round(liq, 2)

    def calc_unrealized_pnl(self, mark_price: Decimal) -> Tuple[Decimal, Decimal]:
        """
        Tính Lãi/Lỗ chưa chốt (Unrealized PnL) và Tỷ suất lợi nhuận (ROE %):
        - Long: PnL = Size * (MarkPrice - EntryPrice)
        - Short: PnL = Size * (EntryPrice - MarkPrice)
        """
        if self.side == SIDE_LONG:
            pnl = self.size * (mark_price - self.entry_price)
        else:
            pnl = self.size * (self.entry_price - mark_price)
        roe = (pnl / self.initial_margin) * Decimal("100") if self.initial_margin > 0 else Decimal("0")
        return round(pnl, 2), round(roe, 2)

    def __repr__(self):
        return (f"<Position user={self.user_id} {self.side} size={self.size} {self.pair} "
                f"entry={self.entry_price} lev={self.leverage}x margin={round(self.initial_margin, 2)} "
                f"liq={self.liquidation_price}>")


class FuturesOrder:
    """
    Đại diện cho lệnh đặt Mua (Long) hoặc Bán (Short).
    """
    def __init__(self, order_id: int, user_id: int, pair: str, side: str,
                 price: Decimal, size: Decimal, leverage: int = 10, effect: str = EFFECT_OPEN):
        self.id = order_id
        self.user_id = user_id
        self.pair = pair
        self.side = side                  # LONG hoặc SHORT
        self.price = price                # Mức giá đặt
        self.size = size                  # Khối lượng
        self.size_left = size             # Khối lượng còn lại chưa khớp
        self.leverage = leverage          # Đòn bẩy
        self.effect = effect              # OPEN hoặc CLOSE
        self.created_at = time.time()

    def __repr__(self):
        return f"<FuturesOrder #{self.id} user={self.user_id} {self.side} {self.size_left}@{self.price} {self.leverage}x>"


class FuturesOrderBook:
    """
    Sổ lệnh phái sinh cho một cặp hợp đồng (ví dụ: BTC-USDT-PERP).
    Quản lý 2 nhánh lệnh chờ:
      - Long Orders (Bids): Ưu tiên giá cao nhất xếp trước (DESC)
      - Short Orders (Asks): Ưu tiên giá thấp nhất xếp trước (ASC)
    """
    def __init__(self, pair: str = "BTC-USDT-PERP"):
        self.pair = pair
        self.long_stack: List[FuturesOrder] = []   # Lệnh chờ Long (Mua)
        self.short_stack: List[FuturesOrder] = []  # Lệnh chờ Short (Bán)
        self.positions: Dict[int, FuturesPosition] = {} # user_id -> FuturesPosition (In-memory cache)

    def place_order(self, order: FuturesOrder) -> List[Dict]:
        """
        Nhận lệnh mới và thực thi thuật toán so khớp (Price-Time Priority).
        """
        logger.info(f"[FUTURES_BOOK] [{self.pair}] >>> Tiếp nhận lệnh: {order}")
        trades = []

        if order.side == SIDE_LONG:
            # Lệnh Long sẽ tìm khớp với các lệnh Short có giá <= giá đặt
            trades = self._match(order, opposite_stack=self.short_stack, is_long=True)
            if order.size_left > 0:
                self._insert_stack(self.long_stack, order, reverse=True) # Giá cao xếp trước
        else:
            # Lệnh Short sẽ tìm khớp với các lệnh Long có giá >= giá đặt
            trades = self._match(order, opposite_stack=self.long_stack, is_long=False)
            if order.size_left > 0:
                self._insert_stack(self.short_stack, order, reverse=False) # Giá thấp xếp trước

        return trades

    def _match(self, taker_order: FuturesOrder, opposite_stack: List[FuturesOrder], is_long: bool) -> List[Dict]:
        trades = []
        i = 0
        while i < len(opposite_stack) and taker_order.size_left > 0:
            maker_order = opposite_stack[i]

            # Kiểm tra điều kiện giá khớp
            match_possible = (taker_order.price >= maker_order.price) if is_long else (taker_order.price <= maker_order.price)
            if not match_possible:
                break

            matched_size = min(taker_order.size_left, maker_order.size_left)
            execution_price = maker_order.price # Khớp theo giá của Maker đang treo

            # Giảm khối lượng còn lại
            taker_order.size_left -= matched_size
            maker_order.size_left -= matched_size

            trade_info = {
                "pair": self.pair,
                "price": execution_price,
                "size": matched_size,
                "long_user": taker_order.user_id if is_long else maker_order.user_id,
                "short_user": maker_order.user_id if is_long else taker_order.user_id,
                "timestamp": time.time()
            }
            trades.append(trade_info)

            logger.info(f"[MATCHING_ENGINE] [MATCHED] Khớp {matched_size} {self.pair} @ {execution_price} USDT "
                        f"| Long: User #{trade_info['long_user']} <---> Short: User #{trade_info['short_user']}")

            # Cập nhật Vị thế (Position) cho 2 bên
            self._update_position(trade_info["long_user"], SIDE_LONG, matched_size, execution_price, taker_order.leverage)
            self._update_position(trade_info["short_user"], SIDE_SHORT, matched_size, execution_price, maker_order.leverage)

            # Nếu lệnh maker đã khớp hết thì loại khỏi stack
            if maker_order.size_left == 0:
                opposite_stack.pop(i)
            else:
                i += 1

        return trades

    def _update_position(self, user_id: int, side: str, size: Decimal, price: Decimal, leverage: int):
        """Mô phỏng cập nhật vị thế sau khi khớp lệnh"""
        pos = FuturesPosition(user_id=user_id, pair=self.pair, side=side, size=size, entry_price=price, leverage=leverage)
        self.positions[user_id] = pos
        logger.info(f"[POSITION_MANAGER] [UPDATED] {pos}")

    def _insert_stack(self, stack: List[FuturesOrder], order: FuturesOrder, reverse: bool):
        stack.append(order)
        stack.sort(key=lambda o: o.price, reverse=reverse)
        logger.info(f"[FUTURES_BOOK] Lệnh #{order.id} còn dư {order.size_left}, đưa vào sổ chờ ({order.side} Stack)")


# =============================================================================
# CHẠY THỬ NGHIỆM ĐỘC LẬP DÀNH CHO GIẢNG VIÊN & SINH VIÊN
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("DEMO: KIỂM THỬ KHỚP LỆNH PHÁI SINH (FUTURES ORDERBOOK SIMULATION)")
    print("=" * 70)

    book = FuturesOrderBook(pair="BTC-USDT-PERP")

    # 1. Sinh viên A đặt lệnh SHORT treo trên sổ lệnh (Maker)
    order_maker = FuturesOrder(
        order_id=101, user_id=1, pair="BTC-USDT-PERP",
        side=SIDE_SHORT, price=Decimal("65000"), size=Decimal("1.5"), leverage=20
    )
    book.place_order(order_maker)

    # 2. Sinh viên B đặt lệnh LONG với giá chấp nhận khớp ngay (Taker)
    order_taker = FuturesOrder(
        order_id=102, user_id=2, pair="BTC-USDT-PERP",
        side=SIDE_LONG, price=Decimal("65000"), size=Decimal("1.0"), leverage=20
    )
    book.place_order(order_taker)

    # 3. Kiểm tra vị thế được tạo lập trong RAM
    print("\n--- DANH SÁCH VỊ THẾ HIỆN TẠI TRONG RAM ---")
    for uid, pos in book.positions.items():
        print(f"User {uid}: {pos}")

    # 4. Giả lập biến động giá Mark Price và kiểm tra PnL
    test_mark_price = Decimal("66000")
    print(f"\n--- KHI GIÁ THỊ TRƯỜNG BIẾN ĐỘNG LÊN {test_mark_price} USDT ---")
    for uid, pos in book.positions.items():
        pnl, roe = pos.calc_unrealized_pnl(test_mark_price)
        print(f"User {uid} ({pos.side}): Unrealized PnL = {pnl:+} USDT (ROE: {roe:+}%)")

    print("=" * 70)
