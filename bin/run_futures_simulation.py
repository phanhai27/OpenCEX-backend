#!/usr/bin/env python3
"""
=============================================================================
MASTER EDUCATIONAL DEMO: FULL LIFECYCLE SIMULATION OF FUTURES ENGINE
=============================================================================
Vị trí trong hệ thống: backend/bin/run_futures_simulation.py
Mục đích:
  - Một file chạy độc lập duy nhất giúp sinh viên quan sát toàn bộ chuỗi mắt xích
    hoạt động của hệ sinh thái Long / Short (Futures) qua 6 giai đoạn:
      Giai đoạn 1: Khởi động Matching Worker & Sổ lệnh in-memory.
      Giai đoạn 2: Bot Market Maker bơm thanh khoản hai đầu.
      Giai đoạn 3: Người dùng đặt lệnh Long x20 -> Khớp lệnh -> Sinh Vị thế.
      Giai đoạn 4: Oracle cập nhật giá Mark Price -> Bắn WebSocket cập nhật PnL.
      Giai đoạn 5: Kích hoạt chu kỳ thanh toán phí Funding Rate.
      Giai đoạn 6: Thị trường sụt giảm mạnh -> Kích hoạt Liquidation Worker ép bán.
=============================================================================
"""

import sys
import os
import time
from decimal import Decimal

# Thêm đường dẫn thư mục backend vào python path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import importlib.util

