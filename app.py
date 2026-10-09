"""
Blood Donation Management System - live Python version
Flask + SQLite. Run:  pip install flask  &&  python app.py
Open: http://127.0.0.1:5000
"""
import random
import sqlite3
from datetime import date, timedelta

from flask import Flask, g, jsonify, redirect, render_template_string, request, url_for

DB = "blood_donation.db"
ELIGIBLE_DAYS = 90  # 3 months gap between donations
BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

# recipient -> donor groups that can safely donate to them
COMPATIBLE = {
    "A+": ["A+", "A-", "O+", "O-"],
    "A-": ["A-", "O-"],
    "B+": ["B+", "B-", "O+", "O-"],
    "B-": ["B-", "O-"],
    "AB+": BLOOD_GROUPS,
    "AB-": ["A-", "B-", "AB-", "O-"],
    "O+": ["O+", "O-"],
    "O-": ["O-"],
}

app = Flask(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS Donors (
    donor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    blood_group TEXT NOT NULL,
    phone TEXT,
    city TEXT,
    last_donation_date TEXT
);
CREATE TABLE IF NOT EXISTS BloodRequests (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_name TEXT NOT NULL,
    blood_group_needed TEXT NOT NULL,
    hospital_name TEXT,
    urgency_level TEXT DEFAULT 'Medium',
    request_date TEXT,
    status TEXT DEFAULT 'Open'
);
CREATE TABLE IF NOT EXISTS Donations (
    donation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id INTEGER NOT NULL REFERENCES Donors(donor_id),
    request_id INTEGER NOT NULL REFERENCES BloodRequests(request_id),
    donation_date TEXT,
    status TEXT DEFAULT 'Completed'
);
-- View: donors who are eligible (never donated, or last donation >= 90 days ago)
CREATE VIEW IF NOT EXISTS AvailableDonors AS
SELECT * FROM Donors
WHERE last_donation_date IS NULL
   OR last_donation_date <= date('now', '-90 day');
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    db = sqlite3.connect(DB)
    db.executescript(SCHEMA)
    if db.execute("SELECT COUNT(*) FROM Donors").fetchone()[0] == 0:
        seed(db)
    db.commit()
    db.close()


def seed(db):
    """Sample data generator (same idea as generator.py)."""
    first = ["Rahim", "Karim", "Sohan", "Rana", "Hasan", "Nusrat", "Mim", "Tania",
             "Sakib", "Rafi", "Anika", "Sumaiya", "Imran", "Nabil", "Farhan", "Jannat"]
    last = ["Ahmed", "Hossain", "Islam", "Khan", "Chowdhury", "Sarker", "Uddin", "Akter"]
    cities = ["Dhaka", "Chattogram", "Sylhet", "Rajshahi", "Khulna", "Barishal", "Rangpur"]
    hospitals = ["Dhaka Medical College", "Square Hospital", "Evercare Hospital",
                 "Chattogram Medical", "Sylhet MAG Osmani", "Khulna Medical College"]
    today = date.today()
    for _ in range(60):
        last_don = None if random.random() < 0.2 else str(today - timedelta(days=random.randint(5, 400)))
        db.execute(
            "INSERT INTO Donors(name, blood_group, phone, city, last_donation_date) VALUES (?,?,?,?,?)",
            (f"{random.choice(first)} {random.choice(last)}", random.choice(BLOOD_GROUPS),
             "01" + str(random.randint(300000000, 999999999)), random.choice(cities), last_don),
        )
    for _ in range(15):
        db.execute(
            "INSERT INTO BloodRequests(patient_name, blood_group_needed, hospital_name, urgency_level, request_date) "
            "VALUES (?,?,?,?,?)",
            (f"{random.choice(first)} {random.choice(last)}", random.choice(BLOOD_GROUPS),
             random.choice(hospitals), random.choice(["Low", "Medium", "High", "Critical"]),
             str(today - timedelta(days=random.randint(0, 20)))),
        )


# ---------------------------------------------------------------- templates
LAYOUT = """
<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Blood Donation System</title>
<style>
:root{--red:#c62828;--bg:#fafafa;--card:#fff;--line:#e5e5e5;--ink:#222}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,sans-serif;background:var(--bg);color:var(--ink)}
header{background:var(--red);color:#fff;padding:14px 20px;display:flex;gap:20px;align-items:center;flex-wrap:wrap}
header a{color:#fff;text-decoration:none;font-weight:500}header .brand{font-size:1.2rem;font-weight:700}
main{max-width:1000px;margin:20px auto;padding:0 16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin-bottom:16px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.stat b{display:block;font-size:1.8rem;color:var(--red)}
table{width:100%;border-collapse:collapse;font-size:.92rem}
th,td{text-align:left;padding:8px;border-bottom:1px solid var(--line)}th{background:#f3f3f3}
form.inline{display:flex;gap:8px;flex-wrap:wrap;align-items:end}
input,select{padding:7px;border:1px solid #bbb;border-radius:6px;font:inherit}
button,.btn{background:var(--red);color:#fff;border:0;border-radius:6px;padding:7px 12px;cursor:pointer;text-decoration:none;font:inherit;display:inline-block}
.tag{padding:2px 8px;border-radius:99px;font-size:.78rem;background:#eee}
.Critical{background:#c62828;color:#fff}.High{background:#ef6c00;color:#fff}.Medium{background:#f9a825}.Low{background:#66bb6a;color:#fff}
.ok{color:#2e7d32}.no{color:#999}.flash{background:#e8f5e9;border:1px solid #a5d6a7;padding:10px;border-radius:8px;margin-bottom:12px}
label{font-size:.8rem;display:block;color:#555}
</style></head><body>
<header><span class="brand">🩸 Blood Donation System</span>
<a href="{{ url_for('home') }}">Dashboard</a><a href="{{ url_for('donors') }}">Donors</a>
<a href="{{ url_for('requests_page') }}">Requests</a><a href="{{ url_for('donations') }}">Donations</a></header>
<main>{% if msg %}<div class="flash">{{ msg }}</div>{% endif %}{{ body|safe }}</main></body></html>
"""


def page(body_tpl, **ctx):
    body = render_template_string(body_tpl, **ctx)
    return render_template_string(LAYOUT, body=body, msg=request.args.get("msg"))


def bg_options(selected=""):
    return "".join(f'<option {"selected" if b == selected else ""}>{b}</option>' for b in BLOOD_GROUPS)


def is_eligible(last):
    if not last:
        return True
    return date.fromisoformat(last) <= date.today() - timedelta(days=ELIGIBLE_DAYS)


# ---------------------------------------------------------------- routes
@app.route("/")
def home():
    db = get_db()
    s = {
        "donors": db.execute("SELECT COUNT(*) FROM Donors").fetchone()[0],
        "available": db.execute("SELECT COUNT(*) FROM AvailableDonors").fetchone()[0],
        "open": db.execute("SELECT COUNT(*) FROM BloodRequests WHERE status='Open'").fetchone()[0],
        "done": db.execute("SELECT COUNT(*) FROM Donations").fetchone()[0],
    }
    by_group = db.execute(
        "SELECT blood_group, COUNT(*) c FROM AvailableDonors GROUP BY blood_group ORDER BY blood_group").fetchall()
    urgent = db.execute(
        "SELECT * FROM BloodRequests WHERE status='Open' ORDER BY "
        "CASE urgency_level WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END, request_date "
        "LIMIT 8").fetchall()
    return page("""
<div class="stats">
 <div class="card stat"><b>{{s.donors}}</b>Total donors</div>
 <div class="card stat"><b>{{s.available}}</b>Available now</div>
 <div class="card stat"><b>{{s.open}}</b>Open requests</div>
 <div class="card stat"><b>{{s.done}}</b>Donations</div></div>
<div class="card"><h3>Available donors by blood group</h3>
 {% for g in by_group %}<span class="tag">{{g.blood_group}}: {{g.c}}</span> {% endfor %}</div>
<div class="card"><h3>Most urgent open requests</h3><table>
<tr><th>Patient</th><th>Group</th><th>Hospital</th><th>Urgency</th><th></th></tr>
{% for r in urgent %}<tr><td>{{r.patient_name}}</td><td>{{r.blood_group_needed}}</td><td>{{r.hospital_name}}</td>
<td><span class="tag {{r.urgency_level}}">{{r.urgency_level}}</span></td>
<td><a class="btn" href="{{url_for('match', request_id=r.request_id)}}">Find donors</a></td></tr>{% endfor %}
</table></div>""", s=s, by_group=by_group, urgent=urgent)


@app.route("/donors")
def donors():
    bg = request.args.get("bg", "")
    city = request.args.get("city", "").strip()
    only = request.args.get("only", "")
    sql, args = "SELECT * FROM Donors WHERE 1=1", []
    if bg:
        sql += " AND blood_group=?"; args.append(bg)
    if city:
        sql += " AND city LIKE ?"; args.append(f"%{city}%")
    if only == "1":
        sql += " AND (last_donation_date IS NULL OR last_donation_date <= date('now','-90 day'))"
    rows = [dict(r, eligible=is_eligible(r["last_donation_date"]))
            for r in get_db().execute(sql + " ORDER BY name", args).fetchall()]
    return page("""
<div class="card"><h3>Add donor</h3>
<form class="inline" method="post" action="{{url_for('add_donor')}}">
 <div><label>Name</label><input name="name" required></div>
 <div><label>Blood group</label><select name="blood_group">{{opts|safe}}</select></div>
 <div><label>Phone</label><input name="phone"></div>
 <div><label>City</label><input name="city"></div>
 <div><label>Last donation</label><input type="date" name="last_donation_date"></div>
 <button>Add</button></form></div>
<div class="card"><form class="inline" method="get">
 <div><label>Blood group</label><select name="bg"><option value="">All</option>{{opts|safe}}</select></div>
 <div><label>City</label><input name="city" value="{{city}}"></div>
 <label><input type="checkbox" name="only" value="1" {{'checked' if only}}> Available only</label>
 <button>Filter</button></form></div>
<div class="card"><table><tr><th>Name</th><th>Group</th><th>Phone</th><th>City</th><th>Last donation</th><th>Status</th></tr>
{% for d in rows %}<tr><td>{{d.name}}</td><td>{{d.blood_group}}</td><td>{{d.phone}}</td><td>{{d.city}}</td>
<td>{{d.last_donation_date or '—'}}</td>
<td>{% if d.eligible %}<span class="ok">Available</span>{% else %}<span class="no">Resting</span>{% endif %}</td></tr>{% endfor %}
</table><p>{{rows|length}} donors</p></div>""", rows=rows, opts=bg_options(bg), city=city, only=only)


@app.post("/donors/add")
def add_donor():
    f = request.form
    db = get_db()
    db.execute("INSERT INTO Donors(name, blood_group, phone, city, last_donation_date) VALUES (?,?,?,?,?)",
               (f["name"], f["blood_group"], f.get("phone"), f.get("city"), f.get("last_donation_date") or None))
    db.commit()
    return redirect(url_for("donors", msg="Donor added"))


@app.route("/requests")
def requests_page():
    rows = get_db().execute("SELECT * FROM BloodRequests ORDER BY request_id DESC").fetchall()
    return page("""
<div class="card"><h3>New blood request</h3>
<form class="inline" method="post" action="{{url_for('add_request')}}">
 <div><label>Patient</label><input name="patient_name" required></div>
 <div><label>Blood group</label><select name="blood_group_needed">{{opts|safe}}</select></div>
 <div><label>Hospital</label><input name="hospital_name"></div>
 <div><label>Urgency</label><select name="urgency_level"><option>Low</option><option selected>Medium</option><option>High</option><option>Critical</option></select></div>
 <button>Create</button></form></div>
<div class="card"><table><tr><th>#</th><th>Patient</th><th>Group</th><th>Hospital</th><th>Urgency</th><th>Date</th><th>Status</th><th></th></tr>
{% for r in rows %}<tr><td>{{r.request_id}}</td><td>{{r.patient_name}}</td><td>{{r.blood_group_needed}}</td><td>{{r.hospital_name}}</td>
<td><span class="tag {{r.urgency_level}}">{{r.urgency_level}}</span></td><td>{{r.request_date}}</td><td>{{r.status}}</td>
<td>{% if r.status=='Open' %}<a class="btn" href="{{url_for('match', request_id=r.request_id)}}">Match</a>{% endif %}</td></tr>{% endfor %}
</table></div>""", rows=rows, opts=bg_options())


@app.post("/requests/add")
def add_request():
    f = request.form
    db = get_db()
    db.execute("INSERT INTO BloodRequests(patient_name, blood_group_needed, hospital_name, urgency_level, request_date) "
               "VALUES (?,?,?,?,?)",
               (f["patient_name"], f["blood_group_needed"], f.get("hospital_name"), f["urgency_level"], str(date.today())))
    db.commit()
    return redirect(url_for("requests_page", msg="Request created"))


def find_matches(db, req, exact):
    groups = [req["blood_group_needed"]] if exact else COMPATIBLE[req["blood_group_needed"]]
    q = ",".join("?" * len(groups))
    return db.execute(
        f"SELECT * FROM AvailableDonors WHERE blood_group IN ({q}) "
        f"ORDER BY (blood_group = ?) DESC, last_donation_date IS NOT NULL, last_donation_date",
        [*groups, req["blood_group_needed"]]).fetchall()


@app.route("/match/<int:request_id>")
def match(request_id):
    db = get_db()
    req = db.execute("SELECT * FROM BloodRequests WHERE request_id=?", (request_id,)).fetchone()
    if not req:
        return redirect(url_for("requests_page", msg="Request not found"))
    exact = request.args.get("exact") == "1"
    donors_ = find_matches(db, req, exact)
    return page("""
<div class="card"><h3>Request #{{r.request_id}} — {{r.patient_name}} needs <b>{{r.blood_group_needed}}</b></h3>
<p>{{r.hospital_name}} · <span class="tag {{r.urgency_level}}">{{r.urgency_level}}</span> · status: {{r.status}}</p>
<a class="btn" href="?exact=0">Compatible groups</a> <a class="btn" href="?exact=1">Exact group only</a></div>
<div class="card"><table><tr><th>Donor</th><th>Group</th><th>Phone</th><th>City</th><th>Last donation</th><th></th></tr>
{% for d in ds %}<tr><td>{{d.name}}</td><td>{{d.blood_group}}</td><td>{{d.phone}}</td><td>{{d.city}}</td>
<td>{{d.last_donation_date or '—'}}</td>
<td>{% if r.status=='Open' %}<form method="post" action="{{url_for('donate')}}">
<input type="hidden" name="donor_id" value="{{d.donor_id}}"><input type="hidden" name="request_id" value="{{r.request_id}}">
<button>Record donation</button></form>{% endif %}</td></tr>
{% else %}<tr><td colspan="6">No eligible donors found.</td></tr>{% endfor %}</table></div>""", r=req, ds=donors_)


@app.post("/donate")
def donate():
    db = get_db()
    did, rid = int(request.form["donor_id"]), int(request.form["request_id"])
    today = str(date.today())
    db.execute("INSERT INTO Donations(donor_id, request_id, donation_date) VALUES (?,?,?)", (did, rid, today))
    db.execute("UPDATE Donors SET last_donation_date=? WHERE donor_id=?", (today, did))
    db.execute("UPDATE BloodRequests SET status='Fulfilled' WHERE request_id=?", (rid,))
    db.commit()
    return redirect(url_for("donations", msg="Donation recorded, request marked Fulfilled"))


@app.route("/donations")
def donations():
    rows = get_db().execute(
        "SELECT n.*, d.name donor, d.blood_group, r.patient_name, r.hospital_name FROM Donations n "
        "JOIN Donors d USING(donor_id) JOIN BloodRequests r USING(request_id) ORDER BY n.donation_id DESC").fetchall()
    return page("""
<div class="card"><table><tr><th>#</th><th>Donor</th><th>Group</th><th>Patient</th><th>Hospital</th><th>Date</th><th>Status</th></tr>
{% for n in rows %}<tr><td>{{n.donation_id}}</td><td>{{n.donor}}</td><td>{{n.blood_group}}</td><td>{{n.patient_name}}</td>
<td>{{n.hospital_name}}</td><td>{{n.donation_date}}</td><td>{{n.status}}</td></tr>
{% else %}<tr><td colspan="7">No donations yet.</td></tr>{% endfor %}</table></div>""", rows=rows)


# JSON API
@app.route("/api/match/<int:request_id>")
def api_match(request_id):
    db = get_db()
    req = db.execute("SELECT * FROM BloodRequests WHERE request_id=?", (request_id,)).fetchone()
    if not req:
        return jsonify(error="not found"), 404
    ds = find_matches(db, req, request.args.get("exact") == "1")
    return jsonify(request=dict(req), donors=[dict(d) for d in ds])


init_db()  # runs on import too, so gunicorn (Render) creates the DB

if __name__ == "__main__":
    app.run()
