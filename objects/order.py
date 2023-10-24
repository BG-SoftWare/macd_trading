from decimal import Decimal


class Order:
    def __init__(self, ticker: str, order_id: str, order_type: str, position: str,
                 price: Decimal, status: str, order_time: int, reason: str = None):
        self.ticker = ticker
        self.order_id = order_id
        self.order_type = order_type
        self.position = position
        self.price = price
        self.status = status
        self.order_time = order_time
        self.close_reason = reason
