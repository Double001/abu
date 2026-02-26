# -*- encoding:utf-8 -*-
"""
数据采集模块 — 东方财富+同花顺

提供:
  1. 个股历史K线(东方财富, 前复权)
  2. 实时涨幅榜(东方财富)
  3. 上证指数
  4. 同花顺热股排名(社媒情绪)
"""

import requests
import time
import re
import pandas as pd
import numpy as np

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/120.0.0.0 Safari/537.36'
}


def _safe_get(url, headers=None, retries=2, timeout=15):
    for i in range(retries):
        try:
            r = requests.get(url, headers=headers or HEADERS, timeout=timeout)
            if r.status_code == 200:
                return r
        except Exception:
            if i < retries - 1:
                time.sleep(1)
    return None


def fetch_kline(code, market=None, days=120):
    """
    获取个股历史K线

    参数:
      code: 股票代码 如 '600519'
      market: 0=深圳 1=上海, None则自动判断
      days: 获取天数(近N天)
    """
    if market is None:
        market = 1 if code.startswith('6') else 0
    secid = f"{market}.{code}"

    from datetime import datetime, timedelta
    end = datetime.now().strftime('%Y%m%d')
    start = (datetime.now() - timedelta(days=days+30)).strftime('%Y%m%d')

    url = (f"https://push2his.eastmoney.com/api/qt/stock/kline/get?"
           f"secid={secid}&fields1=f1,f2,f3,f4,f5,f6"
           f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
           f"&klt=101&fqt=1&beg={start}&end={end}")

    resp = _safe_get(url)
    if not resp:
        return None

    data = resp.json()
    if not data.get('data') or not data['data'].get('klines'):
        return None

    rows = []
    for k in data['data']['klines']:
        p = k.split(',')
        if len(p) >= 9:
            rows.append({
                'Date': p[0], 'Open': float(p[1]), 'Close': float(p[2]),
                'High': float(p[3]), 'Low': float(p[4]),
                'Volume': int(float(p[5])),
                'Amplitude': float(p[7]), 'PctChg': float(p[8]),
                'Turnover': float(p[10]) if len(p) > 10 else 0
            })

    if not rows:
        return None

    df = pd.DataFrame(rows).sort_values('Date').reset_index(drop=True)
    df.index = pd.to_datetime(df['Date'])
    df.name = code
    return df


def fetch_benchmark(days=120):
    """获取上证指数"""
    return fetch_kline('000001', market=1, days=days)


def fetch_hot_list():
    """
    获取涨幅榜前100只

    返回: list of dict, 含 code, name, pchg, vol_ratio, turnover, amplitude
    """
    url = ("https://push2.eastmoney.com/api/qt/clist/get?"
           "pn=1&pz=100&po=1&np=1&fltt=2&invt=2"
           "&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
           "&fields=f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21")
    resp = _safe_get(url)
    if not resp:
        return []
    data = resp.json()
    if not data.get('data') or not data['data'].get('diff'):
        return []
    return [{
        'code': s.get('f12', ''),
        'name': s.get('f14', ''),
        'pchg': s.get('f3', 0),
        'vol_ratio': s.get('f10', 0),
        'turnover': s.get('f8', 0),
        'amplitude': s.get('f7', 0),
    } for s in data['data']['diff']]


def fetch_ths_hot():
    """
    获取同花顺热股排名

    返回: dict {code: {rank, name, concepts, popularity}}
    """
    url = ("https://dq.10jqka.com.cn/fuyao/hot_list_data/out/"
           "hot_list/v1/stock?stock_type=a&type=hour&list_type=normal")
    resp = _safe_get(url, headers={**HEADERS, 'Referer': 'https://www.10jqka.com.cn/'})
    if not resp:
        return {}
    result = {}
    try:
        data = resp.json()
        for s in data.get('data', {}).get('stock_list', []):
            code = s.get('code', '')
            tags = s.get('tag', '')
            concepts = []
            popularity = ''
            if isinstance(tags, list):
                for t in tags:
                    if isinstance(t, dict):
                        concepts.extend(t.get('concept_tag', []))
                        p = t.get('popularity_tag', '')
                        if p:
                            popularity = p
            result[code] = {
                'rank': s.get('order', 999),
                'name': s.get('name', ''),
                'concepts': concepts,
                'popularity': popularity,
            }
    except Exception:
        pass
    return result
