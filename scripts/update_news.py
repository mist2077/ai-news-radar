#!/usr/bin/env python3
"""Aggregate updates from multiple AI news sites and produce 24h snapshot data."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import gzip # 新增 gzip
import os   # 新增 os
import random
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import feedparser
except ModuleNotFoundError:
    feedparser = None

UTC = timezone.utc
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
SH_TZ = ZoneInfo("Asia/Shanghai")
WAYTOAGI_DEFAULT = (
    "https://waytoagi.feishu.cn/wiki/QPe5w5g7UisbEkkow8XcDmOpn8e?fromScene=spaceOverview"
)
WAYTOAGI_HISTORY_FALLBACK = "https://waytoagi.feishu.cn/wiki/FjiOwWp2giA7hRk6jjfcPioCnAc"

RSS_FEED_REPLACEMENTS: dict[str, str] = {
    "https://rsshub.app/infoq/recommend": "https://www.infoq.cn/feed",
    "https://rsshub.app/huggingface/blog-zh": "https://huggingface.co/blog/feed.xml",
    "https://rsshub.app/readhub/daily": "https://readhub.cn/rss",
    "https://rsshub.app/36kr/hot-list": "https://36kr.com/feed",
    "https://rsshub.app/sspai/index": "https://sspai.com/feed",
    "https://rsshub.app/sspai/matrix": "https://sspai.com/feed",
    "https://rsshub.app/meituan/tech": "https://tech.meituan.com/feed",
    "https://mjg59.dreamwidth.org/data/rss": "http://mjg59.dreamwidth.org/data/rss",
}

RSS_FEED_SKIP_PREFIXES: tuple[str, ...] = (
    "https://rsshub.app/telegram/channel/",
    "https://rsshub.app/jike/",
    "https://rsshub.app/bilibili/",
