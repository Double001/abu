# -*- encoding:utf-8 -*-
"""
ABU量化交易系统 - Web后端服务
提供回测、策略管理、行情数据、系统配置等REST API接口
"""

import os
import sys
import json
import logging
import traceback
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS

import warnings
warnings.filterwarnings('ignore')

import abupy
from abupy import env, abu
from abupy import ABuSymbolPd
from abupy.CoreBu.ABuEnv import EMarketTargetType, EMarketDataFetchMode

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)
app.config['JSON_AS_ASCII'] = False

CHARTS_DIR = os.path.join(os.path.dirname(__file__), 'static', 'charts')
os.makedirs(CHARTS_DIR, exist_ok=True)

env.enable_example_env_ipython(show_log=False)

BUY_FACTORS_REGISTRY = {}
SELL_FACTORS_REGISTRY = {}


def _register_factors():
    from abupy import (AbuFactorBuyBreak, AbuFactorBuyPutBreak,
                       AbuFactorSellBreak, AbuFactorAtrNStop,
                       AbuFactorPreAtrNStop, AbuFactorCloseAtrNStop)
    from abupy.FactorBuyBu.ABuFactorBuyDM import AbuDoubleMaBuy
    from abupy.FactorBuyBu.ABuFactorBuyTrend import AbuDownUpTrend
    from abupy.FactorSellBu.ABuFactorSellDM import AbuDoubleMaSell
    from abupy.FactorSellBu.ABuFactorSellNDay import AbuFactorSellNDay
    from abupy.FactorBuyBu.ABuFactorBuyCN import (
        AbuFactorBuyVolPriceBreakCN, AbuFactorBuyMAAlignCN,
        AbuFactorBuyMACDCN)
    from abupy.FactorSellBu.ABuFactorSellCN import (
        AbuFactorSellT1StopCN, AbuFactorSellPriceLimitCN,
        AbuFactorSellMACrossCN)
    from abupy.FactorBuyBu.ABuFactorBuyHighWR import AbuFactorBuyPullbackTrend
    from abupy.FactorSellBu.ABuFactorSellHighWR import AbuFactorSellQuickProfit

    global BUY_FACTORS_REGISTRY, SELL_FACTORS_REGISTRY
    BUY_FACTORS_REGISTRY = {
        'break': {
            'class': AbuFactorBuyBreak, 'name': 'N日突破买入',
            'params': [{'key': 'xd', 'label': '突破天数', 'type': 'int', 'default': 20}]
        },
        'put_break': {
            'class': AbuFactorBuyPutBreak, 'name': 'N日反向突破买入',
            'params': [{'key': 'xd', 'label': '突破天数', 'type': 'int', 'default': 20}]
        },
        'double_ma': {
            'class': AbuDoubleMaBuy, 'name': '双均线买入',
            'params': [
                {'key': 'ma_period_s', 'label': '短期均线', 'type': 'int', 'default': 5},
                {'key': 'ma_period_l', 'label': '长期均线', 'type': 'int', 'default': 60}
            ]
        },
        'down_up_trend': {
            'class': AbuDownUpTrend, 'name': '下降趋势后反转买入',
            'params': [
                {'key': 'xd', 'label': '下降天数', 'type': 'int', 'default': 20},
                {'key': 'past_factor', 'label': '反转因子', 'type': 'float', 'default': 0.5},
                {'key': 'down_deg_threshold', 'label': '下降角度阈值', 'type': 'float', 'default': -3}
            ]
        },
        'vol_price_break_cn': {
            'class': AbuFactorBuyVolPriceBreakCN, 'name': 'A股量价齐升突破',
            'params': [
                {'key': 'xd', 'label': '突破天数', 'type': 'int', 'default': 20},
                {'key': 'vol_ratio', 'label': '量比阈值', 'type': 'float', 'default': 1.5}
            ]
        },
        'ma_align_cn': {
            'class': AbuFactorBuyMAAlignCN, 'name': 'A股均线多头排列',
            'params': [
                {'key': 'ma_short', 'label': '短期均线', 'type': 'int', 'default': 5},
                {'key': 'ma_mid', 'label': '中期均线', 'type': 'int', 'default': 20},
                {'key': 'ma_long', 'label': '长期均线', 'type': 'int', 'default': 60}
            ]
        },
        'macd_cn': {
            'class': AbuFactorBuyMACDCN, 'name': 'A股MACD金叉',
            'params': [
                {'key': 'fast_period', 'label': '快线周期', 'type': 'int', 'default': 12},
                {'key': 'slow_period', 'label': '慢线周期', 'type': 'int', 'default': 26},
                {'key': 'signal_period', 'label': '信号线周期', 'type': 'int', 'default': 9}
            ]
        },
        'pullback_trend': {
            'class': AbuFactorBuyPullbackTrend, 'name': '★高胜率趋势回调买入',
            'params': [
                {'key': 'pullback_days', 'label': '回调天数', 'type': 'int', 'default': 3},
                {'key': 'vol_shrink', 'label': '缩量过滤', 'type': 'bool', 'default': True},
                {'key': 'use_rsi', 'label': 'RSI过滤', 'type': 'bool', 'default': False},
                {'key': 'max_pullback_pct', 'label': '最大回调幅度', 'type': 'float', 'default': 0.06}
            ]
        }
    }

    SELL_FACTORS_REGISTRY = {
        'break': {
            'class': AbuFactorSellBreak, 'name': 'N日突破卖出',
            'params': [{'key': 'xd', 'label': '突破天数', 'type': 'int', 'default': 120}]
        },
        'atr_stop': {
            'class': AbuFactorAtrNStop, 'name': 'ATR止盈止损',
            'params': [
                {'key': 'stop_loss_n', 'label': '止损ATR倍数', 'type': 'float', 'default': 1.0},
                {'key': 'stop_win_n', 'label': '止盈ATR倍数', 'type': 'float', 'default': 3.0}
            ]
        },
        'pre_atr_stop': {
            'class': AbuFactorPreAtrNStop, 'name': '盈利回撤止损',
            'params': [{'key': 'pre_atr_n', 'label': 'ATR倍数', 'type': 'float', 'default': 1.5}]
        },
        'close_atr_stop': {
            'class': AbuFactorCloseAtrNStop, 'name': '收盘价ATR止损',
            'params': [{'key': 'close_atr_n', 'label': 'ATR倍数', 'type': 'float', 'default': 1.5}]
        },
        'double_ma': {
            'class': AbuDoubleMaSell, 'name': '双均线卖出',
            'params': [
                {'key': 'ma_period_s', 'label': '短期均线', 'type': 'int', 'default': 5},
                {'key': 'ma_period_l', 'label': '长期均线', 'type': 'int', 'default': 60}
            ]
        },
        'n_day': {
            'class': AbuFactorSellNDay, 'name': 'N日持有卖出',
            'params': [
                {'key': 'sell_n', 'label': '持有天数', 'type': 'int', 'default': 20},
                {'key': 'is_sell_today', 'label': '当天卖出', 'type': 'bool', 'default': False}
            ]
        },
        't1_stop_cn': {
            'class': AbuFactorSellT1StopCN, 'name': 'A股T+1止损',
            'params': [
                {'key': 'stop_loss_n', 'label': '止损ATR倍数', 'type': 'float', 'default': 1.5},
                {'key': 'stop_win_n', 'label': '止盈ATR倍数', 'type': 'float', 'default': 3.0}
            ]
        },
        'price_limit_cn': {
            'class': AbuFactorSellPriceLimitCN, 'name': 'A股涨跌停自适应',
            'params': [
                {'key': 'stop_loss_pct', 'label': '止损百分比', 'type': 'float', 'default': -0.15},
                {'key': 'limit_down_pct', 'label': '跌停阈值', 'type': 'float', 'default': -0.095}
            ]
        },
        'ma_cross_cn': {
            'class': AbuFactorSellMACrossCN, 'name': 'A股均线死叉',
            'params': [
                {'key': 'ma_short', 'label': '短期均线', 'type': 'int', 'default': 5},
                {'key': 'ma_long', 'label': '长期均线', 'type': 'int', 'default': 20}
            ]
        },
        'quick_profit': {
            'class': AbuFactorSellQuickProfit, 'name': '★高胜率快速止盈',
            'params': [
                {'key': 'profit_target_pct', 'label': '止盈目标%', 'type': 'float', 'default': 0.008},
                {'key': 'max_hold_days', 'label': '最大持有天数', 'type': 'int', 'default': 20},
                {'key': 'stop_loss_pct', 'label': '止损线%', 'type': 'float', 'default': -0.15}
            ]
        }
    }


