"""天气抓取 — wttr.in"""

from __future__ import annotations

import logging
import time

import requests

from config import WEATHER_CITY

log = logging.getLogger("monitor.weather")

# 模块级缓存, 失败时回退
_last_ok: dict = {}


def fetch_weather() -> dict | None:
    """拉取天气; 成功返回 dict, 失败返回上次成功缓存或 None。不写全局 state。"""
    global _last_ok
    city = WEATHER_CITY
    url = f"https://wttr.in/{city}"
    try:
        resp = requests.get(
            url,
            params={"format": "j1", "lang": "zh"},
            timeout=15,
            headers={"User-Agent": "usage-monitor/1.0"},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}")
        data = resp.json()
        cur = (data.get("current_condition") or [{}])[0]
        area = ((data.get("nearest_area") or [{}])[0].get("areaName") or [{}])[0]
        weather = {
            "city": area.get("value") or city,
            "temp_c": cur.get("temp_C", "--"),
            "feels_c": cur.get("FeelsLikeC", "--"),
            "humidity": cur.get("humidity", "--"),
            "desc": _zh_desc(cur),
            "wind_kmph": cur.get("windspeedKmph", "--"),
            "updated_at": time.time(),
        }
        _last_ok = weather
        log.info(
            "Weather %s %s°C %s",
            weather["city"], weather["temp_c"], weather["desc"],
        )
        return weather
    except Exception as e:
        log.warning("Weather fetch failed: %s", e)
        return dict(_last_ok) if _last_ok else None


def fetch_weather_sync(state: dict) -> None:
    """兼容旧调用: 拉取并写入 state['weather']; 失败保留旧数据."""
    weather = fetch_weather()
    if weather:
        state["weather"] = weather
    elif _last_ok and not state.get("weather"):
        state["weather"] = dict(_last_ok)


def _zh_desc(cur: dict) -> str:
    langs = cur.get("lang_zh") or cur.get("lang_zh-cn") or []
    if langs and isinstance(langs, list):
        v = langs[0].get("value")
        if v:
            return v
    weather_desc = cur.get("weatherDesc") or []
    if weather_desc and isinstance(weather_desc, list):
        return weather_desc[0].get("value") or "--"
    return "--"