def _load_module(module_name: str, rel_path: str):
    abs_path = os.path.join(backend_dir, rel_path)
    spec = importlib.util.spec_from_file_location(module_name, abs_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod

# Load trực tiếp các module template độc lập
_fb = _load_module("futures_book", "core/orderbook/futures_book.py")
FuturesOrderBook = _fb.FuturesOrderBook
FuturesOrder = _fb.FuturesOrder
SIDE_LONG = _fb.SIDE_LONG
SIDE_SHORT = _fb.SIDE_SHORT

_mm = _load_module("futures_mm", "bots/futures_mm.py")
FuturesMarketMakerBot = _mm.FuturesMarketMakerBot

_ft = _load_module("futures_tasks", "core/tasks/futures.py")
check_liquidations = _ft.check_liquidations
update_mark_price = _ft.update_mark_price
settle_funding_rate = _ft.settle_funding_rate

_fn = _load_module("futures_notifications", "exchange/futures_notifications.py")
FuturesPositionNotificator = _fn.FuturesPositionNotificator
MarkPriceNotificator = _fn.MarkPriceNotificator
LiquidationNotificator = _fn.LiquidationNotificator

# Màu ANSI in ra console
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_stage_banner(stage_num: int, title: str):
    print(f"\n{BOLD}{CYAN}{'=' * 75}{RESET}")
    print(f"{BOLD}{CYAN}GIAI ĐOẠN {stage_num}: {title.upper()}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 75}{RESET}")
    time.sleep(0.4)


def run_simulation():
    print(f"\n{BOLD}{GREEN}*** BẮT ĐẦU MÔ PHỎNG HỆ SINH THÁI LONG / SHORT (FUTURES ENGINE) ***{RESET}\n")

    # =========================================================================
    # GIAI ĐOẠN 1: KHỞI ĐỘNG MATCHING WORKER & ORDERBOOK
    # =========================================================================
    print_stage_banner(1, "Khởi động Matching Worker & Khởi tạo Sổ lệnh RAM")
    print(f"{YELLOW}[Step 1.1]{RESET} Tiến trình `futures_stack.py` khởi chạy, nhận Distributed Lock trên Redis...")
    time.sleep(0.3)
    pair = "BTC-USDT-PERP"
    book = FuturesOrderBook(pair=pair)
    print(f"{GREEN}[OK]{RESET} Sổ lệnh phái sinh `{pair}` đã sẵn sàng trong RAM (Buys/Sells Stack rỗng).")

    # =========================================================================
    # GIAI ĐOẠN 2: BOT MARKET MAKER TẠO THANH KHOẢN MỒI
    # =========================================================================
    print_stage_banner(2, "Market Maker Bot (MM Bot) Bơm Thanh Khoản Hai Đầu")
    print(f"{YELLOW}[Step 2.1]{RESET} Bot lấy giá tham chiếu từ Oracle: 65,000 USDT.")
    mm_bot = FuturesMarketMakerBot(pair=pair, spread_pct=Decimal("0.001"), order_size=Decimal("3.0"))
    bid_p, ask_p = mm_bot.calculate_quotes(Decimal("65000"))

    # Bot treo 1 lệnh Short làm đối ứng thanh khoản
    mm_short_order = FuturesOrder(
        order_id=1, user_id=999, pair=pair, side=SIDE_SHORT,
        price=ask_p, size=Decimal("3.0"), leverage=20
    )
    book.place_order(mm_short_order)
    print(f"{GREEN}[OK]{RESET} Bot MM đã treo lệnh SHORT {mm_short_order.size} BTC @ {ask_p} USDT.")

    # =========================================================================
    # GIAI ĐOẠN 3: TRADER ĐẶT LỆNH LONG -> KHỚP LỆNH -> SINH VỊ THẾ
    # =========================================================================
    print_stage_banner(3, "Trader Đặt Lệnh LONG x20 & Khớp Lệnh Mở Vị Thế")
    print(f"{YELLOW}[Step 3.1]{RESET} Sinh viên A (User #10) gửi lệnh: LONG 1.0 BTC @ {ask_p} USDT (Đòn bẩy 20x).")

    trader_order = FuturesOrder(
        order_id=2, user_id=10, pair=pair, side=SIDE_LONG,
        price=ask_p, size=Decimal("1.0"), leverage=20
    )
    trades = book.place_order(trader_order)

    # Lấy vị thế vừa tạo
    user_pos = book.positions[10]
    print(f"{GREEN}[OK]{RESET} Khớp lệnh thành công! Thông tin vị thế mới:")
    print(f"   -> Khối lượng vị thế: {user_pos.size} BTC")
    print(f"   -> Giá vào lệnh (Entry): {user_pos.entry_price} USDT")
    print(f"   -> Ký quỹ ban đầu (Margin): {user_pos.initial_margin} USDT")
    print(f"   -> Giá thanh lý (Liquidation Price): {BOLD}{RED}{user_pos.liquidation_price} USDT{RESET}")

    # Bắn WebSocket cho Trader
    pos_notifier = FuturesPositionNotificator()
    pos_notifier.notify_position_update(user_id=10, position_data={
        "pair": pair, "side": user_pos.side, "size": user_pos.size,
        "entry_price": user_pos.entry_price, "unrealized_pnl": "0.00", "roe": "0.00%",
        "liq_price": user_pos.liquidation_price
    })

    # =========================================================================
    # GIAI ĐOẠN 4: ORACLE CẬP NHẬT GIÁ MARK PRICE -> PNL TĂNG TRƯỞNG
    # =========================================================================
    print_stage_banner(4, "Oracle Cập Nhật Mark Price Tăng -> Bắn PnL Realtime")
    pump_price = Decimal("66500")
    print(f"{YELLOW}[Step 4.1]{RESET} Giá thị trường thế giới tăng mạnh lên {pump_price} USDT.")

    mark_notifier = MarkPriceNotificator()
    mark_notifier.notify_mark_price(pair, str(pump_price))

    pnl, roe = user_pos.calc_unrealized_pnl(pump_price)
    print(f"{GREEN}[OK]{RESET} Vị thế User #10 đang có lãi:")
    print(f"   -> Lãi chưa chốt (Unrealized PnL): {BOLD}{GREEN}+{pnl} USDT{RESET}")
    print(f"   -> Tỷ suất sinh lời (ROE): {BOLD}{GREEN}+{roe}%{RESET}")

    pos_notifier.notify_position_update(user_id=10, position_data={
        "pair": pair, "side": user_pos.side, "size": user_pos.size,
        "entry_price": user_pos.entry_price, "unrealized_pnl": f"+{pnl}", "roe": f"+{roe}%",
        "liq_price": user_pos.liquidation_price
    })

    # =========================================================================
    # GIAI ĐOẠN 5: CHU KỲ THANH TOÁN FUNDING RATE (CELERY BEAT 8H)
    # =========================================================================
    print_stage_banner(5, "Chu Kỳ Celery Beat Thanh Toán Phí Funding Rate")
    print(f"{YELLOW}[Step 5.1]{RESET} Celery Beat kích hoạt task `settle_funding_rate` lúc 08:00 UTC...")
    settle_funding_rate(pair=pair, current_rate=Decimal("0.0001"))
    funding_fee = user_pos.size * user_pos.entry_price * Decimal("0.0001")
    print(f"{GREEN}[OK]{RESET} User #10 (phe LONG) bị khấu trừ {round(funding_fee, 2)} USDT phí funding trả cho phe SHORT.")

    # =========================================================================
    # GIAI ĐOẠN 6: THỊ TRƯỜNG LAO DỐC -> LIQUIDATION WORKER ÉP BÁN
    # =========================================================================
    print_stage_banner(6, "Thị Trường Lao Dốc -> Liquidation Worker Cưỡng Chế Thanh Lý")
    crash_price = Decimal("61900") # Rớt sâu dưới mức liq 62,075
    print(f"{RED}[FLASH CRASH]{RESET} Giá thị trường bất ngờ rơi tự do xuống {BOLD}{crash_price} USDT{RESET}!")

    simulated_pos_list = [{
        "user_id": 10, "pair": pair, "side": user_pos.side, "size": user_pos.size,
        "entry": user_pos.entry_price, "liq_price": user_pos.liquidation_price
    }]

    # Worker quét phát hiện chạm ngưỡng cháy
    check_liquidations(current_mark_price=crash_price, simulated_positions=simulated_pos_list)

    # Bắn cảnh báo thanh lý ra toàn sàn
    liq_notifier = LiquidationNotificator()
    liq_notifier.notify_liquidation(pair, user_pos.side, str(user_pos.size), str(crash_price))

    print(f"\n{BOLD}{GREEN}{'=' * 75}{RESET}")
    print(f"{BOLD}{GREEN}HOÀN THÀNH TOÀN BỘ KỊCH BẢN MÔ PHỎNG HỆ SINH THÁI LONG / SHORT!{RESET}")
    print(f"{BOLD}{GREEN}{'=' * 75}{RESET}\n")


if __name__ == "__main__":
    run_simulation()
