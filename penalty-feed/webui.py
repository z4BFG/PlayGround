#!/usr/bin/env python3
"""Локальная веб-панель для penalty-feed: всё запускается кнопками.

    python3 webui.py            # затем откройте http://127.0.0.1:8765

Кнопки:
  - Разведка Flashscore  — запускает flashscore_probe.py, лог виден на странице
  - Запустить монитор    — penalty_monitor.py, пойманные пенальти в таблице
  - Остановить           — останавливает выбранный процесс

Только стандартная библиотека; скрипты запускаются как подпроцессы
из этой же директории. Сервер слушает только 127.0.0.1.
"""

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(HERE, "logs")
PORT = int(os.environ.get("PENALTY_UI_PORT", "8765"))

JOBS = {
    "probe": {
        "title": "Разведка Flashscore",
        "cmd": [sys.executable, "-u", "flashscore_probe.py"],
    },
    "monitor": {
        "title": "Монитор пенальти",
        "cmd": [sys.executable, "-u", "penalty_monitor.py", "--interval", "20"],
    },
}
procs = {}
lock = threading.Lock()


def log_path(name):
    return os.path.join(LOG_DIR, f"{name}.log")


def is_running(name):
    p = procs.get(name)
    return p is not None and p.poll() is None


def start_job(name):
    with lock:
        if is_running(name):
            return False, "уже запущен"
        os.makedirs(LOG_DIR, exist_ok=True)
        logf = open(log_path(name), "w", encoding="utf-8")
        env = dict(os.environ, PYTHONUNBUFFERED="1")
        procs[name] = subprocess.Popen(
            JOBS[name]["cmd"], cwd=HERE, stdout=logf, stderr=subprocess.STDOUT, env=env)
        return True, "запущен"


def stop_job(name):
    with lock:
        p = procs.get(name)
        if p is None or p.poll() is not None:
            return False, "не запущен"
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
        return True, "остановлен"


def tail(path, max_bytes=8000):
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - max_bytes))
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def read_penalties(limit=30):
    events = []
    try:
        with open(os.path.join(HERE, "penalties.jsonl"), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except ValueError:
                        pass
    except OSError:
        pass
    return events[-limit:][::-1]


def status_payload():
    return {
        "jobs": {
            name: {
                "title": job["title"],
                "running": is_running(name),
                "log": tail(log_path(name)),
            }
            for name, job in JOBS.items()
        },
        "penalties": read_penalties(),
    }


PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Penalty Feed — панель</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, sans-serif; max-width: 1100px; margin: 24px auto;
         padding: 0 16px; line-height: 1.45; }
  h1 { font-size: 1.35rem; } h2 { font-size: 1.05rem; margin: 20px 0 8px; }
  .job { border: 1px solid rgba(128,128,128,.35); border-radius: 10px;
         padding: 12px 14px; margin: 12px 0; }
  .row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .dot { width: 10px; height: 10px; border-radius: 50%; background: #999; }
  .dot.on { background: #2ea043; }
  button { padding: 6px 14px; border-radius: 8px; border: 1px solid rgba(128,128,128,.5);
           cursor: pointer; font-size: .95rem; background: transparent; }
  button:hover { background: rgba(128,128,128,.15); }
  pre { background: rgba(128,128,128,.12); border-radius: 8px; padding: 10px;
        max-height: 260px; overflow: auto; font-size: .8rem; white-space: pre-wrap; }
  table { border-collapse: collapse; width: 100%; font-size: .9rem; }
  th, td { border-bottom: 1px solid rgba(128,128,128,.3); padding: 6px 8px; text-align: left; }
  .muted { opacity: .65; font-size: .85rem; }
</style></head><body>
<h1>⚽ Penalty Feed — локальная панель</h1>
<p class="muted">Кнопки запускают скрипты на этом компьютере. Страница обновляется сама раз в 2 секунды.</p>
<div id="jobs"></div>
<h2>Пойманные пенальти</h2>
<table><thead><tr><th>Когда (UTC)</th><th>Событие</th><th>Мин.</th><th>Матч</th>
<th>Команда</th><th>Игрок</th><th>Турнир</th><th>Источник</th></tr></thead>
<tbody id="pens"><tr><td colspan="8" class="muted">пока пусто — запустите монитор</td></tr></tbody></table>
<script>
async function act(name, verb) {
  await fetch(`/${verb}/${name}`, {method: "POST"});
  refresh();
}
function esc(s) { return (s ?? "").toString().replace(/[&<>]/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c])); }
async function refresh() {
  let st;
  try { st = await (await fetch("/status")).json(); } catch { return; }
  const jobs = document.getElementById("jobs");
  jobs.innerHTML = "";
  for (const [name, j] of Object.entries(st.jobs)) {
    const d = document.createElement("div");
    d.className = "job";
    d.innerHTML = `<div class="row">
        <span class="dot ${j.running ? "on" : ""}"></span>
        <strong>${esc(j.title)}</strong>
        <span class="muted">${j.running ? "работает" : "остановлен"}</span>
        <button onclick="act('${name}','run')" ${j.running ? "disabled" : ""}>▶ Запустить</button>
        <button onclick="act('${name}','stop')" ${j.running ? "" : "disabled"}>⏹ Остановить</button>
      </div>
      <pre>${esc(j.log) || "— лога пока нет —"}</pre>`;
    jobs.appendChild(d);
  }
  const tb = document.getElementById("pens");
  if (st.penalties.length) {
    tb.innerHTML = st.penalties.map(p => `<tr>
      <td>${esc((p.detected_at || "").replace("T", " ").replace("+00:00", ""))}</td>
      <td>${esc(p.label || p.kind)}</td><td>${esc(p.minute)}</td>
      <td>${esc(p.match)}</td><td>${esc(p.team)}</td><td>${esc(p.player)}</td>
      <td>${esc(p.competition)}</td><td>${esc(p.source)}</td></tr>`).join("");
  }
}
refresh(); setInterval(refresh, 2000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            self._send(200, PAGE, "text/html; charset=utf-8")
        elif self.path == "/status":
            self._send(200, json.dumps(status_payload(), ensure_ascii=False))
        else:
            self._send(404, '{"error": "not found"}')

    def do_POST(self):
        parts = self.path.strip("/").split("/")
        if len(parts) == 2 and parts[0] in ("run", "stop") and parts[1] in JOBS:
            ok, msg = (start_job if parts[0] == "run" else stop_job)(parts[1])
            self._send(200 if ok else 409, json.dumps({"ok": ok, "msg": msg}))
        else:
            self._send(404, '{"error": "not found"}')

    def log_message(self, *args):
        pass  # не шумим в консоль на каждый poll


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Панель запущена: http://127.0.0.1:{PORT}  (Ctrl+C — выход)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for name in JOBS:
            stop_job(name)


if __name__ == "__main__":
    main()
