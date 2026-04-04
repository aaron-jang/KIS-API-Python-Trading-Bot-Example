"""
주문(Order) 도메인 모델

기존 코드에서 dict로 표현되던 주문 데이터를 타입이 있는 클래스로 정의합니다.
기존 dict 형식과의 양방향 변환(to_dict / from_dict)을 지원합니다.
"""
from dataclasses import dataclass
from enum import StrEnum


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    LOC = "LOC"
    LIMIT = "LIMIT"
    MOC = "MOC"
    MOO = "MOO"


@dataclass(frozen=True)
class Order:
    side: OrderSide
    price: float
    qty: int
    order_type: OrderType
    desc: str

    @property
    def amount(self) -> float:
        return self.price * self.qty

    def to_dict(self) -> dict:
        return {
            "side": str(self.side),
            "price": self.price,
            "qty": self.qty,
            "type": str(self.order_type),
            "desc": self.desc,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Order":
        return cls(
            side=OrderSide(d["side"]),
            price=d["price"],
            qty=d["qty"],
            order_type=OrderType(d["type"]),
            desc=d.get("desc", ""),
        )
