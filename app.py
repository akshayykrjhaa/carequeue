import os, time
import psycopg2, redis
from flask import Flask, request, jsonify, redirect, render_template_string, url_for

app = Flask(__name__)
VERSION = os.getenv("APP_VERSION", "v1")
COLOR = os.getenv("APP_COLOR", "blue")
cache = redis.Redis(host=os.getenv("REDIS_HOST", "cache"), port=6379, decode_responses=True)

DEPTS = [("A", "General Medicine", "Room 1"), ("P", "Paediatrics", "Room 2"), ("O", "Orthopaedics", "Room 3"),
         ("C", "Cardiology", "Room 4"), ("E", "ENT", "Room 5")]
DEPT = {d[0]: d for d in DEPTS}
NAMES = {d[0]: d[1] for d in DEPTS}
SEED = ["Ravi M.", "Asha K.", "Imran S.", "Meera P.", "John D.", "Priya R.", "Kabir T.", "Neha G.",
        "Arjun V.", "Fatima Z.", "Sunil B.", "Lakshmi N.", "Rohan C.", "Divya S.", "Vikram J."]


def connect():
    return psycopg2.connect(host=os.getenv("DB_HOST", "db"), dbname=os.getenv("DB_NAME", "careq"),
                            user=os.getenv("DB_USER", "careq"), password=os.getenv("DB_PASSWORD", "careqpass"))


def query(sql, params=(), fetch=False):
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall() if fetch else None
        conn.commit()
        return rows
    finally:
        conn.close()


def init_db():
    for _ in range(30):
        try:
            query("""CREATE TABLE IF NOT EXISTS tokens (
                       id SERIAL PRIMARY KEY, code TEXT NOT NULL, dept TEXT NOT NULL,
                       patient TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'waiting',
                       created_at TIMESTAMPTZ DEFAULT now())""")
            if query("SELECT COUNT(*) FROM tokens", fetch=True)[0][0] == 0:
                names = iter(SEED)
                for p, _, _ in DEPTS:
                    for n in range(1, 4):
                        status = "serving" if n == 1 else "waiting"
                        query("INSERT INTO tokens (code, dept, patient, status) VALUES (%s, %s, %s, %s)",
                              (f"{p}-{n:03d}", p, next(names), status))
            return
        except psycopg2.OperationalError:
            time.sleep(2)
    raise RuntimeError("database not reachable")


init_db()


def safe(fn, default):
    try:
        return fn()
    except redis.RedisError:
        return default

