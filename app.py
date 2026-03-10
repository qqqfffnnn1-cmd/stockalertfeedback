import os
import requests
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]

SITE_PASSWORD = os.environ["SITE_PASSWORD"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

sb = create_client(SUPABASE_URL, SUPABASE_KEY)


def require_login(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == SITE_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        error = "密码错误"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/", methods=["GET"])
@require_login
def index():
    return render_template("form.html")


@app.route("/submit", methods=["POST"])
@require_login
def submit():
    data = {
        "username": request.form.get("username", "").strip(),
        "stock_name": request.form.get("stock_name", "").strip(),
        "stock_code": request.form.get("stock_code", "").strip(),
        "feedback_type": request.form.get("feedback_type", "").strip(),
        "time_start": request.form.get("time_start", "").strip(),
        "time_end": request.form.get("time_end", "").strip(),
        "note": request.form.get("note", "").strip(),
    }
    if not all([data["username"], data["stock_name"], data["stock_code"],
                data["feedback_type"], data["time_start"], data["time_end"]]):
        return render_template("form.html", error="请填写所有必填项", prefill=data)
    sb.table("feedback").insert(data).execute()
    return render_template("form.html", success=True)


@app.route("/api/stock-search")
@require_login
def stock_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    try:
        url = "https://suggest3.eastmoney.com/api/suggest/get"
        params = {
            "input": q,
            "type": "14",
            "token": "D43BF722C8E33BDC906FB84D85E326E8",
            "count": "8",
        }
        r = requests.get(url, params=params, timeout=5,
                         headers={"User-Agent": "Mozilla/5.0"})
        items = r.json().get("QuotationCodeTable", {}).get("Data", []) or []
        results = [
            {"name": i["Name"], "code": i["Code"]}
            for i in items
            if i.get("SecurityTypeName") in ("沪A", "深A", "创业板", "科创板")
        ]
        return jsonify(results)
    except Exception:
        return jsonify([])


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin"))
        error = "密码错误"
    return render_template("login.html", error=error, admin_mode=True)


@app.route("/admin")
@require_admin
def admin():
    rows = sb.table("feedback").select("*").order("created_at", desc=True).execute().data
    return render_template("admin.html", rows=rows)


@app.route("/admin/delete/<row_id>", methods=["POST"])
@require_admin
def admin_delete(row_id):
    sb.table("feedback").delete().eq("id", row_id).execute()
    return redirect(url_for("admin"))


if __name__ == "__main__":
    app.run(debug=False)
