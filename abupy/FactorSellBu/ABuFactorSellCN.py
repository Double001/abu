# -*- encoding:utf-8 -*-
"""
    A股市场专用卖出择时因子模块：
    1. T+1限制止损策略 (T+1 Stop Loss)
    2. 涨跌停自适应卖出策略 (Price Limit Adaptive Sell)
    3. 均线死叉卖出策略 (MA Death Cross Sell)
"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

import numpy as np

from .ABuFactorSellBase import AbuFactorSellBase, ESupportDirection

__author__ = 'abu_cn'


class AbuFactorSellT1StopCN(AbuFactorSellBase):
    """
    A股T+1止损策略：
    强制执行T+1规则（买入当日不能卖出），并在T+1之后根据ATR止损。
    stop_loss_n: ATR止损倍数（默认1.5倍）
    stop_win_n: ATR止盈倍数（默认3.0倍）
    """

    def _init_self(self, **kwargs):
        self.stop_loss_n = kwargs.get('stop_loss_n', 1.5)
        self.stop_win_n = kwargs.get('stop_win_n', 3.0)
        self.sell_type_extra_loss = '{}:T1_loss={}'.format(
            self.__class__.__name__, self.stop_loss_n)
        self.sell_type_extra_win = '{}:T1_win={}'.format(
            self.__class__.__name__, self.stop_win_n)

    def support_direction(self):
        return [ESupportDirection.DIRECTION_CAll.value]

    def _is_t1_ok(self, today, order):
        """T+1: buy_date当天不能卖，至少要到下一个交易日"""
        return int(today.date) > int(order.buy_date)

    def fit_day(self, today, orders):
        for order in orders:
            if not self._is_t1_ok(today, order):
                continue

            profit = (today.close - order.buy_price) * order.expect_direction
            stop_base = today.atr21 + today.atr14

            if profit > 0 and profit > self.stop_win_n * stop_base:
                self.sell_type_extra = self.sell_type_extra_win
                self.sell_tomorrow(order)
            elif profit < 0 and profit < -self.stop_loss_n * stop_base:
                self.sell_type_extra = self.sell_type_extra_loss
                order.fit_sell_order(self.today_ind, self)
                self.sell_tomorrow(order)


class AbuFactorSellPriceLimitCN(AbuFactorSellBase):
    """
    A股涨跌停自适应卖出策略：
    - 跌停时不卖出（模拟无法成交）
    - 连续跌停后首次打开跌停立即卖出
    - 触及止损线时在非跌停日卖出
    """

    def _init_self(self, **kwargs):
        self.stop_loss_pct = kwargs.get('stop_loss_pct', -0.15)
        self.limit_down_pct = kwargs.get('limit_down_pct', -0.095)
        self._consecutive_limit_down = {}
        self.sell_type_extra_limit = '{}:limit_sell'.format(self.__class__.__name__)
        self.sell_type_extra_stop = '{}:stop_loss={}'.format(
            self.__class__.__name__, self.stop_loss_pct)

    def support_direction(self):
        return [ESupportDirection.DIRECTION_CAll.value]

    def _is_limit_down(self, today):
        return (today.p_change <= self.limit_down_pct * 100
                and today.low == today.close)

    def fit_day(self, today, orders):
        for order in orders:
            if int(today.date) <= int(order.buy_date):
                continue

            oid = id(order)
            is_ld = self._is_limit_down(today)

            if is_ld:
                self._consecutive_limit_down[oid] = \
                    self._consecutive_limit_down.get(oid, 0) + 1
                continue

            if self._consecutive_limit_down.get(oid, 0) > 0:
                self.sell_type_extra = self.sell_type_extra_limit
                self._consecutive_limit_down[oid] = 0
                self.sell_tomorrow(order)
                continue

            profit_pct = (today.close - order.buy_price) / order.buy_price
            if profit_pct < self.stop_loss_pct:
                self.sell_type_extra = self.sell_type_extra_stop
                order.fit_sell_order(self.today_ind, self)
                self.sell_tomorrow(order)


class AbuFactorSellMACrossCN(AbuFactorSellBase):
    """
    A股均线死叉卖出策略：
    短期均线下穿中期均线时产生卖出信号。
    """

    def _init_self(self, **kwargs):
        self.ma_short = kwargs.get('ma_short', 5)
        self.ma_long = kwargs.get('ma_long', 20)
        self.sell_type_extra = '{}:ma={}/{}'.format(
            self.__class__.__name__, self.ma_short, self.ma_long)

    def support_direction(self):
        return [ESupportDirection.DIRECTION_CAll.value]

    def fit_day(self, today, orders):
        if self.today_ind < self.ma_long + 1:
            return

        closes = self.kl_pd.close[:self.today_ind + 1]
        ma_s_today = closes.iloc[-self.ma_short:].mean()
        ma_l_today = closes.iloc[-self.ma_long:].mean()
        ma_s_yest = closes.iloc[-self.ma_short - 1:-1].mean()
        ma_l_yest = closes.iloc[-self.ma_long - 1:-1].mean()

        if ma_s_yest >= ma_l_yest and ma_s_today < ma_l_today:
            for order in orders:
                if int(today.date) <= int(order.buy_date):
                    continue
                self.sell_tomorrow(order)
