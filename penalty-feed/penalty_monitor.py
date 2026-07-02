#!/usr/bin/env python3
"""Live-монитор пенальти в футбольных матчах.

Опрашивает live-источники и сообщает о пенальти (назначен / забит / не забит /
VAR-проверка / серия пенальти) сразу, как только событие появляется в фиде.

Источники:
  espn         — неофициальный публичный API ESPN, бесплатно, без ключа,
                 без анти-бот защиты. Лиги настраиваются (--espn-leagues).
  sofascore    — неофициальный API Sofascore, бесплатно, без ключа.
                 С 2025-26 отсеивает клиентов по TLS-отпечатку — нужен
                 curl_cffi (pip install curl_cffi), тогда запросы выглядят
                 как настоящий Chrome.
  api-football — официальный API (api-sports.io), ключ в API_FOOTBALL_KEY.
                 На Free-плане текущие сезоны недоступны (только 2021-2023).

Алерты: stdout, JSONL-файл, опционально Telegram и произвольный webhook.

Примеры:
    python3 penalty_monitor.py                     # auto: espn → sofascore → api-football
    python3 penalty_monitor.py --source espn --espn-leagues fifa.world,eng.2
    API_FOOTBALL_KEY=xxx python3 penalty_monitor.py --source api-football

Переменные окружения:
    API_FOOTBALL_KEY      ключ api-sports.io (для --source api-football)
    TELEGRAM_BOT_TOKEN    токен бота для алертов в Telegram
    TELEGRAM_CHAT_ID      chat_id для алертов в Telegram
    PENALTY_WEBHOOK_URL   URL, куда POST-ится JSON каждого события
"""

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone

import requests

try:
    from curl_cffi import requests as cf_requests
    HAVE_CURL_CFFI = True
except ImportError:
    cf_requests = None
    HAVE_CURL_CFFI = False

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# Сетевые исключения обоих HTTP-клиентов
_net_errors = [requests.RequestException]
if HAVE_CURL_CFFI:
    for mod_name, cls_name in (("curl_cffi.requests.exceptions", "RequestException"),
                               ("curl_cffi.requests.errors", "RequestsError"),
                               ("curl_cffi", "CurlError")):
        try:
            _net_errors.append(getattr(__import__(mod_name, fromlist=[cls_name]), cls_name))
        except (ImportError, AttributeError):
            pass
NET_ERRORS = tuple(_net_errors)

RU_LABELS = {
    "penalty_goal": "⚽ ГОЛ С ПЕНАЛЬТИ",
    "penalty_missed": "❌ ПЕНАЛЬТИ НЕ ЗАБИТ",
    "penalty_var": "📺 VAR: проверка/решение по пенальти",
    "penalty_shootout": "🥅 СЕРИЯ ПЕНАЛЬТИ: удар",
    "penalty_awarded": "🟡 НАЗНАЧЕН ПЕНАЛЬТИ",
    "penalty_cancelled": "🚫 ПЕНАЛЬТИ ОТМЕНЁН",
}


def make_session():
    """Сессия с TLS-отпечатком Chrome, если установлен curl_cffi.

    Sofascore и Flashscore отсеивают не-браузерных клиентов по отпечатку
    TLS-соединения — обычному requests они отвечают 403.
    """
    if HAVE_CURL_CFFI:
        return cf_requests.Session(impersonate="chrome")
    return requests.Session()


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PenaltyEvent:
    def __init__(self, key, kind, competition, match, minute, team, player, source, raw=None):
        self.key = key                  # уникальный ключ для дедупликации
        self.kind = kind                # penalty_goal | penalty_missed | penalty_var | ...
        self.competition = competition
        self.match = match
        self.minute = minute
        self.team = team
        self.player = player
        self.source = source
        self.raw = raw or {}

    def to_dict(self):
        return {
            "detected_at": now_iso(),
            "source": self.source,
            "kind": self.kind,
            "label": RU_LABELS.get(self.kind, self.kind),
            "competition": self.competition,
            "match": self.match,
            "minute": self.minute,
            "team": self.team,
            "player": self.player,
            "key": self.key,
        }

    def format_ru(self):
        parts = [RU_LABELS.get(self.kind, self.kind)]
        minute = str(self.minute or "").rstrip("'")
        if minute:
            parts.append(f"{minute}'")
        parts.append(self.match)
        if self.team:
            parts.append(f"({self.team})")
        if self.player:
            parts.append(f"— {self.player}")
        if self.competition:
            parts.append(f"[{self.competition}]")
        return " ".join(parts)


