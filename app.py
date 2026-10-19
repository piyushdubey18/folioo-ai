import os, re, json, sqlite3, secrets
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse
import requests
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, abort, make_response, session
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()
ROOT = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(ROOT, "portfolios.db")
app = Flask(__name__)
app.config.update(SECRET_KEY=os.getenv("SECRET_KEY") or "local-dev-only-change-me",
    MAX_CONTENT_LENGTH=1048576, SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower()=="true",
    PERMANENT_SESSION_LIFETIME=60*60*24*7)
CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app, default_limits=["120 per hour"], storage_uri="memory://")
TEMPLATES = {
    "midnight": {"name": "Midnight", "description": "Dark, modern developer style", "professions": ["tech", "student", "freelancer"]},
    "minimal": {"name": "Minimal", "description": "Clean, light professional style", "professions": ["student", "business", "educator", "healthcare", "finance", "writer"]},
    "creative": {"name": "Creative", "description": "Colorful, expressive personal brand", "professions": ["creative", "freelancer", "photography", "writer"]},
    "ocean": {"name": "Ocean Blue", "description": "Cool blue tones for tech and data roles", "professions": ["tech", "educator", "healthcare", "freelancer"]},
    "sunset": {"name": "Sunset Glow", "description": "Warm coral and amber accents", "professions": ["creative", "freelancer", "photography"]},
    "forest": {"name": "Forest", "description": "Natural greens and calm layouts", "professions": ["healthcare", "educator", "student"]},
    "editorial": {"name": "Editorial", "description": "Magazine-inspired typography", "professions": ["writer", "business", "photography", "finance"]},
    "terminal": {"name": "Terminal", "description": "Code-inspired, monospace aesthetic", "professions": ["tech"]},
    "brutalist": {"name": "Bold Brutalist", "description": "High contrast, bold shapes", "professions": ["creative", "photography", "tech"]},
    "lavender": {"name": "Lavender", "description": "Soft lilac and airy surfaces", "professions": ["student", "creative", "healthcare"]},
    "mono": {"name": "Monochrome", "description": "Sharp black-and-white portfolio", "professions": ["finance", "business", "writer"]},
    "rose": {"name": "Rose Quartz", "description": "Soft rose and burgundy accents", "professions": ["creative", "photography", "freelancer"]},
}

PROFESSIONS = {
    "tech": "Software, AI & Data", "student": "Student / Graduate", "creative": "Designer / Creative",
    "business": "Business / Marketing / Sales", "freelancer": "Freelancer / Consultant",
    "photography": "Photographer / Artist", "writer": "Writer / Content Creator",
    "educator": "Teacher / Researcher", "healthcare": "Healthcare / Wellness", "finance": "Finance / Legal"
}

def db():
    con=sqlite3.connect(DB_PATH); con.row_factory=sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def init_db():
    with db() as con:
        con.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT UNIQUE NOT NULL COLLATE NOCASE,password_hash TEXT NOT NULL,created_at TEXT NOT NULL)")
        con.execute("CREATE TABLE IF NOT EXISTS portfolios(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,slug TEXT UNIQUE NOT NULL,name TEXT NOT NULL,email TEXT,template TEXT NOT NULL,data_json TEXT NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)")
        cols=[r["name"] for r in con.execute("PRAGMA table_info(portfolios)").fetchall()]
        if "user_id" not in cols: con.execute("ALTER TABLE portfolios ADD COLUMN user_id INTEGER")

def login_required(fn):
    @wraps(fn)
    def wrapped(*args,**kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.","warning")
            return redirect(url_for("login"))
        return fn(*args,**kwargs)
    return wrapped

def current_user():
    if not session.get("user_id"): return None
    with db() as con: return con.execute("SELECT id,email FROM users WHERE id=?",(session["user_id"],)).fetchone()

def clean(v,n=500):
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]","",(v or "").strip())[:n]

def safe_url(v):
    v=clean(v,300); p=urlparse(v)
    return v if p.scheme in ("https","http") and p.netloc else ""

def split_lines(v,n=8):
    return [clean(x,180) for x in (v or "").splitlines() if clean(x,180)][:n]

def fallback(profile):
    skills=profile["skills"] or ["Problem solving","Communication","Continuous learning"]
    projects=[{"title":x,"description":"A project focused on applying practical skills to solve a problem. Add your contribution and results before publishing.","tech":skills[:3],"link":profile["github"]} for x in profile["projects"]]
    if not projects: projects=[{"title":"Add your first project","description":"Describe the problem, your approach, technologies used, and the result. Replace this placeholder before publishing.","tech":skills[:3],"link":profile["github"]}]
    return {"headline":profile["role"]+" | Building useful things and learning every day",
      "summary":profile["name"]+" is a "+profile["role"].lower()+" interested in applying practical skills to meaningful problems.",
      "about":"I am "+profile["name"]+". My background includes "+(profile["education"] or "ongoing learning and practical projects")+". I enjoy learning, building projects, and improving through feedback.",
      "skills":skills,"projects":projects,
      "experience":profile["experience"] or "Add internships, work experience, volunteering, or coursework here.",
      "achievements":profile["achievements"] or "Add verified achievements, certifications, or awards here.","contact":profile["email"]}

