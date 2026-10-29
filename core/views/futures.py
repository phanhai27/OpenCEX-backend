#!/usr/bin/env python3
"""
=============================================================================
EDUCATIONAL TEMPLATE: FUTURES API VIEWS (LONG / SHORT ENDPOINTS)
=============================================================================
Vị trí trong hệ thống: backend/core/views/futures.py
Mục đích:
  - Cung cấp các API REST tiếp nhận lệnh Long/Short và tra cứu Vị thế.
  - Điểm chuyển giao sự kiện (Event Producer):
      Đóng gói JSON và gọi `place_futures_order.apply_async(queue='futures.orders.<PAIR>')`
=============================================================================
"""

import logging
from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated

logger = logging.getLogger("FuturesViews")


class FuturesOrdersView(APIView):
    """
    POST /api/v1/futures/orders/
    Tiếp nhận lệnh Long / Short từ người dùng.
    """
    permission_classes = (AllowAny,) # Trong thực tế dùng IsAuthenticated

    def post(self, request):
        data = request.data
        pair = data.get("pair", "BTC-USDT-PERP")
        side = data.get("side", "LONG").upper()
        price = data.get("price")
        size = data.get("size")
        leverage = int(data.get("leverage", 20))
        user_id = getattr(request.user, "id", None) or data.get("user_id", 1)

        if not price or not size:
            return Response(
                {"error": "Vui lòng cung cấp đầy đủ 'price' và 'size'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        order_payload = {
            "user_id": user_id,
            "pair": pair,
            "side": side,
            "price": str(price),
            "size": str(size),
            "leverage": leverage
        }

        logger.info(f"[API: FuturesOrdersView] Nhận lệnh từ Client: {order_payload}")

        # Chuyển sự kiện sang hàng đợi của Worker Khớp lệnh
        try:
            from core.tasks.futures import place_futures_order
            queue_name = f"futures.orders.{pair.upper()}"
            # Bắn task bất đồng bộ vào RabbitMQ / Redis broker
            place_futures_order.apply_async(args=[order_payload], queue=queue_name)
            logger.info(f"[EVENT_DISPATCH] Đã đẩy task vào queue `{queue_name}`")
        except Exception as e:
            logger.warning(f"[FALLBACK_DISPATCH] Không có Celery broker đang chạy, mô phỏng phản hồi: {e}")

        return Response({
            "status": "ACCEPTED",
            "message": f"Lệnh {side} {size} {pair} đòn bẩy {leverage}x đã được tiếp nhận và đưa vào hàng đợi xử lý.",
            "data": order_payload
        }, status=status.HTTP_201_CREATED)


class FuturesPositionsView(APIView):
    """
    GET /api/v1/futures/positions/
    Lấy danh sách các vị thế phái sinh đang mở của người dùng.
    """
    permission_classes = (AllowAny,)

    def get(self, request):
        user_id = getattr(request.user, "id", None) or 1
        # Mô phỏng danh sách vị thế trả về
        mock_positions = [
            {
                "user_id": user_id,
                "pair": "BTC-USDT-PERP",
                "side": "LONG",
                "size": "1.0",
                "entry_price": "65032.50",
                "margin": "3251.62",
                "leverage": 20,
                "liquidation_price": "62106.04",
                "unrealized_pnl": "+1467.50",
                "roe": "+45.13%"
            }
        ]
        return Response({"positions": mock_positions}, status=status.HTTP_200_OK)
