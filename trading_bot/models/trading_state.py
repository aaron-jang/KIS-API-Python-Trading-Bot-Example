"""
매매 상태(Trading State) 도메인 모델

리버스 모드 상태와 장부 레코드를 구조화합니다.
기존 config.py에서 dict로 관리되던 데이터의 타입 정의입니다.
"""
from dataclasses import dataclass, field


@dataclass
class ReverseState:
    is_active: bool
    day_count: int
    exit_target: float
    last_update_date: str = ""

    @classmethod
    def inactive(cls) -> "ReverseState":
        return cls(is_active=False, day_count=0,
                   exit_target=0.0, last_update_date="")

    @property
    def is_day_one(self) -> bool:
        return self.is_active and self.day_count == 1

    def to_dict(self) -> dict:
        return {
            "is_active": self.is_active,
            "day_count": self.day_count,
            "exit_target": self.exit_target,
            "last_update_date": self.last_update_date,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ReverseState":
        return cls(
            is_active=d.get("is_active", False),
            day_count=d.get("day_count", 0),
            exit_target=d.get("exit_target", 0.0),
            last_update_date=d.get("last_update_date", ""),
        )


@dataclass
class LedgerRecord:
    id: int
    date: str
    ticker: str
    side: str       # "BUY" or "SELL"
    price: float
    qty: int
    avg_price: float = 0.0
    exec_id: str = ""
    desc: str = ""
    is_reverse: bool = False

    @property
    def amount(self) -> float:
        return self.price * self.qty

    @property
    def is_buy(self) -> bool:
        return self.side == "BUY"

    @property
    def is_sell(self) -> bool:
        return self.side == "SELL"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "date": self.date,
            "ticker": self.ticker,
            "side": self.side,
            "price": self.price,
            "qty": self.qty,
            "avg_price": self.avg_price,
            "exec_id": self.exec_id,
            "desc": self.desc,
            "is_reverse": self.is_reverse,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LedgerRecord":
        return cls(
            id=d["id"],
            date=d["date"],
            ticker=d["ticker"],
            side=d["side"],
            price=d["price"],
            qty=d["qty"],
            avg_price=d.get("avg_price", 0.0),
            exec_id=d.get("exec_id", ""),
            desc=d.get("desc", ""),
            is_reverse=d.get("is_reverse", False),
        )
