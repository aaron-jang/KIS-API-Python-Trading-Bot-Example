"""
장부(Ledger) 저장소

ConfigManager의 장부 관련 CRUD + 보유현황 계산 메서드를
독립 클래스로 추출한 것입니다.
"""
import math
import time

from trading_bot.storage.file_utils import FileUtils


class LedgerStore:
    def __init__(self, fu: FileUtils, ledger_path: str,
                 history_path: str, split_history_path: str):
        self._fu = fu
        self._ledger_path = ledger_path
        self._history_path = history_path
        self._split_history_path = split_history_path

    def get_ledger(self) -> list:
        return self._fu.load_json(self._ledger_path, [])

    def _save_ledger(self, ledger: list):
        self._fu.save_json(self._ledger_path, ledger)

    def clear_for_ticker(self, ticker: str):
        ledger = self.get_ledger()
        remaining = [r for r in ledger if r["ticker"] != ticker]
        self._save_ledger(remaining)

    def overwrite_genesis(self, ticker: str, genesis_records: list, actual_avg: float):
        ledger = self.get_ledger()
        target_recs = [r for r in ledger if r["ticker"] == ticker]

        if len(target_recs) > 0:
            print(f"⚠️ [보안 차단] {ticker}의 장부 기록이 이미 존재하여 파괴적 Genesis 덮어쓰기를 차단했습니다.")
            return

        max_id = max([r.get("id", 0) for r in ledger] + [0])
        for i, rec in enumerate(genesis_records):
            max_id += 1
            ledger.append({
                "id": max_id,
                "date": rec["date"],
                "ticker": ticker,
                "side": rec["side"],
                "price": rec["price"],
                "qty": rec["qty"],
                "avg_price": actual_avg,
                "exec_id": f"GENESIS_{int(time.time())}_{i}",
                "desc": "✨과거기록복원",
                "is_reverse": False,
            })
        self._save_ledger(ledger)

    def overwrite_incremental(self, ticker: str, temp_recs: list,
                              new_today_records: list, is_reverse: bool = False):
        ledger = self.get_ledger()
        remaining = [r for r in ledger if r["ticker"] != ticker]
        updated = list(temp_recs)

        max_id = max([r.get("id", 0) for r in ledger] + [0])
        for i, rec in enumerate(new_today_records):
            max_id += 1
            new_row = {
                "id": max_id,
                "date": rec["date"],
                "ticker": ticker,
                "side": rec["side"],
                "price": rec["price"],
                "qty": rec["qty"],
                "avg_price": rec["avg_price"],
                "exec_id": rec.get("exec_id", f"FASTTRACK_{int(time.time())}_{i}"),
                "is_reverse": is_reverse,
            }
            if "desc" in rec:
                new_row["desc"] = rec["desc"]
            updated.append(new_row)

        remaining.extend(updated)
        self._save_ledger(remaining)

    def apply_stock_split(self, ticker: str, ratio: int):
        if ratio <= 0:
            return
        ledger = self.get_ledger()
        changed = False
        for r in ledger:
            if r.get("ticker") == ticker:
                new_qty = round(r["qty"] * ratio)
                r["qty"] = new_qty if new_qty > 0 else (1 if r["qty"] > 0 else 0)
                r["price"] = round(r["price"] / ratio, 4)
                if "avg_price" in r:
                    r["avg_price"] = round(r["avg_price"] / ratio, 4)
                changed = True
        if changed:
            self._save_ledger(ledger)

    def calculate_holdings(self, ticker: str, records: list = None):
        if records is None:
            records = self.get_ledger()
        target_recs = [r for r in records if r["ticker"] == ticker]
        total_qty, total_invested, total_sold = 0, 0.0, 0.0

        for r in target_recs:
            if r["side"] == "BUY":
                total_qty += r["qty"]
                total_invested += r["price"] * r["qty"]
            elif r["side"] == "SELL":
                total_qty -= r["qty"]
                total_sold += r["price"] * r["qty"]

        total_qty = max(0, int(total_qty))
        invested_up = math.ceil(total_invested * 100) / 100.0
        sold_up = math.ceil(total_sold * 100) / 100.0

        if total_qty == 0:
            avg_price = 0.0
        else:
            avg_price = 0.0
            if target_recs:
                avg_price = float(target_recs[-1].get("avg_price", 0.0))
                if avg_price == 0.0:
                    buy_sum = sum(r["price"] * r["qty"] for r in target_recs if r["side"] == "BUY")
                    buy_qty = sum(r["qty"] for r in target_recs if r["side"] == "BUY")
                    if buy_qty > 0:
                        avg_price = buy_sum / buy_qty

        return total_qty, avg_price, invested_up, sold_up

    def calculate_v14_state(self, ticker: str, seed: float, split: float):
        ledger = self.get_ledger()
        target_recs = sorted(
            [r for r in ledger if r["ticker"] == ticker],
            key=lambda x: x.get("id", 0),
        )

        base_portion = seed / split if split > 0 else 1
        holdings = 0
        rem_cash = seed
        total_invested = 0.0

        for r in target_recs:
            if holdings == 0:
                rem_cash = seed
                total_invested = 0.0

            qty = r["qty"]
            amt = qty * r["price"]

            if r["side"] == "BUY":
                rem_cash -= amt
                holdings += qty
                total_invested += amt
            elif r["side"] == "SELL":
                if qty >= holdings:
                    holdings = 0
                    rem_cash = seed
                    total_invested = 0.0
                else:
                    if holdings > 0:
                        avg_p = total_invested / holdings
                        total_invested -= qty * avg_p
                    holdings -= qty
                    rem_cash += amt

        avg_price = total_invested / holdings if holdings > 0 else 0.0
        t_val = (holdings * avg_price) / base_portion if base_portion > 0 else 0.0

        if holdings > 0:
            safe_denom = max(1.0, split - t_val)
            current_budget = rem_cash / safe_denom
        else:
            current_budget = base_portion
            t_val = 0.0

        return max(0.0, round(t_val, 4)), max(0.0, current_budget), max(0.0, rem_cash)

    def calibrate_prices(self, ticker: str, target_date_str: str, exec_history: list) -> int:
        if not exec_history:
            return 0

        buy_qty, buy_amt = 0, 0.0
        sell_qty, sell_amt = 0, 0.0

        for ex in exec_history:
            side_cd = ex.get("sll_buy_dvsn_cd")
            qty = int(float(ex.get("ft_ccld_qty", "0")))
            price = float(ex.get("ft_ccld_unpr3", "0"))
            if qty > 0 and price > 0:
                if side_cd == "02":
                    buy_qty += qty
                    buy_amt += qty * price
                elif side_cd == "01":
                    sell_qty += qty
                    sell_amt += qty * price

        actual_buy_price = round(buy_amt / buy_qty, 4) if buy_qty > 0 else 0.0
        actual_sell_price = round(sell_amt / sell_qty, 4) if sell_qty > 0 else 0.0

        if actual_buy_price == 0.0 and actual_sell_price == 0.0:
            return 0

        ledger = self.get_ledger()
        changed_count = 0

        for r in ledger:
            if r.get("ticker") == ticker and r.get("date") == target_date_str:
                exec_id = str(r.get("exec_id", ""))
                if "INIT" in exec_id:
                    continue
                if r["side"] == "BUY" and actual_buy_price > 0.0:
                    if abs(r["price"] - actual_buy_price) >= 0.01:
                        r["price"] = actual_buy_price
                        changed_count += 1
                elif r["side"] == "SELL" and actual_sell_price > 0.0:
                    if abs(r["price"] - actual_sell_price) >= 0.01:
                        r["price"] = actual_sell_price
                        changed_count += 1

        if changed_count > 0:
            self._save_ledger(ledger)
        return changed_count

    # ── Split History ──
    def get_last_split_date(self, ticker: str) -> str:
        return self._fu.load_json(self._split_history_path, {}).get(ticker, "")

    def set_last_split_date(self, ticker: str, date_str: str):
        d = self._fu.load_json(self._split_history_path, {})
        d[ticker] = date_str
        self._fu.save_json(self._split_history_path, d)

    # ── History ──
    def get_history(self) -> list:
        return self._fu.load_json(self._history_path, [])

    def save_history(self, history: list):
        self._fu.save_json(self._history_path, history)