_register_factors()


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/factors', methods=['GET'])
def get_factors():
    buy_list = []
    for key, info in BUY_FACTORS_REGISTRY.items():
        buy_list.append({
            'id': key, 'name': info['name'],
            'params': info['params']
        })
    sell_list = []
    for key, info in SELL_FACTORS_REGISTRY.items():
        sell_list.append({
            'id': key, 'name': info['name'],
            'params': info['params']
        })
    return jsonify({'buy_factors': buy_list, 'sell_factors': sell_list})


@app.route('/api/symbols', methods=['GET'])
def get_symbols():
    market = request.args.get('market', 'us')
    symbols = []
    try:
        from abupy.MarketBu.ABuSymbolStock import AbuSymbolCN, AbuSymbolUS
        if market == 'cn':
            sym_obj = AbuSymbolCN()
            all_syms = sym_obj.all_symbol()
            symbols = all_syms[:200] if len(all_syms) > 200 else all_syms
        else:
            symbols = ['usTSLA', 'usAAPL', 'usGOOG', 'usBIDU', 'usNOAH',
                        'usSFUN', 'usWUBA', 'usVIPS', 'usAMZN', 'usFB',
                        'usNFLX', 'usMSFT', 'usNVDA', 'usAMD', 'usINTC']
    except Exception:
        symbols = ['usTSLA', 'usAAPL', 'usGOOG', 'usBIDU', 'usNOAH',
                    'usSFUN', 'usWUBA', 'usVIPS']
    return jsonify({'symbols': symbols, 'market': market})


