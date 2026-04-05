# ==========================================================
# [strategy.py]
# ⚠️ 이 주석 및 파일명 표기는 절대 지우지 마세요.
# ==========================================================
import math
import os
import json
import tempfile
import pandas as pd
from datetime import datetime, timedelta
import pytz

class InfiniteStrategy:
    def __init__(self, config):
        self.cfg = config

    def _ceil(self, val): return math.ceil(val * 100) / 100.0
    def _floor(self, val): return math.floor(val * 100) / 100.0

    def _mark_quarter_sell_completed(self, ticker):
        flag_file = f"cache_sniper_sell_{ticker}.json"
        est = pytz.timezone('US/Eastern')
        today_str = datetime.now(est).strftime("%Y-%m-%d")

        if os.path.exists(flag_file):
            try:
                with open(flag_file, 'r') as f:
                    data = json.load(f)
                    if data.get("date") == today_str and data.get("QUARTER_SELL_COMPLETED"):
                        return
            except Exception:
                pass

        data = {"date": today_str, "QUARTER_SELL_COMPLETED": True}
        try:
            fd, temp_path = tempfile.mkstemp(dir=".")
            with os.fdopen(fd, 'w') as f:
                json.dump(data, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, flag_file)
        except Exception:
            pass

    # ==========================================================
    # 🛡️ [V23.12 패치] VWAP 시장 미시구조 거래량 지배력 코어 엔진
    # ==========================================================
    def analyze_vwap_dominance(self, df):
        """
        1분봉 데이터프레임을 받아 당일 VWAP 지배력을 연산합니다.
        df는 'Open', 'Close', 'Volume', 'High', 'Low' 컬럼이 존재해야 합니다.
        """
        if df is None or len(df) < 10:
            return {"vwap_price": 0.0, "is_strong_up": False, "is_strong_down": False}

        try:
            if 'High' in df.columns and 'Low' in df.columns:
                typical_price = (df['High'] + df['Low'] + df['Close']) / 3.0
            else:
                typical_price = df['Close']

            vol_x_price = typical_price * df['Volume']
            total_vol = df['Volume'].sum()

            if total_vol == 0:
                return {"vwap_price": 0.0, "is_strong_up": False, "is_strong_down": False}

            vwap_price = vol_x_price.sum() / total_vol

            # 누적 VWAP 기울기 연산
            df_temp = pd.DataFrame()
            df_temp['Volume'] = df['Volume']
            df_temp['Vol_x_Price'] = vol_x_price
            df_temp['Cum_Vol'] = df_temp['Volume'].cumsum()
            df_temp['Cum_Vol_Price'] = df_temp['Vol_x_Price'].cumsum()
            df_temp['Running_VWAP'] = df_temp['Cum_Vol_Price'] / df_temp['Cum_Vol']

            idx_10pct = int(len(df_temp) * 0.1)
            vwap_start = df_temp['Running_VWAP'].iloc[idx_10pct]
            vwap_end = df_temp['Running_VWAP'].iloc[-1]
            vwap_slope = vwap_end - vwap_start

            # 거래량 지배력 (VWAP 위/아래 체결량 비율)
            vol_above = df[df['Close'] > vwap_price]['Volume'].sum()
            vol_below = df[df['Close'] <= vwap_price]['Volume'].sum()

            vol_above_pct = vol_above / total_vol if total_vol > 0 else 0
            vol_below_pct = vol_below / total_vol if total_vol > 0 else 0

            daily_open = df['Open'].iloc[0] if 'Open' in df.columns else df['Close'].iloc[0]
            daily_close = df['Close'].iloc[-1]

            is_up_day = daily_close > daily_open
            is_down_day = daily_close < daily_open

            is_strong_up = is_up_day and (vwap_slope > 0) and (vol_above_pct > 0.5)
            is_strong_down = is_down_day and (vwap_slope < 0) and (vol_below_pct > 0.5)

            return {
                "vwap_price": round(vwap_price, 2),
                "is_strong_up": bool(is_strong_up),
                "is_strong_down": bool(is_strong_down),
                "vol_above_pct": round(vol_above_pct, 4),
                "vwap_slope": round(vwap_slope, 4)
            }
        except Exception as e:
            return {"vwap_price": 0.0, "is_strong_up": False, "is_strong_down": False}

    # ==========================================================
    # 추출된 서브 메서드들
    # ==========================================================

    def _apply_wash_trade_shield(self, c_orders, b_orders, sc_orders, sb_orders):
        """🛡️ KIS 자전거래(Wash-Trade) 원천 차단 방어벽 엔진"""
        all_o = c_orders + b_orders + sc_orders + sb_orders

        has_sell_moc = any(o['type'] in ['MOC', 'MOO'] and o['side'] == 'SELL' for o in all_o)
        s_prices = [o['price'] for o in all_o if o['side'] == 'SELL' and o['price'] > 0]
        min_s = min(s_prices) if s_prices else 0.0

        def _clean(lst):
            res = []
            for o in lst:
                if o['side'] == 'BUY':
                    if has_sell_moc and o['type'] in ['LOC', 'MOC']:
                        continue
                    if min_s > 0 and o['price'] >= min_s:
                        o['price'] = round(min_s - 0.01, 2)
                        if "🛡️" not in o['desc']:
                            o['desc'] = f"🛡️교정_{o['desc'].replace('🦇', '').replace('🧹', '')}"
                    o['price'] = max(0.01, o['price'])
                res.append(o)
            return res

        return _clean(c_orders), _clean(b_orders), _clean(sc_orders), _clean(sb_orders)

    def _apply_sniper_lock_filter(self, core_orders, bonus_orders, version, is_reverse,
                                   lock_s_sell, lock_s_buy, t_val, split, process_status):
        """스나이퍼 잠금 상태에 따른 주문 필터 및 상태 갱신"""
        if lock_s_sell:
            if not is_reverse:
                if version == "V17" and t_val < (split / 2):
                    process_status = "🔫전반전(명중/성장중)"
                else:
                    process_status = "🔫스나이퍼(명중)"
            else:
                process_status = "🔫리버스(명중)"

        if lock_s_buy and version == "V17":
            core_orders = [o for o in core_orders if o['side'] != 'BUY']
            bonus_orders = [o for o in bonus_orders if o['side'] != 'BUY']
            process_status = "💥가로채기(명중)"

        return core_orders, bonus_orders, process_status

    def _generate_jupjup_orders(self, one_portion_amt, base_price, ceiling_price, prefix="🧹줍줍"):
        """줍줍(보너스) 매수 주문 생성"""
        orders = []
        base_qty = math.floor(one_portion_amt / base_price) if base_price > 0 else 0
        if base_qty > 0:
            for i in range(1, 6):
                jup_price = self._floor(one_portion_amt / (base_qty + i))
                capped = round(min(jup_price, ceiling_price - 0.01), 2)
                if capped > 0:
                    orders.append({
                        "side": "BUY", "price": max(0.01, capped),
                        "qty": 1, "type": "LOC", "desc": f"{prefix}({i})"
                    })
        return orders

    def _build_result(self, core_orders, bonus_orders, smart_core_orders, smart_bonus_orders,
                      t_val, one_portion_amt, process_status, is_reverse, star_price,
                      star_ratio, real_available_cash, tr_info):
        """반환 딕셔너리 조립"""
        orders = core_orders + bonus_orders
        return {
            "orders": orders, "core_orders": core_orders, "bonus_orders": bonus_orders,
            "smart_core_orders": smart_core_orders, "smart_bonus_orders": smart_bonus_orders,
            "t_val": t_val, "one_portion": one_portion_amt, "process_status": process_status,
            "is_reverse": is_reverse, "star_price": star_price, "star_ratio": star_ratio,
            "real_cash_used": real_available_cash, "tracking_info": tr_info
        }

    def _resolve_trading_context(self, ticker, qty, avg_price, current_price, prev_close,
                                  ma_5day, market_type, available_cash, is_simulation):
        """설정 로드 및 핵심 파라미터 계산"""
        lock_s_sell = self.cfg.check_lock(ticker, "SNIPER_SELL")
        lock_s_buy = self.cfg.check_lock(ticker, "SNIPER_BUY")

        other_locked = self.cfg.get_total_locked_cash(exclude_ticker=ticker)
        real_available_cash = max(0, available_cash - other_locked)

        split = self.cfg.get_split_count(ticker)
        target_pct_val = self.cfg.get_target_profit(ticker)
        target_ratio = target_pct_val / 100.0
        version = self.cfg.get_version(ticker)

        rev_state = self.cfg.get_reverse_state(ticker)
        is_reverse = rev_state.get("is_active", False)
        rev_day = rev_state.get("day_count", 0)
        exit_target = rev_state.get("exit_target", 0.0)

        t_val, base_portion = self.cfg.get_absolute_t_val(ticker, qty, avg_price)
        target_price = self._ceil(avg_price * (1 + target_ratio)) if avg_price > 0 else 0
        is_jackpot_reached = target_price > 0 and current_price >= target_price

        # V14/V17 동적 예산
        if version in ["V14", "V17"]:
            _, dynamic_budget, rem_cash = self.cfg.calculate_v14_state(ticker)
            one_portion_amt = dynamic_budget

            is_money_short_check = False if (is_simulation or market_type == "PRE_CHECK") else (real_available_cash < one_portion_amt)

            if not is_reverse and (t_val > (split - 1) or (qty > 0 and is_money_short_check)):
                if not is_jackpot_reached:
                    is_reverse = True
                    rev_day = 1
                    current_return = (current_price - avg_price) / avg_price * 100.0 if avg_price > 0 else 0.0
                    default_exit = -15.0 if ticker == "TQQQ" else -20.0
                    exit_target = 0.0 if current_return >= default_exit else default_exit
        else:
            one_portion_amt = base_portion

        # 별값(Star) 가격 계산
        depreciation_factor = 2.0 / split if split > 0 else 0.1
        star_ratio = target_ratio - (target_ratio * depreciation_factor * t_val)

        if is_reverse:
            star_price = round(ma_5day, 2) if ma_5day > 0 else self._ceil(avg_price)
            # 리버스 매도 수익금 기반 예산 재계산
            ledger = self.cfg.get_ledger()
            total_sell_amount = 0.0
            for r in reversed(ledger):
                if r.get('ticker') == ticker:
                    if r.get('is_reverse', False):
                        if r['side'] == 'SELL':
                            total_sell_amount += (r['qty'] * r['price'])
                    else:
                        break
            if total_sell_amount > 0:
                one_portion_amt = total_sell_amount / 4.0
            else:
                one_portion_amt = base_portion
        else:
            star_price = self._ceil(avg_price * (1 + star_ratio)) if avg_price > 0 else 0

        is_last_lap = (split - 1) < t_val < split
        is_money_short = False if is_simulation else (real_available_cash < one_portion_amt)

        base_price = current_price if current_price > 0 else prev_close

        return {
            "lock_s_sell": lock_s_sell, "lock_s_buy": lock_s_buy,
            "real_available_cash": real_available_cash,
            "split": split, "target_ratio": target_ratio, "version": version,
            "is_reverse": is_reverse, "rev_day": rev_day, "exit_target": exit_target,
            "t_val": t_val, "base_portion": base_portion,
            "target_price": target_price, "is_jackpot_reached": is_jackpot_reached,
            "one_portion_amt": one_portion_amt,
            "star_price": star_price, "star_ratio": star_ratio,
            "is_last_lap": is_last_lap, "is_money_short": is_money_short,
            "base_price": base_price,
        }

    def _generate_premarket_orders(self, ctx, qty, current_price):
        """프리마켓 주문 생성"""
        core_orders = []
        if qty > 0 and ctx["target_price"] > 0 and current_price >= ctx["target_price"] and not ctx["is_reverse"]:
            core_orders.append({"side": "SELL", "price": current_price, "qty": qty, "type": "LIMIT", "desc": "🌅프리:목표돌파익절"})
        return core_orders, "🌅프리마켓"

    def _generate_new_start_orders(self, ctx):
        """새출발(qty=0) 주문 생성"""
        core_orders = []
        buy_price = max(0.01, round(self._ceil(ctx["base_price"] * 1.15) - 0.01, 2))
        buy_qty = math.floor(ctx["one_portion_amt"] / buy_price) if buy_price > 0 else 0
        if buy_qty > 0:
            core_orders.append({"side": "BUY", "price": buy_price, "qty": buy_qty, "type": "LOC", "desc": "🆕새출발"})
        return core_orders, "✨새출발"

    def _generate_reverse_orders(self, ctx, qty):
        """리버스 모드 주문 생성"""
        core_orders = []
        bonus_orders = []
        split = ctx["split"]
        rev_day = ctx["rev_day"]
        star_price = ctx["star_price"]
        one_portion_amt = ctx["one_portion_amt"]
        lock_s_sell = ctx["lock_s_sell"]
        base_price = ctx["base_price"]
        real_available_cash = ctx["real_available_cash"]

        sell_divisor = 10 if split <= 20 else 20
        sell_qty = qty if qty < 4 else max(4, math.floor(qty / sell_divisor))

        is_emergency = (real_available_cash < base_price) and (rev_day > 1)

        if rev_day == 1 or is_emergency:
            process_status = "🩸리버스(긴급수혈)" if is_emergency else "🚨리버스(1일차)"
            if sell_qty > 0:
                desc = "🩸수혈매도" if is_emergency else "🛡️의무매도"
                if qty < 4:
                    desc = "💥잔량청산(수량부족)"
                core_orders.append({"side": "SELL", "price": 0, "qty": sell_qty, "type": "MOC", "desc": desc})
        else:
            process_status = f"🔄리버스({rev_day}일차)"
            buy_qty = 0
            buy_price = 0
            if one_portion_amt > 0 and star_price > 0:
                buy_price = max(0.01, round(star_price - 0.01, 2))
                if buy_price > 0:
                    buy_qty = math.floor(one_portion_amt / buy_price)
                    if buy_qty > 0:
                        core_orders.append({"side": "BUY", "price": buy_price, "qty": buy_qty, "type": "LOC", "desc": "⚓잔금매수"})

            if not lock_s_sell and sell_qty > 0 and star_price > 0:
                core_orders.append({"side": "SELL", "price": star_price, "qty": sell_qty, "type": "LOC", "desc": "🌟별값매도"})

            if one_portion_amt > 0 and buy_price > 0:
                for i in range(1, 6):
                    target_qty = buy_qty + i
                    raw_jup = self._floor(one_portion_amt / target_qty)
                    capped = min(raw_jup, buy_price - 0.01)
                    jup_price = max(0.01, round(capped, 2))
                    if jup_price > 0:
                        bonus_orders.append({"side": "BUY", "price": jup_price, "qty": 1, "type": "LOC", "desc": f"🧹리버스줍줍({i})"})

        return core_orders, bonus_orders, process_status

    def _generate_normal_orders(self, ctx, qty, avg_price):
        """정규장 일반매매 주문 생성"""
        core_orders = []
        bonus_orders = []
        split = ctx["split"]
        t_val = ctx["t_val"]
        one_portion_amt = ctx["one_portion_amt"]
        star_price = ctx["star_price"]
        target_price = ctx["target_price"]
        is_money_short = ctx["is_money_short"]
        is_last_lap = ctx["is_last_lap"]
        is_jackpot_reached = ctx["is_jackpot_reached"]
        is_simulation = False  # normal path는 is_simulation이 False일 때만 진입
        lock_s_sell = ctx["lock_s_sell"]

        # 상태 판별
        if is_jackpot_reached and (t_val > (split - 1) or is_money_short):
            process_status = "🎉대박익절(리버스생략)"
        elif is_last_lap:
            process_status = "🏁마지막회차"
        elif is_money_short:
            process_status = "🛡️방어모드(부족)"
        elif t_val < (split / 2):
            process_status = "🌓전반전"
        else:
            process_status = "🌕후반전"

        if t_val > (split * 1.1):
            process_status = "🚨T값폭주(역산경고)"

        can_buy = not is_money_short and not is_last_lap
        safe_ceiling = min(avg_price, star_price) if star_price > 0 else avg_price
        N = math.floor(one_portion_amt / avg_price) if avg_price > 0 else 0
        p_avg = max(0.01, round(min(self._ceil(avg_price) - 0.01, safe_ceiling - 0.01), 2))

        # 매수 주문
        if can_buy:
            p_star = max(0.01, round(star_price - 0.01, 2))
            if t_val < (split / 2):
                half_amt = one_portion_amt * 0.5
                q_avg_init = math.floor(half_amt / p_avg) if p_avg > 0 else 0
                q_star = math.floor(half_amt / p_star) if p_star > 0 else 0
                total_basic = q_avg_init + q_star
                q_avg = q_avg_init + (N - total_basic) if total_basic < N else q_avg_init
                if q_avg > 0:
                    core_orders.append({"side": "BUY", "price": p_avg, "qty": q_avg, "type": "LOC", "desc": "⚓평단매수"})
                if q_star > 0:
                    core_orders.append({"side": "BUY", "price": p_star, "qty": q_star, "type": "LOC", "desc": "💫별값매수"})
            else:
                if star_price > 0:
                    p_star = max(0.01, round(star_price - 0.01, 2))
                    q_star = math.floor(one_portion_amt / p_star)
                    if q_star > 0:
                        core_orders.append({"side": "BUY", "price": p_star, "qty": q_star, "type": "LOC", "desc": "💫별값매수"})

        # 줍줍
        if one_portion_amt > 0 and not is_money_short:
            bonus_orders = self._generate_jupjup_orders(one_portion_amt, avg_price, avg_price)

        # 매도 주문
        if qty > 0 and not lock_s_sell:
            q_qty = math.ceil(qty / 4)
            rem_qty = qty - q_qty
            if star_price > 0 and q_qty > 0:
                core_orders.append({"side": "SELL", "price": star_price, "qty": q_qty, "type": "LOC", "desc": "🌟별값매도"})
            if target_price > 0 and rem_qty > 0:
                core_orders.append({"side": "SELL", "price": target_price, "qty": rem_qty, "type": "LIMIT", "desc": "🎯목표매도"})

        return core_orders, bonus_orders, process_status

    # ==========================================================
    # 메인 진입점
    # ==========================================================

    def get_plan(self, ticker, current_price, avg_price, qty, prev_close, ma_5day=0.0, market_type="REG", available_cash=0, is_simulation=False, vwap_status=None):
        smart_core_orders = []
        smart_bonus_orders = []
        tr_info = {"vwap_status": vwap_status} if vwap_status else {}

        # 스나이퍼 잠금 캐시 각인
        lock_s_sell = self.cfg.check_lock(ticker, "SNIPER_SELL")
        if lock_s_sell and not is_simulation:
            self._mark_quarter_sell_completed(ticker)

        # 설정 및 핵심 파라미터 계산
        ctx = self._resolve_trading_context(
            ticker, qty, avg_price, current_price, prev_close,
            ma_5day, market_type, available_cash, is_simulation
        )

        # 가격 오류 방어
        if ctx["base_price"] <= 0:
            return self._build_result([], [], [], [], ctx["t_val"], ctx["one_portion_amt"],
                                       "⛔가격오류", ctx["is_reverse"], ctx["star_price"],
                                       ctx["star_ratio"], ctx["real_available_cash"], tr_info)

        # 프리마켓
        if market_type == "PRE_CHECK":
            core_orders, status = self._generate_premarket_orders(ctx, qty, current_price)
            return self._build_result(core_orders, [], [], [], ctx["t_val"], ctx["one_portion_amt"],
                                       status, ctx["is_reverse"], ctx["star_price"],
                                       ctx["star_ratio"], ctx["real_available_cash"], tr_info)

        # 정규장
        if market_type == "REG":
            # 새출발
            if qty == 0:
                core_orders, status = self._generate_new_start_orders(ctx)
                return self._build_result(core_orders, [], [], [], ctx["t_val"], ctx["one_portion_amt"],
                                           status, False, ctx["star_price"],
                                           ctx["star_ratio"], ctx["real_available_cash"], tr_info)

            # 리버스
            if ctx["is_reverse"]:
                core_orders, bonus_orders, status = self._generate_reverse_orders(ctx, qty)
                core_orders, bonus_orders, status = self._apply_sniper_lock_filter(
                    core_orders, bonus_orders, ctx["version"], True,
                    ctx["lock_s_sell"], ctx["lock_s_buy"], ctx["t_val"], ctx["split"], status)
                core_orders, bonus_orders, smart_core_orders, smart_bonus_orders = \
                    self._apply_wash_trade_shield(core_orders, bonus_orders, smart_core_orders, smart_bonus_orders)
                return self._build_result(core_orders, bonus_orders, [], [], ctx["t_val"], ctx["one_portion_amt"],
                                           status, True, ctx["star_price"],
                                           ctx["star_ratio"], ctx["real_available_cash"], tr_info)

            # 일반매매
            core_orders, bonus_orders, status = self._generate_normal_orders(ctx, qty, avg_price)

            # is_simulation에서도 줍줍 생성 (기존 동작 보존)
            if is_simulation and ctx["one_portion_amt"] > 0 and not bonus_orders:
                bonus_orders = self._generate_jupjup_orders(ctx["one_portion_amt"], avg_price, avg_price)

            core_orders, bonus_orders, status = self._apply_sniper_lock_filter(
                core_orders, bonus_orders, ctx["version"], False,
                ctx["lock_s_sell"], ctx["lock_s_buy"], ctx["t_val"], ctx["split"], status)
            core_orders, bonus_orders, smart_core_orders, smart_bonus_orders = \
                self._apply_wash_trade_shield(core_orders, bonus_orders, smart_core_orders, smart_bonus_orders)
            return self._build_result(core_orders, bonus_orders, smart_core_orders, smart_bonus_orders,
                                       ctx["t_val"], ctx["one_portion_amt"], status, ctx["is_reverse"],
                                       ctx["star_price"], ctx["star_ratio"], ctx["real_available_cash"], tr_info)
