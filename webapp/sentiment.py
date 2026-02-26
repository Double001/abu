# -*- encoding:utf-8 -*-
"""
A股社媒情绪采集模块

数据源:
1. 同花顺热股榜 — 实时热度排名、排名变化、概念标签、连板标注
2. 淘股吧热帖 — 短线交易者社区情绪
3. 东方财富实时行情 — 量比、换手率、振幅(价量衍生情绪)
"""

import requests
import json
import re
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/120.0.0.0 Safari/537.36'
}


def _safe_get(url, headers=None, timeout=10, retries=2, **kwargs):
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers or HEADERS,
                                timeout=timeout, **kwargs)
            if resp.status_code == 200:
                return resp
        except Exception:
            if attempt < retries - 1:
                time.sleep(1)
    return None


class SentimentCollector:
    """A股社媒情绪数据采集器"""

    def __init__(self):
        self._ths_cache = None
        self._ths_cache_time = 0
        self._taoguba_cache = None
        self._taoguba_cache_time = 0

    def get_ths_hot_stocks(self, force_refresh=False):
        """
        获取同花顺热股榜 (实时社媒热度)
        返回: {code: {rank, name, rank_chg, tags, popularity}} 
        """
        now = time.time()
        if not force_refresh and self._ths_cache and now - self._ths_cache_time < 300:
            return self._ths_cache

        url = ("https://dq.10jqka.com.cn/fuyao/hot_list_data/out/"
               "hot_list/v1/stock?stock_type=a&type=hour&list_type=normal")
        resp = _safe_get(url, headers={
            **HEADERS, 'Referer': 'https://www.10jqka.com.cn/'
        })

        result = {}
        if resp:
            try:
                data = resp.json()
                for s in data.get('data', {}).get('stock_list', []):
                    code = s.get('code', '')
                    tags_raw = s.get('tag', '')
                    concept_tags = []
                    popularity_tag = ''
                    if isinstance(tags_raw, list) and tags_raw:
                        for t in tags_raw:
                            if isinstance(t, dict):
                                concept_tags.extend(t.get('concept_tag', []))
                                pt = t.get('popularity_tag', '')
                                if pt:
                                    popularity_tag = pt
                    elif isinstance(tags_raw, str):
                        popularity_tag = tags_raw

                    result[code] = {
                        'rank': s.get('order', 999),
                        'name': s.get('name', ''),
                        'rank_chg': s.get('hot_rank_chg', 0),
                        'concept_tags': concept_tags,
                        'popularity': popularity_tag,
                    }
            except Exception as e:
                logger.warning(f"同花顺热股解析失败: {e}")

        self._ths_cache = result
        self._ths_cache_time = now
        return result

    def get_taoguba_hot_topics(self):
        """
        获取淘股吧热帖 (短线交易社区情绪)
        返回: [code] 被讨论的股票代码列表
        """
        now = time.time()
        if self._taoguba_cache and now - self._taoguba_cache_time < 600:
            return self._taoguba_cache

        resp = _safe_get("https://www.taoguba.com.cn/hot")
        codes = []
        if resp:
            try:
                text = resp.text
                found = re.findall(r'[036]\d{5}', text)
                codes = list(dict.fromkeys(found))[:50]
            except Exception as e:
                logger.warning(f"淘股吧解析失败: {e}")

        self._taoguba_cache = codes
        self._taoguba_cache_time = now
        return codes

    def calc_social_sentiment_score(self, code):
        """
        计算个股社媒情绪综合得分 (0-100)

        得分维度:
        1. 同花顺热度排名 (0-40分): 排名越前 = 社媒讨论越多
        2. 排名变化 (0-20分): 排名快速上升 = 情绪升温
        3. 概念标签热度 (0-20分): 热门概念加分
        4. 淘股吧讨论度 (0-20分): 是否被短线社区讨论
        """
        ths = self.get_ths_hot_stocks()
        tgb = self.get_taoguba_hot_topics()

        score = 0
        details = {}

        # 1. 同花顺热度排名
        if code in ths:
            info = ths[code]
            rank = info['rank']
            if rank <= 10:
                rank_score = 40
            elif rank <= 30:
                rank_score = 30
            elif rank <= 50:
                rank_score = 20
            elif rank <= 100:
                rank_score = 10
            else:
                rank_score = 0
            score += rank_score
            details['ths_rank'] = rank
            details['ths_rank_score'] = rank_score

            # 2. 排名变化
            chg = info.get('rank_chg', 0)
            if isinstance(chg, (int, float)):
                if chg < -20:
                    chg_score = 20
                elif chg < -5:
                    chg_score = 15
                elif chg < 0:
                    chg_score = 10
                else:
                    chg_score = 5
            else:
                chg_score = 5
            score += chg_score
            details['rank_chg_score'] = chg_score

            # 3. 概念标签
            hot_concepts = ['AI', '人工智能', '机器人', '算力', '芯片',
                            '华为', '新能源', '光伏', '锂电', '军工']
            tags = info.get('concept_tags', [])
            tag_hits = sum(1 for t in tags for hc in hot_concepts if hc in t)
            tag_score = min(tag_hits * 7, 20)
            score += tag_score
            details['concept_score'] = tag_score

            # 连板标注额外加分
            pop = info.get('popularity', '')
            if '连板' in str(pop) or '涨停' in str(pop):
                score += 5
                details['board_bonus'] = 5
        else:
            details['ths_rank'] = None

        # 4. 淘股吧讨论
        if code in tgb:
            tgb_rank = tgb.index(code)
            tgb_score = max(20 - tgb_rank, 5)
            score += tgb_score
            details['tgb_score'] = tgb_score
        else:
            details['tgb_score'] = 0

        return min(score, 100), details


# 全局实例
_collector = None


def get_collector():
    global _collector
    if _collector is None:
        _collector = SentimentCollector()
    return _collector


def scan_with_sentiment(hot_stocks_data):
    """
    对涨幅榜股票进行社媒情绪评分

    参数: hot_stocks_data — 东方财富涨幅榜数据列表
    返回: 带情绪评分的候选股票列表
    """
    collector = get_collector()
    results = []

    for s in hot_stocks_data:
        code = s.get('f12', '')
        name = s.get('f14', '')
        pchg = s.get('f3', 0)
        if pchg < 5.0:
            continue

        social_score, details = collector.calc_social_sentiment_score(code)

        results.append({
            'code': code,
            'name': name,
            'pchg': pchg,
            'social_score': social_score,
            'social_details': details,
            'vol_ratio': s.get('f10', 0),
            'turnover': s.get('f8', 0),
            'amplitude': s.get('f7', 0),
        })

    results.sort(key=lambda x: -x['social_score'])
    return results
