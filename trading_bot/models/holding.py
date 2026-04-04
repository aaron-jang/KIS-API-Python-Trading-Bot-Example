"""
보유(Holding) 도메인 모델

종목별 보유 현황을 나타냅니다.
기존 config.calculate_holdings()의 반환값을 구조화합니다.
"""
from dataclasses import dataclass


@dataclass
class Holding:
    ticker: str
    qty: int
    avg_price: float
    total_invested: float
    total_sold: float

    @classmethod
    def empty(cls, ticker: str) -> "Holding":
        return cls(ticker=ticker, qty=0, avg_price=0.0,
                   total_invested=0.0, total_sold=0.0)

    @property
    def is_empty(self) -> bool:
        return self.qty == 0

    @property
    def profit(self) -> float:
        return self.total_sold - self.total_invested

    @property
    def yield_pct(self) -> float:
        if self.total_invested == 0:
            return 0.0
        return (self.profit / self.total_invested) * 100.0

    def current_value(self, current_price: float) -> float:
        return self.qty * current_price

    def unrealized_pnl(self, current_price: float) -> float:
        return (current_price - self.avg_price) * self.qty