def generate_content(profile):
    key=os.getenv("GEMINI_API_KEY","").strip()
    if not key: return fallback(profile),"demo"
    model=os.getenv("GEMINI_MODEL","gemini-2.5-flash").strip()
    endpoint="https://generativelanguage.googleapis.com/v1beta/models/"+model+":generateContent"
    prompt=("Use ONLY the facts supplied. Never invent employers, degrees, dates, metrics, certifications, or achievements. "
      "Return valid JSON only with keys headline, summary, about, skills array, projects array of title/description/tech/link, "
      "experience, achievements, contact. Tailor language and project framing to the selected profession type, without inventing facts. Keep it concise and professional. Facts: "+json.dumps(profile,ensure_ascii=False))
    r=requests.post(endpoint,params={"key":key},json={"contents":[{"parts":[{"text":prompt}]}],
      "generationConfig":{"temperature":0.4,"responseMimeType":"application/json"}},timeout=35)
    r.raise_for_status(); data=json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
    out=fallback(profile)
    for k in ("headline","summary","about","experience","achievements","contact"):
        if isinstance(data.get(k),str) and data[k].strip(): out[k]=clean(data[k],1500)
    if isinstance(data.get("skills"),list): out["skills"]=[clean(str(x),100) for x in data["skills"][:8] if clean(str(x),100)]
    if isinstance(data.get("projects"),list):
        ps=[]
        for x in data["projects"][:8]:
            if isinstance(x,dict): ps.append({"title":clean(str(x.get("title","Project")),100),"description":clean(str(x.get("description","")),600),"tech":[clean(str(t),60) for t in x.get("tech",[])[:6]],"link":safe_url(str(x.get("link","")))})
        if ps: out["projects"]=ps
    return out,"ai"

def new_slug(name):
    stem=re.sub(r"[^a-z0-9]+","-",name.lower()).strip("-")[:36] or "portfolio"
    return stem+"-"+secrets.token_hex(3)

@app.route("/")
def login():
    return redirect(url_for("dashboard")) if session.get("user_id") else render_template("login.html")

