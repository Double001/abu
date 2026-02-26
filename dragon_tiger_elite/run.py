#!/usr/bin/env python3
# -*- encoding:utf-8 -*-
"""
龙虎榜精选模式 — 一键运行

用法:
  python run.py              # 实时扫描今日信号
  python run.py --backtest   # 回测历史数据
  python run.py --help       # 帮助
"""

import sys
import os
import time
import argparse
from datetime import datetime

# 确保当前目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import fetch_kline, fetch_benchmark, fetch_hot_list, fetch_ths_hot
from strategy import scan_signals, backtest, calc_emotion_score


def run_scan():
    """实时扫描今日信号"""
    print("=" * 70)
    print("  龙虎榜精选模式 — 实时信号扫描")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 1. 获取涨幅榜
    print("\n[1/4] 获取涨幅榜...")
    hot = fetch_hot_list()
    hot5 = [s for s in hot if s['pchg'] >= 5.0]
    hot7 = [s for s in hot if s['pchg'] >= 7.0]
    print(f"  涨>=5%: {len(hot5)}只  涨>=7%: {len(hot7)}只")

    # 2. 获取上证指数
    print("[2/4] 获取上证指数...")
    bench = fetch_benchmark(days=30)
    if bench is None:
        print("  ❌ 上证数据获取失败"); return
    bc = bench['Close'].values
    bench_5d = (bc[-1] - bc[-6]) / bc[-6] * 100 if len(bc) >= 6 else 0
    print(f"  上证5日涨幅: {bench_5d:+.2f}%  {'✅达标(>1%)' if bench_5d>=1 else '⚠️未达标(需>1%)'}")

    # 3. 获取同花顺热股
    print("[3/4] 获取同花顺热股...")
    ths = fetch_ths_hot()
    print(f"  热股: {len(ths)}只")

    # 4. 逐股扫描
    print(f"[4/4] 扫描 {len(hot7)} 只候选...\n")
    all_stocks = {}
    for s in hot7[:50]:
        code = s['code']
        time.sleep(0.2)
        kl = fetch_kline(code, days=90)
        if kl is not None and len(kl) >= 25:
            all_stocks[code] = kl

    signals = scan_signals(all_stocks, bench)

    # 输出
    print(f"{'=' * 70}")
    print(f"  大盘: 上证5日 {bench_5d:+.2f}%  {'✅可操作' if bench_5d>=1 else '⚠️等待转强'}")
    print(f"  热度: {len(hot5)}只涨>=5%  {'✅' if len(hot5)>=5 else '⚠️'}")
    print(f"  信号: {len(signals)} 只通过V6全部条件")
    print(f"{'=' * 70}")

    if signals:
        print(f"\n  {'#':>3s} {'代码':>8s} {'涨幅':>7s} {'量比':>5s} {'情绪':>5s} {'同花顺':>8s}")
        print(f"  {'─' * 50}")
        for i, s in enumerate(signals[:10], 1):
            ths_info = ths.get(s['code'], {})
            ths_rank = f"第{ths_info['rank']}名" if ths_info else "—"
            print(f"  {i:>3d} {s['code']:>8s} {s['pchg']:+6.1f}% {s['vol_ratio']:4.1f}x {s['emotion']:4.0f} {ths_rank:>8s}")

        print(f"\n  操作建议:")
        print(f"  1. 选择情绪最高的1-2只, 明日开盘价买入")
        print(f"  2. 开盘跳空>5%则放弃")
        print(f"  3. 峰值>=20%后回撤8%卖出")
        print(f"  4. 浮亏>=-20%止损")
        print(f"  5. 持仓60天盈利则卖, 90天强平")
    else:
        if bench_5d < 1:
            print(f"\n  ⚠️ 大盘5日仅{bench_5d:+.2f}%, 不满足>1%条件")
            print(f"  等待上证放量突破后再操作")
        else:
            print(f"\n  今日无满足全部条件的信号")

    print(f"\n{'=' * 70}")


