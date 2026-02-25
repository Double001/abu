# -*- encoding:utf-8 -*-
"""
    A股市场专用买入择时因子模块：
    1. 量价齐升买入策略 (Volume-Price Breakout)
    2. 均线多头排列买入策略 (MA Bull Alignment)
    3. MACD金叉买入策略 (MACD Golden Cross)
"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

import numpy as np

from .ABuFactorBuyBase import AbuFactorBuyBase, AbuFactorBuyXD, BuyCallMixin

__author__ = 'abu_cn'


class AbuFactorBuyVolPriceBreakCN(AbuFactorBuyBase, BuyCallMixin):
    """
    A股量价齐升突破买入策略：
    当价格突破xd日新高 且 成交量大于xd日均量的vol_ratio倍时买入。
    该策略适合A股市场的放量突破行情。
    """

    def _init_self(self, **kwargs):
        self.xd = kwargs.get('xd', 20)
        self.vol_ratio = kwargs.get('vol_ratio', 1.5)
        self.factor_name = '{}:xd={},vol={}'.format(
            self.__class__.__name__, self.xd, self.vol_ratio)

    def fit_day(self, today):
        if self.today_ind < self.xd - 1:
            return None

        window = self.kl_pd.iloc[self.today_ind - self.xd + 1:self.today_ind + 1]
        price_high = today.close == window.close.max()
        vol_mean = window.volume.mean()
        vol_surge = today.volume > vol_mean * self.vol_ratio

        if price_high and vol_surge:
            self.skip_days = self.xd
            return self.buy_tomorrow()
        return None


class AbuFactorBuyMAAlignCN(AbuFactorBuyBase, BuyCallMixin):
    """
    A股均线多头排列买入策略：
    当短期均线 > 中期均线 > 长期均线形成多头排列，
    且价格站上短期均线时产生买入信号。
    """

    def _init_self(self, **kwargs):
        self.ma_short = kwargs.get('ma_short', 5)
        self.ma_mid = kwargs.get('ma_mid', 20)
        self.ma_long = kwargs.get('ma_long', 60)
        self.factor_name = '{}:ma={}/{}/{}'.format(
            self.__class__.__name__, self.ma_short, self.ma_mid, self.ma_long)

    def fit_day(self, today):
        if self.today_ind < self.ma_long:
            return None

        closes = self.kl_pd.close[:self.today_ind + 1]
        ma_s = closes.iloc[-self.ma_short:].mean()
        ma_m = closes.iloc[-self.ma_mid:].mean()
        ma_l = closes.iloc[-self.ma_long:].mean()

        if ma_s > ma_m > ma_l and today.close > ma_s:
            self.skip_days = self.ma_short
            return self.buy_tomorrow()
        return None


class AbuFactorBuyMACDCN(AbuFactorBuyBase, BuyCallMixin):
    """
    A股MACD金叉买入策略：
    DIF上穿DEA（金叉）时买入。支持自定义快线/慢线/信号线周期。
    """

    def _init_self(self, **kwargs):
        self.fast_period = kwargs.get('fast_period', 12)
        self.slow_period = kwargs.get('slow_period', 26)
        self.signal_period = kwargs.get('signal_period', 9)
        self.factor_name = '{}:{}/{}/{}'.format(
            self.__class__.__name__, self.fast_period,
            self.slow_period, self.signal_period)

    @staticmethod
    def _ema(series, period):
        return series.ewm(span=period, adjust=False).mean()

    def fit_day(self, today):
        if self.today_ind < self.slow_period + self.signal_period:
            return None

        closes = self.kl_pd.close[:self.today_ind + 1]
        ema_fast = self._ema(closes, self.fast_period)
        ema_slow = self._ema(closes, self.slow_period)
        dif = ema_fast - ema_slow
        dea = self._ema(dif, self.signal_period)

        dif_today = dif.iloc[-1]
        dea_today = dea.iloc[-1]
        dif_yesterday = dif.iloc[-2]
        dea_yesterday = dea.iloc[-2]

        if dif_yesterday <= dea_yesterday and dif_today > dea_today:
            self.skip_days = self.signal_period
            return self.buy_tomorrow()
        return None