PAGE = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CareQueue</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Familjen+Grotesk:wght@600;700&family=Public+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@600;700&display=swap" rel="stylesheet">
<style>
:root{--ink:#13201F;--paper:#EEF2EF;--card:#fff;--line:#D5DDD8;--muted:#566662;--board:#0D1514;--led:#FFB627;--env:{{ envc }}}
*{box-sizing:border-box;margin:0}
body{font-family:"Public Sans",system-ui,sans-serif;background:var(--paper);color:var(--ink);line-height:1.5}
.wrap{max-width:1100px;margin:0 auto;padding:0 20px}
header{background:var(--card);border-bottom:1px solid var(--line)}
header .wrap{display:flex;align-items:center;justify-content:space-between;gap:12px;padding-top:14px;padding-bottom:14px;flex-wrap:wrap}
.brand{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.brand b{font-family:"Familjen Grotesk",sans-serif;font-size:1.45rem;letter-spacing:-.01em}
.brand span{color:var(--muted);font-size:.9rem}
.pill{display:inline-flex;align-items:center;gap:8px;background:var(--env);color:#fff;border-radius:999px;padding:6px 12px;font-size:.78rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase}
.pill i{width:8px;height:8px;border-radius:50%;background:#fff}
.board{background:var(--board);color:#C9D4D1;margin-top:24px;border-radius:16px;padding:22px 22px 18px}
.board h1{font-family:"Familjen Grotesk",sans-serif;font-size:1rem;letter-spacing:.14em;text-transform:uppercase;color:#8FA19C;font-weight:600}
.cells{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-top:14px}
.cell{border:1px solid #23302E;border-radius:10px;padding:12px 12px 10px;background:#111C1B}
.cell small{display:block;font-size:.78rem;color:#8FA19C}
.tok{font-family:"JetBrains Mono",monospace;font-weight:700;font-size:2.6rem;line-height:1;color:var(--led);text-shadow:0 0 12px rgba(255,182,39,.35);margin:6px 0 2px;letter-spacing:.04em}
.tok.off{color:#3A4A47;text-shadow:none}
.cell em{font-style:normal;font-size:.82rem}
.ticker{margin-top:14px;font-size:.88rem;color:#8FA19C;display:flex;align-items:center;gap:8px}
.ticker b{color:var(--led);font-weight:600}
.blink{width:8px;height:8px;border-radius:50%;background:var(--led);animation:b 1.4s infinite}
@keyframes b{50%{opacity:.2}}
.mine{margin-top:18px;background:var(--card);border:2px solid var(--ink);border-radius:14px;padding:16px 20px;display:flex;gap:20px;align-items:center;flex-wrap:wrap}
.mine .tok{color:var(--ink);text-shadow:none;font-size:2.8rem;margin:0}
.mine strong{display:block;font-size:1.1rem}
.mine p{color:var(--muted)}
.grid{display:grid;grid-template-columns:340px 1fr;gap:18px;margin-top:18px;align-items:start}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}
.card h2{font-family:"Familjen Grotesk",sans-serif;font-size:1.1rem;padding:14px 18px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.card h2 span{font-family:"Public Sans",sans-serif;font-size:.82rem;color:var(--muted);font-weight:500}
form.take{padding:16px 18px 18px;display:grid;gap:12px}
label{font-size:.82rem;font-weight:600;display:grid;gap:4px}
input,select{font:inherit;padding:10px 11px;border:1px solid #BCC8C3;border-radius:8px;background:#fff}
.btn{font:inherit;font-weight:700;border:0;border-radius:8px;padding:11px 14px;background:var(--ink);color:#fff;cursor:pointer}
.btn.ghost{background:transparent;border:1px solid var(--ink);color:var(--ink);padding:7px 12px;font-size:.85rem}
.btn:disabled{opacity:.35;cursor:not-allowed}
:focus-visible{outline:3px solid var(--env);outline-offset:2px}
.q{list-style:none;padding:0}
.q li{display:grid;grid-template-columns:76px 1fr auto;gap:12px;align-items:center;padding:11px 18px;border-bottom:1px solid #E6ECE9}
.q li:last-child{border-bottom:0}
.code{font-family:"JetBrains Mono",monospace;font-weight:700;font-size:1.15rem;line-height:1}
.dept{font-size:.8rem;color:var(--muted)}
.empty{padding:28px 18px;color:var(--muted);text-align:center}
.desk{margin-top:18px}
.desk table{width:100%;border-collapse:collapse}
.desk td,.desk th{padding:11px 18px;border-bottom:1px solid #E6ECE9;text-align:left;font-size:.92rem}
.desk th{font-size:.78rem;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.06em}
.desk tr:last-child td{border-bottom:0}
footer{margin:22px 0 36px;font-size:.82rem;color:var(--muted);display:flex;gap:16px;flex-wrap:wrap}
@media(max-width:900px){.cells{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}}
@media(max-width:520px){.tok{font-size:2.2rem}.desk th:nth-child(3),.desk td:nth-child(3){display:none}}
@media(prefers-reduced-motion:reduce){.blink{animation:none}}
</style></head>
<body>
<header><div class="wrap">
  <div class="brand"><b>CareQueue</b><span>City Hospital outpatient department · blue-green release</span></div>
  <span class="pill"><i></i>{{ color }} {{ version }}</span>
</div></header>
<main class="wrap">
  <section class="board" aria-label="Now serving">
    <h1>Now serving</h1>
    <div class="cells">
    {% for p, name, room in depts %}
      <div class="cell"><small>{{ name }}</small>
        {% if serving[p] %}<div class="tok">{{ serving[p] }}</div>{% else %}<div class="tok off">---</div>{% endif %}
        <em>{{ room }}</em></div>
    {% endfor %}
    </div>
    <p class="ticker">{% if last_call %}<span class="blink" aria-hidden="true"></span>Last call: <b>{{ last_call }}</b>{% else %}No patients called yet.{% endif %}</p>
  </section>

  {% if mine %}
  <section class="mine" id="mine" aria-live="polite">
    <div class="tok">{{ mine.code }}</div>
    <div><strong>{{ mine.headline }}</strong><p>{{ mine.detail }}</p></div>
  </section>
  {% endif %}

  <div class="grid">
    <section class="card">
      <h2>Take a token</h2>
      <form class="take" method="post" action="/take">
        <label>Patient name<input name="patient" required maxlength="60" autocomplete="off"></label>
        <label>Department
          <select name="dept" required>
            <option value="" disabled selected>Choose a department</option>
            {% for p, name, room in depts %}<option value="{{ p }}">{{ name }} ({{ room }})</option>{% endfor %}
          </select>
        </label>
        <button class="btn" type="submit">Get token</button>
      </form>
    </section>
    <section class="card">
      <h2>Waiting <span>{{ waiting|length }} patients</span></h2>
      {% if waiting %}<ul class="q">
        {% for code, d, patient in waiting %}<li><span class="code">{{ code }}</span><span>{{ patient }}</span><span class="dept">{{ names[d] }}</span></li>{% endfor %}
      </ul>{% else %}<p class="empty">Nobody is waiting. New tokens will appear here.</p>{% endif %}
    </section>
  </div>

  <section class="card desk" id="desk">
    <h2>Reception desk <span>{{ served }} patients seen</span></h2>
    <table>
      <tr><th>Department</th><th>Serving</th><th>Waiting</th><th><span class="dept">Action</span></th></tr>
      {% for p, name, room in depts %}
      <tr><td>{{ name }}</td><td class="code">{{ serving[p] or "---" }}</td><td>{{ counts[p] }}</td>
        <td><form method="post" action="/call/{{ p }}"><button class="btn ghost" type="submit" {% if not counts[p] and not serving[p] %}disabled{% endif %}>Call next</button></form></td></tr>
      {% endfor %}
    </table>
  </section>

  <footer><span>Tokens stored in PostgreSQL</span><span>Live counters in Redis: {{ visits }} page views, {{ calls }} calls</span></footer>
</main>
</body></html>"""


@app.route("/")
def home():
    visits = safe(lambda: cache.incr("visits"), "n/a")
    calls = safe(lambda: cache.get("calls") or 0, "n/a")
    last_call = safe(lambda: cache.get("last_call"), None)
    rows = query("SELECT code, dept, patient, status FROM tokens WHERE status <> 'done' ORDER BY id", fetch=True)
    serving = {p: None for p in DEPT}
    counts = {p: 0 for p in DEPT}
    waiting = []
    for code, dept, patient, status in rows:
        if status == "serving":
            serving[dept] = code
        else:
            waiting.append((code, dept, patient))
            counts[dept] += 1
    served = query("SELECT COUNT(*) FROM tokens WHERE status = 'done'", fetch=True)[0][0]

    mine = None
    t = request.args.get("t")
    if t:
        r = query("SELECT id, code, dept, status FROM tokens WHERE code = %s ORDER BY id DESC LIMIT 1", (t,), fetch=True)
        if r:
            tid, code, dept, status = r[0]
            if status == "waiting":
                ahead = query("SELECT COUNT(*) FROM tokens WHERE dept = %s AND status = 'waiting' AND id < %s",
                              (dept, tid), fetch=True)[0][0]
                word = "patient" if ahead == 1 else "patients"
                mine = {"code": code, "headline": "Your token is in the queue",
                        "detail": f"{ahead} {word} ahead of you for {NAMES[dept]}. Watch the board for your number."}
            elif status == "serving":
                mine = {"code": code, "headline": f"It's your turn. Please go to {DEPT[dept][2]}.", "detail": NAMES[dept]}
            else:
                mine = {"code": code, "headline": "You have been seen", "detail": "This token is closed."}

    envc = "#0F9D6B" if COLOR == "green" else "#2457D6"
    return render_template_string(PAGE, depts=DEPTS, names=NAMES, serving=serving, counts=counts, waiting=waiting,
                                  served=served, mine=mine, visits=visits, calls=calls, last_call=last_call,
                                  version=VERSION, color=COLOR, envc=envc)


@app.route("/take", methods=["POST"])
def take():
    dept = request.form.get("dept", "")
    patient = request.form.get("patient", "").strip()[:60]
    if dept not in DEPT or not patient:
        return redirect(url_for("home"))
    n = query("SELECT COUNT(*) FROM tokens WHERE dept = %s", (dept,), fetch=True)[0][0] + 1
    code = f"{dept}-{n:03d}"
    query("INSERT INTO tokens (code, dept, patient) VALUES (%s, %s, %s)", (code, dept, patient))
    return redirect(url_for("home", t=code) + "#mine")


@app.route("/call/<dept>", methods=["POST"])
def call_next(dept):
    if dept not in DEPT:
        return redirect(url_for("home"))
    query("UPDATE tokens SET status = 'done' WHERE dept = %s AND status = 'serving'", (dept,))
    nxt = query("SELECT id, code FROM tokens WHERE dept = %s AND status = 'waiting' ORDER BY id LIMIT 1", (dept,), fetch=True)
    if nxt:
        query("UPDATE tokens SET status = 'serving' WHERE id = %s", (nxt[0][0],))
        safe(lambda: cache.set("last_call", f"{nxt[0][1]} to {DEPT[dept][2]}"), None)
        safe(lambda: cache.incr("calls"), None)
    return redirect(url_for("home") + "#desk")


@app.route("/api/queue")
def api_queue():
    rows = query("SELECT code, dept, patient, status FROM tokens WHERE status <> 'done' ORDER BY id", fetch=True)
    return jsonify([{"code": r[0], "department": NAMES[r[1]], "patient": r[2], "status": r[3]} for r in rows])


@app.route("/health")
def health():
    try:
        query("SELECT 1", fetch=True)
        cache.ping()
        return jsonify(status="ok", version=VERSION, color=COLOR), 200
    except Exception:
        return jsonify(status="error"), 500
