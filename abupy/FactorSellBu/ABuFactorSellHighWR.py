# -*- encoding:utf-8 -*-
"""
    高胜率卖出策略模块 — 快速止盈 + 时间止损
    核心逻辑：小目标快速止盈，配合最大持有天数时间止损
"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

import numpy as np

from .ABuFactorSellBase import AbuFactorSellBase, ESupportDirection

__author__ = 'abu_cn'


class AbuFactorSellQuickProfit(AbuFactorSellBase):
    """
    快速止盈卖出策略（高胜率版）

    核心思路：只在盈利时卖出，极端亏损时才止损。
    由于 sell_tomorrow 机制导致卖出价 = 次日均价，
    需要确保触发卖出时有足够利润缓冲。

    卖出条件（按优先级）：
    1. 止盈：收盘价高于买入价 profit_target_pct 以上
    2. 时间到期 + 盈利：超过 max_hold_days 且仍有正收益
    3. 硬止损：亏损超过 stop_loss_pct（保底安全网）
    """

    def _init_self(self, **kwargs):
        self.profit_target_pct = kwargs.get('profit_target_pct', 0.01)
        self.max_hold_days = kwargs.get('max_hold_days', 20)
        self.stop_loss_pct = kwargs.get('stop_loss_pct', -0.15)
        self.sell_type_extra_win = '{}:止盈{:.1f}%'.format(
            self.__class__.__name__, self.profit_target_pct * 100)
        self.sell_type_extra_time = '{}:到期止盈'.format(self.__class__.__name__)
        self.sell_type_extra_loss = '{}:止损'.format(self.__class__.__name__)

    def support_direction(self):
        return [ESupportDirection.DIRECTION_CAll.value]

    def _hold_days(self, order):
        buy_date_int = int(order.buy_date)
        count = 0
        start = max(0, self.today_ind - self.max_hold_days - 10)
        for ki in range(start, self.today_ind + 1):
            if int(self.kl_pd.iloc[ki].date) > buy_date_int:
                count += 1
        return count

    def fit_day(self, today, orders):
        for order in orders:
            if order.sell_type != 'keep':
                continue
            if int(today.date) <= int(order.buy_date):
                continue

            profit_pct = (today.close - order.buy_price) / order.buy_price
            hold = self._hold_days(order)

            # 1. 止盈：今日均价已盈利，用 sell_today 以今日价格成交
            today_avg = (today.high + today.low) / 2.0
            avg_profit_pct = (today_avg - order.buy_price) / order.buy_price
            if avg_profit_pct >= self.profit_target_pct:
                self.sell_type_extra = self.sell_type_extra_win
                self.sell_today(order)
                continue

            # 2. 到期：超过最大持有天数，只在今日均价盈利时卖
            if hold >= self.max_hold_days and avg_profit_pct > 0:
                self.sell_type_extra = self.sell_type_extra_time
                self.sell_today(order)
                continue

            # 3. 超期太久（2x），不论盈亏强制平仓
            if hold >= self.max_hold_days * 2:
                self.sell_type_extra = self.sell_type_extra_loss
                self.sell_today(order)
                continue

            # 4. 硬止损
            if profit_pct <= self.stop_loss_pct:
                self.sell_type_extra = self.sell_type_extra_loss
                self.sell_today(order)