@app.route('/api/kline', methods=['GET'])
def get_kline():
    symbol = request.args.get('symbol', 'usTSLA')
    try:
        from abupy.CoreBu.ABuEnv import EMarketDataSplitMode
        kl_df = ABuSymbolPd.make_kl_df(
            symbol, data_mode=EMarketDataSplitMode.E_DATA_SPLIT_UNDO)
        if kl_df is None:
            return jsonify({'error': '无法获取数据', 'symbol': symbol}), 404

        data = []
        for idx, row in kl_df.iterrows():
            data.append({
                'date': str(idx.strftime('%Y-%m-%d')),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': int(row['volume'])
            })
        return jsonify({'symbol': symbol, 'data': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/backtest', methods=['POST'])
def run_backtest():
    try:
        config = request.get_json()
        read_cash = config.get('read_cash', 1000000)
        symbols = config.get('symbols', ['usTSLA'])
        n_folds = config.get('n_folds', 2)
        buy_factor_configs = config.get('buy_factors', [])
        sell_factor_configs = config.get('sell_factors', [])

        if not buy_factor_configs:
            return jsonify({'error': '请至少选择一个买入策略'}), 400

        buy_factors = []
        for fc in buy_factor_configs:
            fid = fc.get('id')
            if fid not in BUY_FACTORS_REGISTRY:
                continue
            factor_info = BUY_FACTORS_REGISTRY[fid]
            params = {'class': factor_info['class']}
            for p in factor_info['params']:
                val = fc.get('params', {}).get(p['key'], p['default'])
                if p['type'] == 'int':
                    val = int(val)
                elif p['type'] == 'float':
                    val = float(val)
                elif p['type'] == 'bool':
                    val = bool(val)
                params[p['key']] = val
            buy_factors.append(params)

        sell_factors = []
        for fc in sell_factor_configs:
            fid = fc.get('id')
            if fid not in SELL_FACTORS_REGISTRY:
                continue
            factor_info = SELL_FACTORS_REGISTRY[fid]
            params = {'class': factor_info['class']}
            for p in factor_info['params']:
                val = fc.get('params', {}).get(p['key'], p['default'])
                if p['type'] == 'int':
                    val = int(val)
                elif p['type'] == 'float':
                    val = float(val)
                elif p['type'] == 'bool':
                    val = bool(val)
                params[p['key']] = val
            sell_factors.append(params)

        if not sell_factors:
            from abupy import AbuFactorAtrNStop, AbuFactorPreAtrNStop
            sell_factors = [
                {'stop_loss_n': 1.0, 'class': AbuFactorAtrNStop},
                {'class': AbuFactorPreAtrNStop, 'pre_atr_n': 1.5}
            ]

        result, kl_mgr = abu.run_loop_back(
            read_cash=read_cash,
            buy_factors=buy_factors,
            sell_factors=sell_factors,
            choice_symbols=symbols,
            n_folds=n_folds,
            n_process_kl=1,
            n_process_pick=1
        )

        if result is None or result.orders_pd is None or len(result.orders_pd) == 0:
            return jsonify({
                'success': True,
                'summary': {
                    'total_trades': 0,
                    'total_profit': 0,
                    'win_rate': 0,
                    'win_trades': 0,
                    'loss_trades': 0,
                    'initial_cash': read_cash
                },
                'orders': [],
                'chart_url': None
            })

        orders = result.orders_pd
        total_trades = len(orders)
        total_profit = float(orders['profit'].sum())
        win_trades = int(len(orders[orders['profit'] > 0]))
        loss_trades = int(len(orders[orders['profit'] <= 0]))
        win_rate = round(win_trades / total_trades * 100, 1) if total_trades > 0 else 0

        def clean_value(val):
            if isinstance(val, (float, np.floating)):
                if np.isnan(val) or np.isinf(val):
                    return 0.0
                return float(val)
            return val
        
        orders_list = []
        for _, row in orders.iterrows():
            orders_list.append({
                'symbol': str(row['symbol']),
                'buy_date': int(row['buy_date']),
                'sell_date': int(row['sell_date']) if row['sell_date'] else None,
                'buy_price': clean_value(round(float(row['buy_price']), 2)),
                'sell_price': clean_value(round(float(row['sell_price']), 2)) if row['sell_price'] else None,
                'buy_cnt': clean_value(float(row['buy_cnt'])),
                'profit': clean_value(round(float(row['profit']), 2)),
                'buy_factor': str(row['buy_factor']),
                'sell_type': str(row.get('sell_type', ''))
            })

        chart_filename = 'backtest_{}.png'.format(
            datetime.now().strftime('%Y%m%d_%H%M%S'))
        chart_path = os.path.join(CHARTS_DIR, chart_filename)
        _generate_chart(result, kl_mgr, symbols, chart_path)

        def clean_value(val):
            if isinstance(val, (float, np.floating)):
                if np.isnan(val) or np.isinf(val):
                    return 0.0
                return float(val)
            return val
        
        per_stock = {}
        for sym in orders['symbol'].unique():
            sym_orders = orders[orders['symbol'] == sym]
            sym_profit = float(sym_orders['profit'].sum())
            sym_win = int(len(sym_orders[sym_orders['profit'] > 0]))
            per_stock[str(sym)] = {
                'trades': int(len(sym_orders)),
                'profit': clean_value(round(sym_profit, 2)),
                'win_trades': sym_win,
                'win_rate': clean_value(round(sym_win / len(sym_orders) * 100, 1) if len(sym_orders) > 0 else 0)
            }

        # Handle NaN values before JSON serialization
        def clean_value(val):
            if isinstance(val, (float, np.floating)):
                if np.isnan(val) or np.isinf(val):
                    return 0.0
                return float(val)
            return val
        
        return jsonify({
            'success': True,
            'summary': {
                'total_trades': total_trades,
                'total_profit': clean_value(round(total_profit, 2)),
                'win_rate': clean_value(win_rate),
                'win_trades': win_trades,
                'loss_trades': loss_trades,
                'initial_cash': read_cash,
                'final_cash': clean_value(round(read_cash + total_profit, 2)),
                'return_pct': clean_value(round(total_profit / read_cash * 100, 2))
            },
            'per_stock': per_stock,
            'orders': orders_list,
            'chart_url': '/static/charts/' + chart_filename
        })

    except Exception as e:
        logging.exception('Backtest error')
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


def _generate_chart(result, kl_mgr, symbols, chart_path):
    try:
        fig, axes = plt.subplots(2, 1, figsize=(16, 10),
                                  gridspec_kw={'height_ratios': [3, 1]})

        orders = result.orders_pd
        sym = symbols[0] if len(symbols) == 1 else symbols[0]

        try:
            kl_pd = kl_mgr.get_pick_time_kl_pd(sym)
        except Exception:
            kl_pd = None

        if kl_pd is not None:
            ax1 = axes[0]
            ax1.plot(kl_pd.index, kl_pd['close'], color='#2196F3',
                     linewidth=1.2, label=sym)

            sym_orders = orders[orders['symbol'] == sym]
            for _, order in sym_orders.iterrows():
                buy_date_str = str(int(order['buy_date']))
                try:
                    from abupy.UtilBu import ABuDateUtil
                    bd = ABuDateUtil.fmt_date(int(order['buy_date']))
                    bd_ts = pd.Timestamp(bd)
                    if bd_ts in kl_pd.index:
                        color = '#4CAF50' if order['profit'] > 0 else '#F44336'
                        ax1.scatter(bd_ts, order['buy_price'],
                                    marker='^', color='#4CAF50', s=120,
                                    zorder=5, edgecolors='black', linewidth=0.5)
                except Exception:
                    pass

            ax1.set_title(u'回测结果 - {}'.format(sym), fontsize=14)
            ax1.set_ylabel(u'价格', fontsize=12)
            ax1.legend(fontsize=11)
            ax1.grid(True, alpha=0.3)

        ax2 = axes[1]
        profits = orders['profit'].values
        colors = ['#4CAF50' if p > 0 else '#F44336' for p in profits]
        ax2.bar(range(len(profits)), profits, color=colors, alpha=0.8)
        ax2.set_title(u'每笔交易盈亏', fontsize=12)
        ax2.set_xlabel(u'交易序号', fontsize=11)
        ax2.set_ylabel(u'盈亏金额', fontsize=11)
        ax2.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(chart_path, dpi=100, bbox_inches='tight')
        plt.close(fig)
    except Exception as e:
        logging.exception('Chart generation error')


@app.route('/api/market/info', methods=['GET'])
def market_info():
    return jsonify({
        'version': abupy.__version__,
        'data_mode': str(env.g_data_fetch_mode),
        'market_target': str(env.g_market_target),
        'available_markets': [
            {'id': 'us', 'name': '美股'},
            {'id': 'cn', 'name': 'A股'},
            {'id': 'hk', 'name': '港股'}
        ]
    })


if __name__ == '__main__':
    print('='*50)
    print('  ABU量化交易系统 Web服务')
    print('  版本: {}'.format(abupy.__version__))
    print('  访问: http://localhost:5000')
    print('='*50)
    app.run(host='0.0.0.0', port=5000, debug=False)
