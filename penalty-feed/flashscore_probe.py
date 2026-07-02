#!/usr/bin/env python3
"""Разведчик внутреннего фида Flashscore.

Запускать на машине с открытым интернетом (НЕ в облачной среде Claude —
там спортивные домены закрыты сетевой политикой):

    python3 flashscore_probe.py

Что делает:
  1. Достаёт актуальный токен x-fsign из JS сайта (плюс пробует известный
     исторический токен SW9D1eZo).
  2. Пробует варианты live-фида футбола на d.flashscore.com.
  3. Из live-фида берёт первые матчи и пробует фиды деталей матча
     (события, статистика) по известным паттернам.
  4. Все успешные ответы сохраняет в flashscore_samples/ и печатает
     компактный отчёт — его содержимое нужно для написания парсера.

Скрипт ничего не ломает и не логинится — только GET-запросы, как браузер.
"""

import json
import os
import re
import sys
import time

import requests

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
KNOWN_FSIGN = "SW9D1eZo"  # многолетняя константа, может смениться
BASE_SITE = "https://www.flashscore.com"
BASE_FEED = "https://d.flashscore.com/x/feed"
OUT_DIR = "flashscore_samples"

session = requests.Session()
session.headers.update({"User-Agent": UA, "Referer": BASE_SITE + "/"})


def save(name, content, meta=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    mode = "wb" if isinstance(content, bytes) else "w"
    kwargs = {} if isinstance(content, bytes) else {"encoding": "utf-8"}
    with open(path, mode, **kwargs) as f:
        f.write(content)
    if meta:
        with open(path + ".meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    return path


def get(url, headers=None, label=""):
    try:
        resp = session.get(url, headers=headers or {}, timeout=15)
        size = len(resp.content)
        print(f"  [{resp.status_code}] {label or url} ({size} bytes)")
        return resp
    except requests.RequestException as e:
        print(f"  [ERR] {label or url}: {e}")
        return None


def find_fsign():
    """Ищем токен x-fsign в HTML и JS-бандлах сайта."""
    candidates = []
    resp = get(BASE_SITE + "/", label="главная страница")
    if resp is None or resp.status_code != 200:
        return candidates
    html = resp.text
    save("index.html", html)

    # прямое вхождение в HTML
    for m in re.findall(r'''["']?(?:x-)?fsign["']?\s*[:=]\s*["']([A-Za-z0-9_-]{6,16})["']''', html):
        candidates.append(m)

    # JS-бандлы: ищем core/common скрипты
    js_urls = re.findall(r'src=["\']([^"\']+\.js[^"\']*)["\']', html)
    js_urls = [u if u.startswith("http") else BASE_SITE + u for u in js_urls][:8]
    for u in js_urls:
        r = get(u, label=f"js: {u.rsplit('/', 1)[-1][:50]}")
        if r is None or r.status_code != 200:
            continue
        for m in re.findall(r'''["']?(?:x-)?fsign["']?\s*[:=]\s*["']([A-Za-z0-9_-]{6,16})["']''', r.text):
            candidates.append(m)
        time.sleep(0.3)

    seen = []
    for c in candidates:
        if c not in seen:
            seen.append(c)
    return seen


def parse_feed(text):
    """Разбор протокола Flashscore: записи ~, поля ¬, ключ÷значение."""
    rows = []
    for chunk in text.split("~"):
        row = {}
        for field in chunk.split("¬"):
            if "÷" in field:
                k, _, v = field.partition("÷")
                row[k] = v
        if row:
            rows.append(row)
    return rows


def try_live_feeds(fsign):
    """Пробуем варианты live-фида футбола."""
    headers = {"x-fsign": fsign}
    variants = [
        "f_1_0_1_en_1",   # футбол, сегодня
        "f_1_0_2_en_1",
        "f_1_0_1_ru_1",   # русская локаль
        "f_1_-1_1_en_1",  # вчера
    ]
    for v in variants:
        resp = get(f"{BASE_FEED}/{v}", headers=headers, label=f"live-фид {v} (fsign={fsign})")
        if resp is not None and resp.status_code == 200 and len(resp.content) > 100:
            save(f"live_{v}_{fsign}.txt", resp.text,
                 {"url": resp.url, "fsign": fsign, "status": resp.status_code})
            return v, resp.text
        time.sleep(0.4)
    return None, None


def try_match_feeds(fsign, match_id):
    """Пробуем фиды деталей матча по известным паттернам."""
    headers = {"x-fsign": fsign}
    patterns = [
        f"df_sui_1_{match_id}",   # summary / incidents (события)
        f"df_st_1_{match_id}",    # статистика (владение, удары, передачи)
        f"df_sur_1_{match_id}",   # результат/summary
        f"df_lu_1_{match_id}",    # составы
        f"dc_1_{match_id}",       # live-обновления матча
    ]
    ok = []
    for p in patterns:
        resp = get(f"{BASE_FEED}/{p}", headers=headers, label=f"матч-фид {p}")
        if resp is not None and resp.status_code == 200 and len(resp.content) > 20:
            save(f"match_{p}.txt", resp.text, {"url": resp.url, "fsign": fsign})
            ok.append(p)
            low = resp.text.lower()
            if "penal" in low:
                print(f"      >>> в фиде {p} найдено упоминание пенальти!")
        time.sleep(0.4)
    return ok


def main():
    print("=== Разведка фида Flashscore ===\n")

    print("[1/4] Ищу токен x-fsign на сайте...")
    found = find_fsign()
    tokens = found + ([KNOWN_FSIGN] if KNOWN_FSIGN not in found else [])
    print(f"  кандидаты: {tokens or 'не найдено, пробуем только известный'}\n")

    print("[2/4] Пробую live-фид футбола...")
    live_variant = live_text = live_fsign = None
    for t in tokens:
        live_variant, live_text = try_live_feeds(t)
        if live_text:
            live_fsign = t
            break
    if not live_text:
        print("\nЖивой фид не получен ни с одним токеном. Сохранённые файлы в",
              OUT_DIR, "— пришлите их содержимое для анализа.")
        sys.exit(1)

    print(f"\n[3/4] Разбираю live-фид {live_variant} (fsign={live_fsign})...")
    rows = parse_feed(live_text)
    matches = [r for r in rows if "AA" in r]  # AA = id матча
    print(f"  записей: {len(rows)}, матчей (с ключом AA): {len(matches)}")
    for r in matches[:5]:
        print("  пример:", {k: r.get(k) for k in
                            ("AA", "AE", "AF", "AG", "AH", "AB", "AC") if k in r})

    print("\n[4/4] Пробую фиды деталей для первых матчей...")
    tested = 0
    for r in matches:
        mid = r.get("AA")
        if not mid:
            continue
        print(f"  матч {mid} ({r.get('AE', '?')} — {r.get('AF', '?')}):")
        ok = try_match_feeds(live_fsign, mid)
        print(f"    рабочие паттерны: {ok or 'нет'}")
        tested += 1
        if tested >= 3:
            break

    print(f"\n=== Готово. Образцы в {OUT_DIR}/ ===")
    print("Пришлите в чат вывод этого скрипта и содержимое 1-2 файлов из",
          f"{OUT_DIR}/ (например, live_*.txt и match_df_sui_*.txt) —",
          "по ним будет написан полноценный парсер FlashscoreSource.")


if __name__ == "__main__":
    main()
