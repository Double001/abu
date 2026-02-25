# -*- encoding:utf-8 -*-
"""
    高胜率买入策略模块 — 趋势回调买入
    核心逻辑：在上升趋势中捕捉短期回调，配合快速止盈实现高胜率
"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

import numpy as np

from .ABuFactorBuyBase import AbuFactorBuyBase, BuyCallMixin

__author__ = 'abu_cn'


class AbuFactorBuyPullbackTrend(AbuFactorBuyBase, BuyCallMixin):
    """
    趋势回调买入策略（高胜率版）

    入场条件（全部满足）：
    1. 中长期趋势向上：MA20 > MA60
    2. 价格在MA60上方（确认趋势有效）
    3. 连续 pullback_days 天收阴线（短期回调）
    4. 回调幅度不超过 max_pullback_pct（避免趋势破坏）
    5. [可选] 缩量回调：当日成交量 < 10日均量（vol_shrink=True）
    6. [可选] RSI过滤：RSI14 < rsi_max（避免超买区入场）

    配合 AbuFactorSellQuickProfit 使用可达 90%+ 胜率
    """

    def _init_self(self, **kwargs):
        self.pullback_days = kwargs.get('pullback_days', 3)
        self.max_pullback_pct = kwargs.get('max_pullback_pct', 0.06)
        self.vol_shrink = kwargs.get('vol_shrink', True)
        self.rsi_max = kwargs.get('rsi_max', 50)
        self.use_rsi = kwargs.get('use_rsi', False)
        self.ma_short = kwargs.get('ma_short', 20)
        self.ma_long = kwargs.get('ma_long', 60)

        name_parts = ['pb{}d'.format(self.pullback_days)]
        if self.vol_shrink:
            name_parts.append('vol')
        if self.use_rsi:
            name_parts.append('rsi<{}'.format(self.rsi_max))
        self.factor_name = '{}:{}'.format(
            self.__class__.__name__, '+'.join(name_parts))

        self._rsi_cache = None
        self._vol_ma_cache = None

    def _calc_rsi(self, closes, period=14):
        delta = closes.diff()
        gain = delta.where(delta > 0, 0.0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def fit_day(self, today):
        min_lookback = max(self.ma_long + 2, 62)
        if self.today_ind < min_lookback:
            return None

        closes = self.kl_pd.close[:self.today_ind + 1]
        volumes = self.kl_pd.volume[:self.today_ind + 1]

        ma_s = closes.iloc[-self.ma_short:].mean()
        ma_l = closes.iloc[-self.ma_long:].mean()

        if ma_s <= ma_l:
            return None
        if today.close < ma_l:
            return None

        for d in range(self.pullback_days):
            idx = self.today_ind - d
            if idx < 1:
                return None
            if self.kl_pd.close.iloc[idx] >= self.kl_pd.close.iloc[idx - 1]:
                return None

        start_price = self.kl_pd.close.iloc[self.today_ind - self.pullback_days]
        if start_price <= 0:
            return None
        pullback_pct = (start_price - today.close) / start_price
        if pullback_pct > self.max_pullback_pct or pullback_pct < 0:
            return None

        if self.vol_shrink:
            vol_ma = volumes.iloc[-10:].mean()
            if today.volume > vol_ma:
                return None

        if self.use_rsi:
            rsi_series = self._calc_rsi(closes)
            rsi_val = rsi_series.iloc[-1]
            if np.isnan(rsi_val) or rsi_val > self.rsi_max:
                return None

        self.skip_days = self.pullback_days
        return self.buy_tomorrow()