@app.route("/register",methods=["GET","POST"])
@limiter.limit("10 per hour")
def register():
    if session.get("user_id"): return redirect(url_for("dashboard"))
    if request.method=="POST":
        email=clean(request.form.get("email"),160).lower()
        password=request.form.get("password",""); confirm=request.form.get("confirm_password","")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",email): flash("Enter a valid email address.","error")
        elif len(password)<10: flash("Password must contain at least 10 characters.","error")
        elif password!=confirm: flash("Passwords do not match.","error")
        else:
            try:
                with db() as con: con.execute("INSERT INTO users(email,password_hash,created_at) VALUES(?,?,?)",(email,generate_password_hash(password),datetime.utcnow().isoformat(timespec="seconds")))
                flash("Account created. Log in to continue.","success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError: flash("An account with this email already exists.","error")
    return render_template("register.html")

@app.route("/login",methods=["POST"])
@limiter.limit("10 per minute")
def do_login():
    email=clean(request.form.get("email"),160).lower()
    with db() as con: user=con.execute("SELECT id,email,password_hash FROM users WHERE email=?",(email,)).fetchone()
    if not user or not check_password_hash(user["password_hash"],request.form.get("password","")):
        flash("Email or password is incorrect.","error"); return redirect(url_for("login"))
    session.clear(); session["user_id"]=user["id"]; session.permanent=True
    return redirect(url_for("dashboard"))

@app.route("/logout",methods=["POST"])
@login_required
def logout():
    session.clear(); flash("You have been logged out.","success")
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    user=current_user()
    with db() as con: rows=con.execute("SELECT slug,name,template,created_at FROM portfolios WHERE user_id=? ORDER BY id DESC",(user["id"],)).fetchall()
    return render_template("dashboard.html",user=user,portfolios=rows,templates=TEMPLATES)

@app.route("/create")
@login_required
def create():
    return render_template("index.html",templates=TEMPLATES,professions=PROFESSIONS,user=current_user())

@app.route("/generate",methods=["POST"])
@login_required
@limiter.limit("8 per hour")
def generate():
    p={"name":clean(request.form.get("name"),80),"role":clean(request.form.get("role"),100),"email":clean(request.form.get("email"),120),
       "education":clean(request.form.get("education"),250),"skills":split_lines(request.form.get("skills")),"projects":split_lines(request.form.get("projects")),
       "experience":clean(request.form.get("experience"),700),"achievements":clean(request.form.get("achievements"),500),
       "github":safe_url(request.form.get("github")),"linkedin":safe_url(request.form.get("linkedin")),"website":safe_url(request.form.get("website")),
       "template":clean(request.form.get("template"),20),"profession_type":clean(request.form.get("profession_type"),30)}
    if not p["name"] or not p["role"]: flash("Name and target role are required.","error"); return redirect(url_for("create"))
    if p["profession_type"] not in PROFESSIONS: p["profession_type"]="tech"
    if p["template"] not in TEMPLATES: p["template"]="midnight"
    try: content,mode=generate_content(p)
    except (requests.RequestException,KeyError,ValueError,json.JSONDecodeError) as exc:
        app.logger.warning("AI generation failed: %s",type(exc).__name__)
        content,mode=fallback(p),"demo"; flash("AI service unavailable; demo content was used. Check API configuration.","warning")
    slug=new_slug(p["name"]); user=current_user()
    with db() as con:
        con.execute("INSERT INTO portfolios(user_id,slug,name,email,template,data_json,created_at) VALUES(?,?,?,?,?,?,?)",
          (user["id"],slug,p["name"],p["email"],p["template"],json.dumps({"profile":p,"content":content,"mode":mode},ensure_ascii=False),datetime.utcnow().isoformat(timespec="seconds")))
    return redirect(url_for("preview",slug=slug))

def owned(slug):
    with db() as con: row=con.execute("SELECT * FROM portfolios WHERE slug=? AND user_id=?",(slug,session["user_id"])).fetchone()
    if row is None: abort(404)
    return row

@app.route("/p/<slug>")
@login_required
def preview(slug):
    row=owned(slug)
    return render_template("portfolio.html",portfolio=json.loads(row["data_json"]),slug=slug,templates=TEMPLATES,user=current_user())


@app.route("/p/<slug>/edit", methods=["GET", "POST"])
@login_required
def edit_portfolio(slug):
    row = owned(slug)
    portfolio = json.loads(row["data_json"])
    if request.method == "POST":
        profile = portfolio["profile"]
        profile.update({
            "name": clean(request.form.get("name"), 80),
            "role": clean(request.form.get("role"), 100),
            "email": clean(request.form.get("email"), 120),
            "education": clean(request.form.get("education"), 250),
            "skills": split_lines(request.form.get("skills")),
            "experience": clean(request.form.get("experience"), 700),
            "achievements": clean(request.form.get("achievements"), 500),
            "github": safe_url(request.form.get("github")),
            "linkedin": safe_url(request.form.get("linkedin")),
            "website": safe_url(request.form.get("website")),
            "template": clean(request.form.get("template"), 20),
            "profession_type": clean(request.form.get("profession_type"), 30),
        })
        if not profile["name"] or not profile["role"]:
            flash("Name and target role are required.", "error")
            return redirect(url_for("edit_portfolio", slug=slug))
        if profile.get("profession_type") not in PROFESSIONS:
            profile["profession_type"] = "tech"
        if profile["template"] not in TEMPLATES:
            profile["template"] = "midnight"

        content = portfolio["content"]
        content["headline"] = clean(request.form.get("headline"), 300)
        content["summary"] = clean(request.form.get("summary"), 1000)
        content["about"] = clean(request.form.get("about"), 2000)
        content["skills"] = profile["skills"]
        content["experience"] = profile["experience"]
        content["achievements"] = profile["achievements"]
        content["contact"] = profile["email"]

        titles = request.form.getlist("project_title")
        descriptions = request.form.getlist("project_description")
        links = request.form.getlist("project_link")
        techs = request.form.getlist("project_tech")
        projects = []
        for i, title in enumerate(titles[:8]):
            title = clean(title, 100)
            description = clean(descriptions[i] if i < len(descriptions) else "", 600)
            link = safe_url(links[i] if i < len(links) else "")
            tech = [clean(t, 60) for t in (techs[i] if i < len(techs) else "").split(",") if clean(t, 60)][:6]
            if title:
                projects.append({"title": title, "description": description, "link": link, "tech": tech})
        content["projects"] = projects

        with db() as con:
            con.execute("UPDATE portfolios SET name=?, email=?, template=?, data_json=? WHERE slug=? AND user_id=?",
                (profile["name"], profile["email"], profile["template"],
                 json.dumps(portfolio, ensure_ascii=False), slug, session["user_id"]))
        if request.form.get("action") == "draft":
            flash("Draft saved. You can continue editing whenever you want.", "success")
            return redirect(url_for("edit_portfolio", slug=slug))
        flash("Portfolio changes saved.", "success")
        return redirect(url_for("preview", slug=slug))
    return render_template("edit.html", portfolio=portfolio, slug=slug, templates=TEMPLATES, professions=PROFESSIONS)

@app.route("/p/<slug>/download")
@login_required
def download(slug):
    row=owned(slug); html=render_template("export.html",portfolio=json.loads(row["data_json"]),templates=TEMPLATES)
    response=make_response(html); response.headers["Content-Type"]="text/html; charset=utf-8"
    response.headers["Content-Disposition"]='attachment; filename="'+row["slug"]+'.html"'
    return response

@app.errorhandler(404)
def not_found(_e): return render_template("404.html"),404

@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"]="nosniff"; response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"]="no-store"
    return response

init_db()
if __name__=="__main__": app.run(debug=os.getenv("FLASK_DEBUG","false").lower()=="true")