def run_backtest():
    """回测历史数据"""
    print("=" * 70)
    print("  龙虎榜精选模式 — 历史回测")
    print("=" * 70)

    # 检查本地数据
    data_dirs = ['../data_cn_active', './data']
    data_dir = None
    for d in data_dirs:
        if os.path.exists(d) and len(os.listdir(d)) > 5:
            data_dir = d
            break

    if data_dir is None:
        print("\n  未找到本地数据, 从网络下载...")
        data_dir = './data'
        os.makedirs(data_dir, exist_ok=True)
        download_sample_data(data_dir)

    # 加载
    import pandas as pd
    all_stocks = {}
    bench = None
    for f in os.listdir(data_dir):
        if not f.endswith('.csv'):
            continue
        code = f.replace('.csv', '')
        fp = os.path.join(data_dir, f)
        with open(fp) as fh:
            lines = fh.readlines()
        rows = []
        for line in lines[1:]:
            p = line.strip().split(',')
            if len(p) >= 9:
                rows.append({'Date': p[0], 'Open': float(p[1]), 'Close': float(p[2]),
                             'High': float(p[3]), 'Low': float(p[4]),
                             'Volume': int(float(p[5])), 'Amplitude': float(p[7]),
                             'PctChg': float(p[8]),
                             'Turnover': float(p[10]) if len(p) > 10 else 0})
        df = pd.DataFrame(rows).sort_values('Date').reset_index(drop=True)
        df.index = pd.to_datetime(df['Date'])
        df.name = code
        if code == '000001':
            bench = df
        else:
            all_stocks[code] = df

    if bench is None:
        print("  ❌ 未找到上证指数数据(000001.csv)")
        return

    print(f"\n  股票数: {len(all_stocks)}")
    print(f"  基准: 上证指数")

    # 回测
    trades = backtest(all_stocks, bench)
    total = len(trades)
    if total == 0:
        print("  无交易生成")
        return

    wins = sum(1 for t in trades if t['win'])
    wr = wins / total * 100
    pcts = [t['profit_pct'] for t in trades]
    wp = [p for p in pcts if p > 0]
    n20 = sum(1 for p in pcts if p >= 20)

    print(f"\n  {'=' * 55}")
    print(f"  回测结果")
    print(f"  {'=' * 55}")
    print(f"  交易笔数: {total}")
    print(f"  胜    率: {wr:.1f}%  ({wins}盈 / {total-wins}亏)")
    print(f"  盈利均值: {sum(wp)/len(wp):+.1f}%" if wp else "")
    print(f"  全部均盈: {sum(pcts)/len(pcts):+.1f}%")
    print(f"  20%+占比: {n20}/{total}")
    print(f"  {'=' * 55}")
    print(f"\n  明细:")
    for t in trades:
        w = '✓' if t['win'] else '✗'
        print(f"    {w} {t['code']:>8s} {t['buy_date']}→{t['sell_date']}"
              f" 盈{t['profit_pct']:+6.1f}% 峰{t['peak_pct']:+6.1f}%"
              f" 持{t['hold_days']:>2d}天 [{t['exit']}] 情绪{t['emotion']:.0f}")


def download_sample_data(data_dir):
    """下载示例数据"""
    import requests
    stocks = [
        ('1', '601162'), ('0', '000750'), ('1', '600776'),
        ('0', '002625'), ('1', '603019'), ('0', '000977'),
        ('1', '601360'), ('0', '300033'), ('0', '300803'),
        ('0', '300624'), ('0', '300418'), ('0', '300364'),
        ('1', '601788'), ('1', '601136'), ('0', '688256'),
        ('0', '002371'), ('0', '688981'), ('0', '002230'),
        ('1', '000001'),  # 上证指数
    ]

    for market, code in stocks:
        url = (f"https://push2his.eastmoney.com/api/qt/stock/kline/get?"
               f"secid={market}.{code}&fields1=f1,f2,f3,f4,f5,f6"
               f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
               f"&klt=101&fqt=1&beg=20240101&end=20261231")
        try:
            r = requests.get(url, timeout=15,
                             headers={'User-Agent': 'Mozilla/5.0'})
            klines = r.json().get('data', {}).get('klines', [])
            if klines:
                lines = ['Date,Open,Close,High,Low,Volume,Amount,Amplitude,PctChg,Change,Turnover']
                lines.extend(klines)
                with open(os.path.join(data_dir, f'{code}.csv'), 'w') as f:
                    f.write('\n'.join(lines))
                print(f"    下载 {code}: {len(klines)}天")
        except Exception:
            pass
        time.sleep(0.3)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='龙虎榜精选模式')
    parser.add_argument('--backtest', action='store_true', help='运行历史回测')
    args = parser.parse_args()

    if args.backtest:
        run_backtest()
    else:
        run_scan()