class ESPNSource:
    """Неофициальный публичный API ESPN — без ключа и анти-бот защиты.

    В деталях матча есть явный флаг penaltyKick. Лиги: fifa.world,
    eng.1 (АПЛ), eng.2 (Championship), eng.3 (League One), eng.4 (League Two),
    uefa.champions и т.д.
    """

    name = "espn"
    BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
    DEFAULT_LEAGUES = ["fifa.world", "eng.1", "eng.2", "eng.3", "eng.4"]

    def __init__(self, session, leagues=None):
        self.session = session
        self.leagues = leagues or list(self.DEFAULT_LEAGUES)

    def check(self):
        resp = self.session.get(f"{self.BASE}/{self.leagues[0]}/scoreboard",
                                headers={"User-Agent": UA}, timeout=15)
        resp.raise_for_status()

    def poll(self):
        results = []
        for league in self.leagues:
            try:
                resp = self.session.get(f"{self.BASE}/{league}/scoreboard",
                                        headers={"User-Agent": UA}, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except NET_ERRORS + (ValueError,):
                continue
            league_name = (data.get("leagues") or [{}])[0].get("name", league)
            for ev in data.get("events", []):
                comp = (ev.get("competitions") or [{}])[0]
                names, by_team_id = {}, {}
                for c in comp.get("competitors", []):
                    team_name = (c.get("team") or {}).get("displayName", "?")
                    names[c.get("homeAway", "")] = team_name
                    by_team_id[str((c.get("team") or {}).get("id"))] = team_name
                match = "{} — {}".format(names.get("home", "?"), names.get("away", "?"))
                for d in comp.get("details", []):
                    kind = self._classify(d)
                    if not kind:
                        continue
                    athletes = d.get("athletesInvolved") or []
                    player = athletes[0].get("displayName", "") if athletes else ""
                    minute = (d.get("clock") or {}).get("displayValue", "")
                    key = "es:{}:{}:{}:{}".format(
                        ev.get("id"), (d.get("type") or {}).get("id"), minute, player)
                    results.append(PenaltyEvent(
                        key=key, kind=kind, competition=league_name, match=match,
                        minute=minute, team=by_team_id.get(str((d.get("team") or {}).get("id")), ""),
                        player=player, source=self.name, raw=d))
        return results

    @staticmethod
    def _classify(d):
        text = ((d.get("type") or {}).get("text") or "").lower()
        if not (d.get("penaltyKick") or "penalty" in text):
            return None
        if "shootout" in text:
            return "penalty_shootout"
        if d.get("scoringPlay") or "scored" in text:
            return "penalty_goal"
        if "missed" in text or "saved" in text:
            return "penalty_missed"
        return "penalty_awarded"


class SofascoreSource:
    """Неофициальный API Sofascore. Бесплатно, но требует curl_cffi (TLS)."""

    name = "sofascore"
    BASE = "https://api.sofascore.com/api/v1"

    def __init__(self, session, max_events=120, request_pause=0.25):
        self.session = session
        self.max_events = max_events
        self.request_pause = request_pause

    def _get(self, path):
        resp = self.session.get(self.BASE + path, headers={"User-Agent": UA}, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def check(self):
        self._get("/sport/football/events/live")

    def poll(self):
        events = self._get("/sport/football/events/live").get("events", [])[: self.max_events]
        results = []
        for ev in events:
            ev_id = ev.get("id")
            match = "{} — {}".format(
                ev.get("homeTeam", {}).get("name", "?"),
                ev.get("awayTeam", {}).get("name", "?"),
            )
            competition = ev.get("tournament", {}).get("name", "")
            try:
                incidents = self._get(f"/event/{ev_id}/incidents").get("incidents", [])
            except NET_ERRORS:
                continue
            for inc in incidents:
                kind = self._classify(inc)
                if not kind:
                    continue
                inc_key = inc.get("id") or "{}:{}:{}".format(
                    inc.get("incidentType"), inc.get("time"), inc.get("addedTime"))
                results.append(PenaltyEvent(
                    key=f"ss:{ev_id}:{inc_key}",
                    kind=kind,
                    competition=competition,
                    match=match,
                    minute=inc.get("time"),
                    team=self._team_name(ev, inc),
                    player=(inc.get("player") or {}).get("name", ""),
                    source=self.name,
                    raw=inc,
                ))
            time.sleep(self.request_pause)
        return results

    @staticmethod
    def _team_name(ev, inc):
        is_home = inc.get("isHome")
        if is_home is None:
            return ""
        side = "homeTeam" if is_home else "awayTeam"
        return ev.get(side, {}).get("name", "")

    @staticmethod
    def _classify(inc):
        itype = (inc.get("incidentType") or "").lower()
        iclass = (inc.get("incidentClass") or "").lower()
        ifrom = (inc.get("from") or "").lower()
        if itype == "goal" and ("penalty" in iclass or "penalty" in ifrom):
            return "penalty_goal"
        if itype == "ingamepenalty":
            return "penalty_goal" if "scored" in iclass else "penalty_missed"
        if itype == "vardecision" and "penalty" in iclass:
            return "penalty_var"
        if itype == "penaltyshootout":
            return "penalty_shootout"
        return None


class ApiFootballSource:
    """Официальный API-Football (api-sports.io). Один запрос на цикл."""

    name = "api-football"
    BASE = "https://v3.football.api-sports.io"

    def __init__(self, session, api_key):
        self.session = session
        self.api_key = api_key

    def check(self):
        resp = self.session.get(self.BASE + "/status",
                                headers={"x-apisports-key": self.api_key, "User-Agent": UA},
                                timeout=15)
        resp.raise_for_status()

    def poll(self):
        resp = self.session.get(
            self.BASE + "/fixtures",
            params={"live": "all"},
            headers={"x-apisports-key": self.api_key, "User-Agent": UA},
            timeout=20,
        )
        resp.raise_for_status()
        payload = resp.json()
        results = []
        for fx in payload.get("response", []):
            fixture_id = fx.get("fixture", {}).get("id")
            match = "{} — {}".format(
                fx.get("teams", {}).get("home", {}).get("name", "?"),
                fx.get("teams", {}).get("away", {}).get("name", "?"),
            )
            competition = fx.get("league", {}).get("name", "")
            for ev in fx.get("events", []):
                kind = self._classify(ev)
                if not kind:
                    continue
                minute = (ev.get("time") or {}).get("elapsed")
                player = (ev.get("player") or {}).get("name") or ""
                key = "af:{}:{}:{}:{}:{}".format(
                    fixture_id, ev.get("type"), ev.get("detail"), minute, player)
                results.append(PenaltyEvent(
                    key=key,
                    kind=kind,
                    competition=competition,
                    match=match,
                    minute=minute,
                    team=(ev.get("team") or {}).get("name", ""),
                    player=player,
                    source=self.name,
                    raw=ev,
                ))
        return results

    @staticmethod
    def _classify(ev):
        etype = (ev.get("type") or "").lower()
        detail = (ev.get("detail") or "").lower()
        if "penalty" not in detail:
            return None
        if etype == "goal":
            return "penalty_missed" if "missed" in detail else "penalty_goal"
        if etype == "var":
            if "cancelled" in detail or "not awarded" in detail:
                return "penalty_cancelled"
            if "confirmed" in detail or "awarded" in detail:
                return "penalty_awarded"
            return "penalty_var"
        return None


class Alerter:
    def __init__(self, session, jsonl_path):
        self.session = session
        self.jsonl_path = jsonl_path
        self.tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.tg_chat = os.environ.get("TELEGRAM_CHAT_ID")
        self.webhook = os.environ.get("PENALTY_WEBHOOK_URL")

    def emit(self, event):
        line = event.format_ru()
        print(f"[{now_iso()}] {line}", flush=True)
        try:
            with open(self.jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        except OSError as e:
            print(f"[warn] не удалось записать JSONL: {e}", file=sys.stderr)
        if self.tg_token and self.tg_chat:
            try:
                self.session.post(
                    f"https://api.telegram.org/bot{self.tg_token}/sendMessage",
                    json={"chat_id": self.tg_chat, "text": line},
                    timeout=10,
                )
            except NET_ERRORS as e:
                print(f"[warn] Telegram: {e}", file=sys.stderr)
        if self.webhook:
            try:
                self.session.post(self.webhook, json=event.to_dict(), timeout=10)
            except NET_ERRORS as e:
                print(f"[warn] webhook: {e}", file=sys.stderr)


def load_state(path):
    try:
        with open(path, encoding="utf-8") as f:
            return set(json.load(f))
    except (OSError, ValueError):
        return set()


def save_state(path, seen):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f)
    os.replace(tmp, path)


def build_source(name, session, espn_leagues):
    if name == "espn":
        return ESPNSource(session, espn_leagues)
    if name == "sofascore":
        return SofascoreSource(session)
    if name == "api-football":
        key = os.environ.get("API_FOOTBALL_KEY")
        if not key:
            sys.exit("Для --source api-football задайте API_FOOTBALL_KEY")
        return ApiFootballSource(session, key)
    sys.exit(f"Неизвестный источник: {name}")


def pick_auto_source(session, espn_leagues):
    """espn → sofascore → api-football: первый, чей check() прошёл."""
    candidates = [ESPNSource(session, espn_leagues), SofascoreSource(session)]
    if os.environ.get("API_FOOTBALL_KEY"):
        candidates.append(ApiFootballSource(session, os.environ["API_FOOTBALL_KEY"]))
    for src in candidates:
        try:
            src.check()
            return src
        except NET_ERRORS as e:
            print(f"[info] {src.name} недоступен ({e}), пробую следующий",
                  file=sys.stderr)
    sys.exit("Ни один источник не доступен. Для Sofascore поставьте curl_cffi "
             "(pip install curl_cffi); для api-football задайте API_FOOTBALL_KEY.")


def main():
    ap = argparse.ArgumentParser(description="Live-монитор пенальти")
    ap.add_argument("--source", choices=["espn", "sofascore", "api-football", "auto"],
                    default="auto", help="источник данных (auto: espn → sofascore → api-football)")
    ap.add_argument("--espn-leagues", default=",".join(ESPNSource.DEFAULT_LEAGUES),
                    help="лиги ESPN через запятую (eng.2 = Championship, eng.3 = League One...)")
    ap.add_argument("--interval", type=int, default=20, help="интервал опроса, сек (default 20)")
    ap.add_argument("--once", action="store_true", help="один проход и выход (проверка доступности)")
    ap.add_argument("--state-file", default="penalty_state.json",
                    help="файл с ключами уже отправленных событий")
    ap.add_argument("--jsonl", default="penalties.jsonl", help="журнал событий в JSONL")
    ap.add_argument("--backfill", action="store_true",
                    help="алертить и старые события первого прохода (по умолчанию первый проход только заполняет state)")
    args = ap.parse_args()

    session = make_session()
    print(f"[info] TLS-имитация Chrome: {'да (curl_cffi)' if HAVE_CURL_CFFI else 'нет — pip install curl_cffi для Sofascore/Flashscore'}",
          file=sys.stderr)

    espn_leagues = [x.strip() for x in args.espn_leagues.split(",") if x.strip()]
    if args.source == "auto":
        source = pick_auto_source(session, espn_leagues)
    else:
        source = build_source(args.source, session, espn_leagues)

    alerter = Alerter(session, args.jsonl)
    seen = load_state(args.state_file)
    first_pass = not seen and not args.backfill

    stop = {"flag": False}
    signal.signal(signal.SIGINT, lambda *_: stop.update(flag=True))
    signal.signal(signal.SIGTERM, lambda *_: stop.update(flag=True))

    print(f"[info] источник: {source.name}, интервал: {args.interval}s, "
          f"state: {args.state_file}", file=sys.stderr)

    while not stop["flag"]:
        try:
            events = source.poll()
        except NET_ERRORS as e:
            print(f"[warn] опрос не удался: {e}", file=sys.stderr)
            events = []
        fresh = [ev for ev in events if ev.key not in seen]
        for ev in fresh:
            seen.add(ev.key)
            if first_pass:
                continue  # не алертим события, случившиеся до запуска
            alerter.emit(ev)
        if fresh:
            save_state(args.state_file, seen)
        if first_pass:
            print(f"[info] первый проход: {len(fresh)} прошлых пенальти-событий "
                  f"занесено в state без алертов", file=sys.stderr)
            first_pass = False
        if args.once:
            print(f"[info] --once: найдено пенальти-событий: {len(events)}",
                  file=sys.stderr)
            break
        for _ in range(args.interval):
            if stop["flag"]:
                break
            time.sleep(1)

    save_state(args.state_file, seen)
    print("[info] остановлен", file=sys.stderr)


if __name__ == "__main__":
    main()
