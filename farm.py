from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
import requests
import json
import feedparser
import hashlib
import os
import threading
import time
import re
import random
import html
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = 's#8d7f9g3h5j2k1l4m6n0p7q9r2t5w8y'  # غيّرها بأي مفتاح عشوائي طويل

# ================================================================
# 🔐 إعدادات الأمان والجلسات
# ================================================================

app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# ================================================================
# 🛡️ Talisman (حماية الرؤوس)
# ================================================================

csp = {
    'default-src': [
        "'self'",
        'https://cdnjs.cloudflare.com',
        'https://fonts.googleapis.com',
        'https://fonts.gstatic.com',
        'https://image.pollinations.ai',
        'https://text.pollinations.ai',
        'https://www.google.com',
        'https://*.googleapis.com',
        'https://*.gstatic.com'
    ],
    'script-src': ["'self'", "'unsafe-inline'", 'https://cdnjs.cloudflare.com'],
    'style-src': ["'self'", "'unsafe-inline'", 'https://fonts.googleapis.com', 'https://cdnjs.cloudflare.com'],
    'img-src': ["'self'", 'data:', 'https://image.pollinations.ai', 'https://via.placeholder.com'],
    'font-src': ["'self'", 'https://fonts.gstatic.com', 'https://cdnjs.cloudflare.com']
}

Talisman(app, content_security_policy=csp, force_https=False)

# ================================================================
# 🚦 Limiter (تقييد الطلبات)
# ================================================================

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# ================================================================
# ⚙️ الإعدادات العامة
# ================================================================

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "k7#9mX2!qL5@vP8"  # غيّرها لكلمة قوية!
PUBLISH_TIMES = ["08:00", "14:00"]
CLEANUP_DAYS = 30

# ================================================================
# 📚 قائمة المواضيع الحصرية (متنوعة)
# ================================================================

TOPICS = [
    {"title": "أنظمة التيار الخفيف في المباني الذكية", "style": "تقريري"},
    {"title": "كيف تختار كاميرات المراقبة المناسبة لمشروعك؟", "style": "دليل إرشادي"},
    {"title": "أحدث تقنيات أنظمة الإنذار والحماية", "style": "تقني"},
    {"title": "فوائد أنظمة BMS في توفير الطاقة", "style": "اقتصادي"},
    {"title": "شبكات الألياف البصرية: المستقبل الآن", "style": "تسويقي"},
    {"title": "الصيانة الدورية للأنظمة الكهربائية: لماذا هي ضرورية؟", "style": "نصائح عملية"},
    {"title": "أنظمة التحكم الآلي في الإضاءة", "style": "تطبيقي"},
    {"title": "كيف تؤثر جودة الكابلات على أداء الشبكات", "style": "تقني"},
    {"title": "أمن المباني: دمج الكاميرات مع أنظمة الإنذار", "style": "أمني"},
    {"title": "حلول الطاقة المتجددة في المشاريع الكهربائية", "style": "بيئي"},
    {"title": "تركيب شبكات الحاسب: أفضل الممارسات", "style": "إرشادي"},
    {"title": "أنظمة الصوتيات في المنشآت التجارية", "style": "تطبيقي"},
]

used_topics = []

# ================================================================
# إنشاء المجلدات
# ================================================================

for folder in ["data", "static"]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# ================================================================
# دوال الذكاء الاصطناعي
# ================================================================

def local_ai_request(prompt, system_msg="أنت مساعد خبير"):
    system_msg = """أنت المهندس/المستشار الأول في شركة ركاز للمقاولات الكهربائية والتيار الخفيف.  
    أنت خبير في جميع مجالات الشركة: الكهرباء العامة، أنظمة التيار الخفيف، كاميرات المراقبة، شبكات الحاسب، أنظمة الإنذار، BMS، والصيانة.  
    
    **تعليماتك:**  
    1. إذا كان السؤال عن خدمات الشركة أو مجال الكهرباء والتيار الخفيف: أجب بإسهاب وبأسلوب احترافي، واذكر إنجازات الشركة وخبراتها.  
    2. إذا كان السؤال عن أي موضوع آخر: أجب بأدب وبمعلومات مفيدة.  
    3. دائماً قدم نفسك كجزء من فريق ركاز.  
    4. لا تذكر أي شركات منافسة، ولا تذكر أنك نموذج ذكاء اصطناعي.  
    """

    # 1. محاولة النموذج المحلي (Ollama)
    try:
        payload = {"model": "deepseek-r1:7b", "prompt": f"{system_msg}\n\nسؤال العميل: {prompt}\n\nالرد:", "stream": False}
        resp = requests.post("http://localhost:11434/api/generate", json=payload, timeout=30)
        if resp.status_code == 200:
            return resp.json()['response']
    except Exception as e:
        print(f"⚠️ فشل النموذج المحلي: {e}")

    # 2. الاحتياطي: Pollinations.ai
    try:
        url = f"https://text.pollinations.ai/{system_msg[:100]}. السؤال: {prompt}"
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            return resp.text
    except Exception as e:
        print(f"⚠️ فشل Pollinations: {e}")

    return "⚠️ عذراً، خدمة الذكاء الاصطناعي غير متاحة حالياً."

def format_markdown(text):
    if not text:
        return ""
    text = html.escape(text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'^### (.*?)$', r'<h4>\1</h4>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.*?)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.*?)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^\- (.*?)$', r'<li>\1</li>', text, flags=re.MULTILINE)
    text = re.sub(r'^• (.*?)$', r'<li>\1</li>', text, flags=re.MULTILINE)
    text = re.sub(r'(<li>.*?</li>\s*)+', r'<ul>\g<0></ul>', text, flags=re.DOTALL)
    text = text.replace('\n', '<br>')
    return text

# ================================================================
# إدارة البيانات
# ================================================================

def load_data(filename):
    try:
        with open(f"data/{filename}.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_data(filename, data):
    with open(f"data/{filename}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_settings():
    try:
        with open("data/settings.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {
            "company_name": "ركاز",
            "company_slogan": "للتيار الخفيف",
            "phone": "+20 100 888 7777",
            "email": "info@rekaz.com",
            "address": "مصر - القاهرة - مدينة نصر",
            "hero_title": "حلول كهربائية متكاملة",
            "hero_subtitle": "شركة ركاز للمقاولات الكهربائية والتيار الخفيف – جودة واحترافية منذ 2010.",
            "publish_times": ["08:00", "14:00"],
            "cleanup_days": 30,
        }

def save_settings(settings):
    global PUBLISH_TIMES, CLEANUP_DAYS
    PUBLISH_TIMES = settings.get("publish_times", ["08:00", "14:00"])
    CLEANUP_DAYS = settings.get("cleanup_days", 30)
    save_data("settings", settings)

def sanitize_input(text):
    return html.escape(str(text).strip())

# ================================================================
# دالة التحقق من تسجيل الدخول
# ================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ================================================================
# وظائف الأتمتة
# ================================================================

def generate_article():
    global used_topics
    available = [t for t in TOPICS if t["title"] not in used_topics[-5:]]
    if not available:
        available = TOPICS
    selected = random.choice(available)
    used_topics.append(selected["title"])
    if len(used_topics) > 20:
        used_topics.pop(0)
    
    topic = selected["title"]
    style = selected["style"]
    
    style_instructions = {
        "تقريري": "اكتب مقالاً تقريرياً مفصلاً.",
        "دليل إرشادي": "اكتب دليلاً إرشادياً خطوة بخطوة.",
        "تقني": "اكتب مقالاً تقنياً متخصصاً.",
        "اقتصادي": "اكتب مقالاً يركز على الجوانب الاقتصادية.",
        "تسويقي": "اكتب مقالاً تسويقياً مقنعاً.",
        "نصائح عملية": "اكتب مقالاً يقدم نصائح عملية.",
        "تطبيقي": "اكتب مقالاً تطبيقياً مع أمثلة.",
        "أمني": "اكتب مقالاً يركز على الأمن.",
        "بيئي": "اكتب مقالاً يركز على الاستدامة.",
        "إرشادي": "اكتب مقالاً إرشادياً للمبتدئين."
    }
    
    instruction = style_instructions.get(style, "اكتب مقالاً احترافياً.")
    prompt = f"اكتب مقالة حصرية عن: {topic}. الأسلوب: {instruction}. الطول: 300-400 كلمة."
    article = local_ai_request(prompt)
    return article, topic

def generate_image(topic):
    prompt = f"professional electrical contracting company, {topic}, modern technology, high quality, 4k"
    return f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?width=800&height=400&nologo=true"

def download_image(url):
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200 and 'image' in resp.headers.get('content-type', ''):
            return resp.content
    except:
        pass
    return None

def fetch_tenders():
    results = []
    feeds = [
        "https://www.arabtender.com/feed/rss",
        "https://www.tenderegypt.com/feed",
        "https://www.tendersinfo.com/rss/",
    ]
    keywords = ["كهرباء", "تيار خفيف", "مقاولات", "كابلات", "إنارة", "لوحات", "كاميرات", "شبكات"]
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                link = entry.get('link', '')
                if any(kw in (title + summary).lower() for kw in keywords):
                    if not any(t.get('link') == link for t in results):
                        results.append({'title': title, 'link': link, 'summary': summary[:200], 'date': entry.get('published', '')})
        except:
            continue
    return results

def auto_publish():
    print("📝 جاري نشر مقال جديد...")
    article, topic = generate_article()
    if not article or "خطأ" in article:
        print("❌ فشل توليد المقال")
        return
    title = f"{topic} - مقالة حصرية من شركة ركاز"
    img_url = generate_image(topic)
    img_data = download_image(img_url)
    posts = load_data("posts")
    posts.append({"title": title, "content": article, "image": img_url, "topic": topic, "date": str(datetime.now())})
    save_data("posts", posts)
    if img_data:
        filename = f"static/post_{hashlib.md5(title.encode()).hexdigest()[:8]}.jpg"
        with open(filename, "wb") as f:
            f.write(img_data)
        print("🖼️ تم حفظ الصورة")
    logs = load_data("logs")
    logs.append({"action": "publish", "title": title, "time": str(datetime.now())})
    save_data("logs", logs)
    print(f"✅ تم نشر: {title}")

def auto_tenders():
    print("🔍 جاري البحث عن مناقصات...")
    tenders = fetch_tenders()
    if not tenders:
        return
    old = load_data("tenders")
    new_tenders = [t for t in tenders if t not in old]
    if new_tenders:
        save_data("tenders", old + new_tenders)
        print(f"✅ تم العثور على {len(new_tenders)} مناقصة جديدة")

def auto_cleanup():
    print("🧹 جاري التنظيف...")
    cutoff = datetime.now() - timedelta(days=CLEANUP_DAYS)
    posts = load_data("posts")
    new_posts = [p for p in posts if datetime.strptime(p['date'], "%Y-%m-%d %H:%M:%S") > cutoff]
    if len(new_posts) != len(posts):
        save_data("posts", new_posts)
    if os.path.exists("static"):
        for f in os.listdir("static"):
            if f.startswith("post_") and f.endswith(".jpg"):
                if datetime.fromtimestamp(os.path.getmtime(os.path.join("static", f))) < cutoff:
                    os.remove(os.path.join("static", f))

def auto_backup():
    print("💾 جاري النسخ الاحتياطي...")
    for f in ["posts", "tenders", "messages", "settings", "logs"]:
        data = load_data(f)
        with open(f"data/backup_{f}_{datetime.now().strftime('%Y%m%d_%H%M')}.json", "w", encoding="utf-8") as bk:
            json.dump(data, bk, ensure_ascii=False, indent=2)
    for f in sorted([f for f in os.listdir("data") if f.startswith("backup_")])[:-20]:
        os.remove(os.path.join("data", f))

def scheduler_loop():
    auto_publish()
    auto_tenders()
    auto_cleanup()
    auto_backup()
    while True:
        now = datetime.now()
        if now.strftime("%H:%M") in PUBLISH_TIMES:
            auto_publish()
            time.sleep(60)
        if now.minute % 45 == 0:
            auto_tenders()
            time.sleep(60)
        if now.hour == 3 and now.minute == 0:
            auto_cleanup()
            time.sleep(60)
        if now.hour % 6 == 0 and now.minute == 0:
            auto_backup()
            time.sleep(60)
        time.sleep(30)

# ================================================================
# مسارات الموقع
# ================================================================

@app.route('/')
def index():
    settings = load_settings()
    posts = load_data("posts")
    return render_template_string(HTML_MASTER, settings=settings, posts=posts[::-1])

@app.route('/ask', methods=['POST'])
@limiter.limit("5 per minute")
def ask():
    data = request.get_json()
    user_msg = sanitize_input(data.get('message', ''))
    if not user_msg:
        return jsonify({"reply": "اكتب سؤالك أولاً"})
    reply = local_ai_request(user_msg)
    chats = load_data("chats")
    chats.append({"question": user_msg, "answer": reply[:100], "time": str(datetime.now())})
    save_data("chats", chats[-100:])
    return jsonify({"reply": format_markdown(reply), "time": round(time.time(), 2)})

@app.route('/contact', methods=['POST'])
def contact():
    data = request.get_json()
    msgs = load_data("messages")
    msgs.append({
        "name": sanitize_input(data.get('name', '')),
        "email": sanitize_input(data.get('email', '')),
        "phone": sanitize_input(data.get('phone', '')),
        "msg": sanitize_input(data.get('msg', '')),
        "time": str(datetime.now())
    })
    save_data("messages", msgs)
    return jsonify({"status": "ok"})

# ================================================================
# لوحة التحكم
# ================================================================

@app.route('/admin/login', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def admin_login():
    if request.method == 'POST':
        username = sanitize_input(request.form.get('username'))
        password = sanitize_input(request.form.get('password'))
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        return render_template_string(ADMIN_LOGIN_HTML, error="❌ اسم المستخدم أو كلمة المرور غير صحيحة")
    return render_template_string(ADMIN_LOGIN_HTML, error=None)

@app.route('/admin/logout')
def admin_logout():
    session.pop('logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin')
@login_required
def admin_dashboard():
    return render_template_string(ADMIN_DASHBOARD_HTML,
                                   posts=load_data("posts"),
                                   tenders=load_data("tenders"),
                                   msgs=load_data("messages"),
                                   chats=load_data("chats"),
                                   logs=load_data("logs"))

@app.route('/admin/posts')
@login_required
def admin_posts():
    return render_template_string(ADMIN_POSTS_HTML, posts=load_data("posts"))

@app.route('/admin/posts/delete/<int:index>')
@login_required
def admin_delete_post(index):
    posts = load_data("posts")
    if 0 <= index < len(posts):
        posts.pop(index)
        save_data("posts", posts)
    return redirect(url_for('admin_posts'))

@app.route('/admin/posts/add', methods=['POST'])
@login_required
def admin_add_post():
    title = sanitize_input(request.form.get('title'))
    content = sanitize_input(request.form.get('content'))
    if title and content:
        posts = load_data("posts")
        posts.append({"title": title, "content": content, "date": str(datetime.now())})
        save_data("posts", posts)
    return redirect(url_for('admin_posts'))

@app.route('/admin/publish_now')
@login_required
def admin_publish_now():
    auto_publish()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/fetch_tenders_now')
@login_required
def admin_fetch_tenders_now():
    auto_tenders()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/tenders')
@login_required
def admin_tenders():
    return render_template_string(ADMIN_TENDERS_HTML, tenders=load_data("tenders"))

@app.route('/admin/messages')
@login_required
def admin_messages():
    return render_template_string(ADMIN_MESSAGES_HTML, msgs=load_data("messages"))

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    if request.method == 'POST':
        settings = {
            "company_name": sanitize_input(request.form.get('company_name')),
            "company_slogan": sanitize_input(request.form.get('company_slogan')),
            "phone": sanitize_input(request.form.get('phone')),
            "email": sanitize_input(request.form.get('email')),
            "address": sanitize_input(request.form.get('address')),
            "hero_title": sanitize_input(request.form.get('hero_title')),
            "hero_subtitle": sanitize_input(request.form.get('hero_subtitle')),
            "publish_times": [t.strip() for t in request.form.get('publish_times').split(',')],
            "cleanup_days": int(request.form.get('cleanup_days', 30)),
        }
        save_settings(settings)
        return redirect(url_for('admin_settings'))
    return render_template_string(ADMIN_SETTINGS_HTML, settings=load_settings())

@app.route('/admin/system')
@login_required
def admin_system():
    return render_template_string(ADMIN_SYSTEM_HTML,
                                   posts_count=len(load_data("posts")),
                                   tenders_count=len(load_data("tenders")),
                                   msgs_count=len(load_data("messages")),
                                   chats_count=len(load_data("chats")),
                                   logs_count=len(load_data("logs")),
                                   now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# ================================================================
# واجهات HTML (يتبع)
# ================================================================

HTML_MASTER = """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ settings.company_name }} - {{ settings.company_slogan }}</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:'Segoe UI',Tahoma,Arial,sans-serif}
body{background:#0a0e1a;color:#e8edf5;transition:0.3s;line-height:1.6}
.container{max-width:1200px;margin:auto;padding:0 25px}
header{background:rgba(10,14,26,0.9);backdrop-filter:blur(12px);border-bottom:2px solid #f5b81b;padding:12px 0;position:sticky;top:0;z-index:100}
.flex-header{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap}
.logo{font-size:30px;font-weight:800;background:linear-gradient(135deg,#f5b81b,#ff8c00);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.logo i{-webkit-text-fill-color:#f5b81b;margin-left:8px}
.logo span{-webkit-text-fill-color:#e8edf5}
nav a{color:#aab;margin:0 12px;font-weight:500;transition:0.3s;font-size:15px;border-bottom:2px solid transparent;padding-bottom:3px;text-decoration:none}
nav a:hover{color:#f5b81b;border-bottom-color:#f5b81b}
.theme-toggle{background:#f5b81b;border:none;padding:6px 14px;border-radius:30px;cursor:pointer;font-weight:bold;color:#000}
.hero{background:linear-gradient(135deg,#0a0e1a 0%,#162044 50%,#0a1a3a 100%);padding:80px 0 60px;border-bottom:1px solid rgba(245,184,27,0.2);position:relative;overflow:hidden}
.hero-grid{display:grid;grid-template-columns:1fr 1fr;gap:50px;align-items:center}
.hero h1{font-size:48px;font-weight:800;line-height:1.2}
.hero h1 span{color:#f5b81b}
.hero p{font-size:18px;opacity:0.85;margin:20px 0;max-width:500px}
.hero-badge{display:inline-block;background:rgba(245,184,27,0.15);border:1px solid #f5b81b;padding:8px 20px;border-radius:50px;font-size:14px;color:#f5b81b;margin-bottom:15px}
.btn{display:inline-block;background:#f5b81b;color:#000;padding:14px 40px;border-radius:50px;font-weight:700;border:none;cursor:pointer;transition:0.3s;font-size:16px;text-decoration:none}
.btn:hover{transform:scale(1.05);box-shadow:0 10px 30px rgba(245,184,27,0.3)}
.btn-outline{background:transparent;border:2px solid #f5b81b;color:#f5b81b;margin-right:15px}
.btn-outline:hover{background:#f5b81b;color:#000}
.hero-stats{display:flex;gap:40px;margin-top:30px}
.hero-stats div h3{font-size:32px;color:#f5b81b}
.hero-stats div p{font-size:14px;opacity:0.6;margin:0}
.hero-image{background:rgba(255,255,255,0.03);border-radius:16px;padding:30px;border:1px solid rgba(255,255,255,0.05);text-align:center;backdrop-filter:blur(5px)}
.hero-image i{font-size:100px;color:#f5b81b;opacity:0.8}
.hero-image h3{margin:15px 0;font-size:24px}
.hero-image .tags span{display:inline-block;background:rgba(245,184,27,0.1);padding:5px 15px;border-radius:30px;font-size:13px;border:1px solid rgba(245,184,27,0.2);margin:5px}
section{padding:70px 0}
.section-title{font-size:36px;font-weight:800;text-align:center;margin-bottom:15px}
.section-title span{color:#f5b81b}
.section-sub{text-align:center;opacity:0.7;max-width:600px;margin:0 auto 50px;font-size:17px}
.services-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:30px}
.service-card{background:#111833;padding:30px 25px;border-radius:16px;border-bottom:4px solid #f5b81b;transition:0.4s;text-align:center;border:1px solid rgba(255,255,255,0.03)}
.service-card:hover{transform:translateY(-12px);box-shadow:0 15px 40px rgba(0,0,0,0.4);border-color:#1a73e8}
.service-card i{font-size:45px;color:#f5b81b;margin-bottom:15px}
.service-card h3{font-size:20px;margin-bottom:8px;color:#fff}
.service-card p{opacity:0.7;font-size:15px}
.stats-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:20px;background:#111833;padding:40px;border-radius:16px;border:1px solid rgba(255,255,255,0.05)}
.stat-item{text-align:center}
.stat-item h2{font-size:40px;color:#f5b81b;font-weight:800}
.stat-item p{opacity:0.6;font-size:15px}
.projects-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:30px}
.project-card{background:#111833;border-radius:16px;overflow:hidden;border:1px solid rgba(255,255,255,0.05);transition:0.4s}
.project-card:hover{transform:scale(1.02);border-color:#f5b81b}
.project-card img{width:100%;height:200px;object-fit:cover;background:linear-gradient(135deg,#1a2a4a,#0a1a2a)}
.project-card .info{padding:20px}
.project-card .info h4{color:#f5b81b;margin-bottom:5px}
.clients-grid{display:flex;flex-wrap:wrap;justify-content:center;gap:40px;padding:20px;background:#111833;border-radius:16px;border:1px solid rgba(255,255,255,0.05)}
.clients-grid span{font-size:22px;font-weight:700;opacity:0.4;transition:0.3s;filter:grayscale(1)}
.clients-grid span:hover{opacity:1;filter:grayscale(0);color:#f5b81b}
.quality-badge{display:flex;justify-content:center;gap:50px;flex-wrap:wrap;background:linear-gradient(135deg,rgba(245,184,27,0.05),rgba(26,115,232,0.05));padding:30px;border-radius:16px;border:1px solid rgba(245,184,27,0.1)}
.quality-badge div{text-align:center}
.quality-badge i{font-size:40px;color:#f5b81b}
.contact-wrap{display:grid;grid-template-columns:1fr 1fr;gap:40px;background:#111833;padding:40px;border-radius:16px;border:1px solid rgba(255,255,255,0.05)}
.contact-form input,.contact-form textarea{width:100%;padding:14px;margin:10px 0;border-radius:12px;border:1px solid #2a3a5a;background:#0a0e1a;color:#fff;font-size:15px}
.contact-form input:focus,.contact-form textarea:focus{outline:none;border-color:#f5b81b}
.contact-info i{color:#f5b81b;margin-left:15px;width:25px}
.contact-info .item{margin:15px 0;display:flex;align-items:center}
footer{border-top:1px solid rgba(255,255,255,0.05);padding:30px 0;text-align:center;opacity:0.6;font-size:14px}
footer .socials a{color:#f5b81b;margin:0 12px;font-size:24px;transition:0.3s;display:inline-block}
footer .socials a:hover{transform:translateY(-5px)}
.chat-btn{position:fixed;bottom:30px;right:30px;background:#f5b81b;color:#000;border:none;width:65px;height:65px;border-radius:50%;font-size:28px;cursor:pointer;box-shadow:0 10px 30px rgba(0,0,0,0.5);z-index:999;transition:0.3s}
.chat-btn:hover{transform:scale(1.1)}
.chat-window{position:fixed;bottom:110px;right:30px;width:380px;max-width:90vw;background:#111833;border-radius:20px;border:1px solid #f5b81b;display:none;flex-direction:column;z-index:998;max-height:500px;box-shadow:0 15px 40px rgba(0,0,0,0.4)}
.chat-window.active{display:flex}
.chat-header{background:#f5b81b;color:#000;padding:15px;border-radius:20px 20px 0 0;font-weight:bold;display:flex;justify-content:space-between}
.chat-body{height:300px;overflow-y:auto;padding:15px;background:#0a0e1a;display:flex;flex-direction:column}
.chat-msg{padding:10px 16px;border-radius:16px;margin-bottom:10px;max-width:85%;font-size:14px;word-wrap:break-word}
.chat-msg.user{background:#f5b81b;color:#000;align-self:flex-end}
.chat-msg.bot{background:#1a2a4a;color:#fff;align-self:flex-start}
.chat-msg.bot h2,.chat-msg.bot h3,.chat-msg.bot h4{color:#f5b81b;margin:5px 0}
.chat-msg.bot ul{margin:5px 0;padding-right:20px}
.chat-msg.bot li{margin:3px 0}
.chat-footer{display:flex;padding:10px;background:#0a0e1a;border-top:1px solid #2a3a5a;border-radius:0 0 20px 20px}
.chat-footer input{flex:1;padding:12px;border-radius:30px;border:none;background:#1a2a4a;color:#fff;outline:none}
.chat-footer button{background:#f5b81b;color:#000;border:none;padding:12px 22px;border-radius:30px;cursor:pointer;font-weight:bold}
@media(max-width:992px){.hero-grid{grid-template-columns:1fr;text-align:center}.hero p{margin:20px auto}.hero-stats{justify-content:center}.contact-wrap{grid-template-columns:1fr}}
@media(max-width:768px){.hero h1{font-size:30px}.stats-grid{grid-template-columns:1fr 1fr;padding:20px}nav a{margin:0 8px;font-size:13px}.section-title{font-size:28px}.chat-window{width:95%;right:2.5%}}
</style>
</head>
<body>
<header>
<div class="container flex-header">
<div class="logo"><i class="fas fa-bolt"></i> {{ settings.company_name }} <span>{{ settings.company_slogan }}</span></div>
<nav>
<a href="#home">الرئيسية</a>
<a href="#services">الخدمات</a>
<a href="#latest-articles">المقالات</a>
<a href="#about">عن الشركة</a>
<a href="#contact">اتصل بنا</a>
</nav>
</div>
</header>
<section id="home" class="hero"><div class="container hero-grid"><div><div class="hero-badge"><i class="fas fa-shield-alt"></i> معتمد ISO 9001</div><h1>{{ settings.hero_title }} <span>ذكية</span> للمستقبل</h1><p>{{ settings.hero_subtitle }}</p><div><a href="#contact" class="btn"><i class="fas fa-phone-alt"></i> اطلب عرض سعر</a><a href="#services" class="btn btn-outline">اكتشف خدماتنا</a></div><div class="hero-stats"><div><h3 id="stat1">0</h3><p>مشروع منفذ</p></div><div><h3 id="stat2">0</h3><p>عميل سعيد</p></div><div><h3 id="stat3">0</h3><p>سنوات خبرة</p></div></div></div><div class="hero-image"><i class="fas fa-microchip"></i><h3>أنظمة التيار الخفيف</h3><p>شبكات • كاميرات • إنذار • BMS</p><div class="tags"><span>⚡ كهرباء</span><span>📡 تيار خفيف</span><span>🔒 أمن</span></div></div></div></section>
<section id="services" style="background:rgba(255,255,255,0.02);"><div class="container"><h2 class="section-title">خدماتنا <span>المتخصصة</span></h2><p class="section-sub">نقدم حلولاً هندسية متكاملة في مجال الكهرباء والتيار الخفيف</p><div class="services-grid"><div class="service-card"><i class="fas fa-bolt"></i><h3>كهرباء عامة</h3><p>لوحات توزيع، كابلات، إنارة، ومفاتيح تحكم للمشاريع الكبرى.</p></div><div class="service-card"><i class="fas fa-network-wired"></i><h3>شبكات التيار الخفيف</h3><p>شبكات الحاسب، الهواتف، الألياف الضوئية، وشبكات الصوت.</p></div><div class="service-card"><i class="fas fa-video"></i><h3>كاميرات المراقبة IP</h3><p>أنظمة مراقبة عالية الدقة مع تسجيل وسحابة تخزين.</p></div><div class="service-card"><i class="fas fa-fire-extinguisher"></i><h3>أنظمة الإنذار</h3><p>إنذار حريق، سرقة، وأنظمة أمنية متكاملة 24/7.</p></div><div class="service-card"><i class="fas fa-microchip"></i><h3>أنظمة BMS الذكية</h3><p>التحكم الآلي في المباني (إضاءة، تكييف، طاقة) لتوفير الاستهلاك.</p></div><div class="service-card"><i class="fas fa-satellite-dish"></i><h3>حلول الاتصالات</h3><p>تركيب أبراج، هوائيات، وأنظمة اتصال داخلية.</p></div></div></div></section>
<section id="latest-articles" style="background:rgba(255,255,255,0.02);">
    <div class="container">
        <h2 class="section-title">أحدث <span>المقالات</span></h2>
        <p class="section-sub">مقالات حصرية من خبراء شركة ركاز</p>
        <div class="projects-grid">
            {% if posts %}
                {% for post in posts[:6] %}
                <div class="project-card">
                    <img src="{{ post.image }}" alt="{{ post.title }}" style="width:100%; height:200px; object-fit:cover;">
                    <div class="info">
                        <h4>{{ post.title[:50] }}{% if post.title|length > 50 %}...{% endif %}</h4>
                        <p style="opacity:0.8; font-size:14px;">{{ post.content[:100] }}{% if post.content|length > 100 %}...{% endif %}</p>
                        <small style="opacity:0.5; display:block; margin-top:5px;">{{ post.date }}</small>
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <p style="text-align:center; color:#aaa; grid-column: 1 / -1;">لا توجد مقالات منشورة حتى الآن.</p>
            {% endif %}
        </div>
    </div>
</section>
<section><div class="container stats-grid"><div class="stat-item"><h2 id="stat4">127</h2><p>مشروع منفذ</p></div><div class="stat-item"><h2 id="stat5">95</h2><p>عميل سعيد</p></div><div class="stat-item"><h2 id="stat6">15</h2><p>سنوات خبرة</p></div><div class="stat-item"><h2 id="stat7">4.9</h2><p>⭐ تقييم العملاء</p></div></div></section>
<section><div class="container"><h2 class="section-title">عملاؤنا <span>الكبار</span></h2><div class="clients-grid"><span>🏢 شركة العمران</span><span>🏗️ المقاولون العرب</span><span>📡 اتصالات مصر</span><span>🏨 مجموعة فنادق النيل</span><span>⚡ هيئة الطاقة</span></div></div></section>
<section style="background:rgba(255,255,255,0.02);"><div class="container quality-badge"><div><i class="fas fa-shield-halved"></i><h4>ضمان سنة</h4></div><div><i class="fas fa-trophy"></i><h4>معتمد ISO</h4></div><div><i class="fas fa-headset"></i><h4>دعم 24/7</h4></div><div><i class="fas fa-clock"></i><h4>تنفيذ في الوقت المحدد</h4></div></div></section>
<section id="about"><div class="container" style="background:#111833;padding:40px;border-radius:16px;border:1px solid rgba(255,255,255,0.05);"><h2 style="color:#f5b81b;font-size:32px;">من نحن</h2><p style="opacity:0.9;font-size:18px;margin-top:15px;">شركة ركاز للمقاولات الكهربائية والتيار الخفيف تأسست عام 2010، نمتلك فريقاً من المهندسين والفنيين ذوي الخبرة في تنفيذ المشاريع الكبرى. نقدم حلولاً مبتكرة وآمنة في مجال الكهرباء، التيار الخفيف، أنظمة المراقبة، والتحكم الذكي. نلتزم بالجودة والمواعيد لنكون شريكك الموثوق.</p></div></section>
<section id="contact" style="background:rgba(255,255,255,0.02);"><div class="container contact-wrap"><div class="contact-form"><h3 style="color:#f5b81b;margin-bottom:15px;"><i class="fas fa-paper-plane"></i> أرسل طلبك</h3><input type="text" id="cname" placeholder="الاسم الكامل"><input type="email" id="cemail" placeholder="البريد الإلكتروني"><input type="text" id="cphone" placeholder="رقم الهاتف"><textarea id="cmsg" placeholder="نوع الخدمة المطلوبة (كهرباء، كاميرات، شبكات، إنذار...)"></textarea><button class="btn" onclick="sendContact()" style="width:100%;"><i class="fas fa-check"></i> إرسال الطلب</button></div><div class="contact-info"><h3 style="color:#f5b81b;margin-bottom:20px;">معلومات الاتصال</h3><div class="item"><i class="fas fa-map-pin"></i> {{ settings.address }}</div><div class="item"><i class="fas fa-phone-alt"></i> {{ settings.phone }}</div><div class="item"><i class="fas fa-envelope"></i> {{ settings.email }}</div><div class="item"><i class="fas fa-clock"></i> السبت - الخميس: 9ص - 6م</div><div style="margin-top:25px;border-radius:15px;overflow:hidden;height:150px;"><iframe src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3453.0!2d31.2357!3d30.0444!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x14583fa60b21beeb%3A0x79dfb296e8423bba!2z2YXYr9mK2YbYqSDYp9mE2YTZgtmK2Kk!5e0!3m2!1sar!2seg!4v1719650000000" width="100%" height="150" style="border:0;" allowfullscreen="" loading="lazy"></iframe></div></div></div></section>
<footer><div class="container"><div class="socials"><a href="#"><i class="fab fa-facebook-f"></i></a><a href="#"><i class="fab fa-instagram"></i></a><a href="#"><i class="fab fa-whatsapp"></i></a><a href="#"><i class="fab fa-linkedin-in"></i></a></div><p style="margin-top:15px;">© 2025 {{ settings.company_name }} للمقاولات الكهربائية والتيار الخفيف – جميع الحقوق محفوظة</p></div></footer>
<button class="chat-btn" onclick="toggleChat()"><i class="fas fa-robot"></i></button>
<div class="chat-window" id="chatWindow"><div class="chat-header"><span>⚡ مساعد {{ settings.company_name }}</span><span onclick="toggleChat()" style="cursor:pointer;">✕</span></div><div class="chat-body" id="chatBody"><div class="chat-msg bot">مرحباً، أنا مساعد {{ settings.company_name }} الذكي. اسألني عن الكهرباء، التيار الخفيف، الكاميرات، أو أي استفسار فني.</div></div><div class="chat-footer"><input id="chatInput" placeholder="اكتب سؤالك..."><button onclick="sendChat()">إرسال</button></div></div>
<script>
function animateCounter(id,target){let c=0;const el=document.getElementById(id);const step=Math.ceil(target/60);const interval=setInterval(()=>{c+=step;if(c>=target){c=target;clearInterval(interval)}el.innerText=c},20)}
setTimeout(()=>{animateCounter('stat1',127);animateCounter('stat2',95);animateCounter('stat3',15)},300);
function toggleChat(){document.getElementById('chatWindow').classList.toggle('active')}
async function sendChat(){const input=document.getElementById('chatInput');const msg=input.value.trim();if(!msg)return;const body=document.getElementById('chatBody');body.innerHTML+=`<div class="chat-msg user">${msg}</div>`;input.value='';body.innerHTML+=`<div class="chat-msg bot">⏳ جاري التفكير...</div>`;try{const res=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg})});const data=await res.json();body.removeChild(body.lastChild);body.innerHTML+=`<div class="chat-msg bot">${data.reply||'عذراً، خطأ.'}</div>`;body.scrollTop=body.scrollHeight}catch(e){body.removeChild(body.lastChild);body.innerHTML+=`<div class="chat-msg bot">⚠️ حدث خطأ في الاتصال بالخادم.</div>`}}
async function sendContact(){const name=document.getElementById('cname').value,email=document.getElementById('cemail').value,phone=document.getElementById('cphone').value,msg=document.getElementById('cmsg').value;if(!name||!msg)return alert('املأ الاسم والرسالة');await fetch('/contact',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,email,phone,msg})});alert('✅ تم إرسال طلبك، سنتواصل معك خلال 24 ساعة.')}
</script>
</body>
</html>
"""

ADMIN_LOGIN_HTML = """
<!DOCTYPE html>
<html dir="rtl"><head><meta charset="UTF-8"><title>تسجيل الدخول</title>
<style>body{background:#0a0e1a;color:#fff;font-family:Tahoma;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;}.login-box{background:#111833;padding:40px;border-radius:20px;border:1px solid #f5b81b;width:350px;}.login-box h1{color:#f5b81b;text-align:center;}.login-box input{width:100%;padding:12px;margin:10px 0;border-radius:10px;border:none;background:#0a0e1a;color:#fff;}.login-box button{width:100%;padding:12px;background:#f5b81b;border:none;border-radius:10px;font-weight:bold;cursor:pointer;}.error{color:#ff6b6b;text-align:center;}</style>
</head>
<body><div class="login-box"><h1>🔐 لوحة التحكم</h1>{% if error %}<p class="error">{{ error }}</p>{% endif %}<form method="POST"><input type="text" name="username" placeholder="اسم المستخدم" required><input type="password" name="password" placeholder="كلمة المرور" required><button type="submit">تسجيل الدخول</button></form></div></body>
</html>
"""

ADMIN_DASHBOARD_HTML = """
<!DOCTYPE html>
<html dir="rtl"><head><meta charset="UTF-8"><title>لوحة التحكم</title>
<style>*{margin:0;padding:0;box-sizing:border-box;font-family:Tahoma;}body{background:#0a0e1a;color:#fff;padding:20px;}.container{max-width:1200px;margin:auto;}.header{display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #f5b81b;padding-bottom:15px;margin-bottom:30px;}.header h1{color:#f5b81b;}.header a{color:#f5b81b;text-decoration:none;}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:20px;margin-bottom:30px;}.stat-card{background:#111833;padding:20px;border-radius:15px;text-align:center;border-right:4px solid #f5b81b;}.stat-card h2{color:#f5b81b;font-size:32px;}.menu{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;}.menu a{background:#111833;padding:20px;border-radius:15px;text-align:center;color:#fff;text-decoration:none;transition:0.3s;border:1px solid rgba(255,255,255,0.05);}.menu a:hover{background:#1a2a4a;border-color:#f5b81b;}.menu a i{font-size:30px;color:#f5b81b;display:block;margin-bottom:10px;}</style>
</head>
<body><div class="container"><div class="header"><h1>📊 لوحة التحكم</h1><a href="/admin/logout">🚪 تسجيل الخروج</a></div><div class="stats"><div class="stat-card"><h2>{{ posts|length }}</h2><p>📝 المقالات</p></div><div class="stat-card"><h2>{{ tenders|length }}</h2><p>🔍 المناقصات</p></div><div class="stat-card"><h2>{{ msgs|length }}</h2><p>✉️ الرسائل</p></div><div class="stat-card"><h2>{{ chats|length }}</h2><p>💬 المحادثات</p></div></div><div class="menu"><a href="/admin/posts"><i>📝</i> المقالات</a><a href="/admin/tenders"><i>🔍</i> المناقصات</a><a href="/admin/messages"><i>✉️</i> الرسائل</a><a href="/admin/settings"><i>⚙️</i> الإعدادات</a><a href="/admin/system"><i>🖥️</i> النظام</a><a href="/admin/publish_now"><i>🚀</i> نشر فوري</a><a href="/admin/fetch_tenders_now"><i>📡</i> جلب مناقصات</a><a href="/"><i>🏠</i> العودة للموقع</a></div></div></body>
</html>
"""

ADMIN_POSTS_HTML = """
<!DOCTYPE html>
<html dir="rtl"><head><meta charset="UTF-8"><title>المقالات</title>
<style>*{margin:0;padding:0;box-sizing:border-box;font-family:Tahoma;}body{background:#0a0e1a;color:#fff;padding:20px;}.container{max-width:1200px;margin:auto;}.header{display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #f5b81b;padding-bottom:15px;margin-bottom:30px;}.header a{color:#f5b81b;text-decoration:none;}.post-card{background:#111833;padding:20px;border-radius:15px;margin-bottom:15px;border-right:3px solid #f5b81b;}.post-card h3{color:#f5b81b;}.post-card small{opacity:0.6;}.post-card .actions a{color:#ff6b6b;text-decoration:none;margin-left:15px;}.form-add{background:#111833;padding:20px;border-radius:15px;margin-bottom:30px;}.form-add input,.form-add textarea{width:100%;padding:12px;margin:10px 0;border-radius:10px;border:none;background:#0a0e1a;color:#fff;}.form-add button{background:#f5b81b;border:none;padding:12px 30px;border-radius:10px;font-weight:bold;cursor:pointer;}</style>
</head>
<body><div class="container"><div class="header"><h1>📝 المقالات</h1><a href="/admin">← العودة</a></div><div class="form-add"><h3 style="color:#f5b81b;">إضافة مقال جديد</h3><form method="POST" action="/admin/posts/add"><input type="text" name="title" placeholder="عنوان المقال" required><textarea name="content" placeholder="محتوى المقال" rows="5" required></textarea><button type="submit">➕ إضافة</button></form></div>{% for post in posts|reverse %}<div class="post-card"><h3>{{ post.title }}</h3><p>{{ post.content[:200] }}{% if post.content|length > 200 %}...{% endif %}</p><small>{{ post.date }}</small><div class="actions"><a href="/admin/posts/delete/{{ loop.index0 }}">🗑️ حذف</a></div></div>{% else %}<p>لا توجد مقالات.</p>{% endfor %}</div></body>
</html>
"""

ADMIN_TENDERS_HTML = """
<!DOCTYPE html>
<html dir="rtl"><head><meta charset="UTF-8"><title>المناقصات</title>
<style>*{margin:0;padding:0;box-sizing:border-box;font-family:Tahoma;}body{background:#0a0e1a;color:#fff;padding:20px;}.container{max-width:1200px;margin:auto;}.header{display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #f5b81b;padding-bottom:15px;margin-bottom:30px;}.header a{color:#f5b81b;text-decoration:none;}.tender-card{background:#111833;padding:20px;border-radius:15px;margin-bottom:15px;border-right:3px solid #f5b81b;}.tender-card h3{color:#f5b81b;}.tender-card a{color:#1a73e8;text-decoration:none;}</style>
</head>
<body><div class="container"><div class="header"><h1>🔍 المناقصات</h1><a href="/admin">← العودة</a></div>{% for tender in tenders|reverse %}<div class="tender-card"><h3>{{ tender.title }}</h3><p>{{ tender.summary }}</p><a href="{{ tender.link }}" target="_blank">🔗 رابط المناقصة</a><small>{{ tender.date }}</small></div>{% else %}<p>لا توجد مناقصات.</p>{% endfor %}</div></body>
</html>
"""

ADMIN_MESSAGES_HTML = """
<!DOCTYPE html>
<html dir="rtl"><head><meta charset="UTF-8"><title>الرسائل</title>
<style>*{margin:0;padding:0;box-sizing:border-box;font-family:Tahoma;}body{background:#0a0e1a;color:#fff;padding:20px;}.container{max-width:1200px;margin:auto;}.header{display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #f5b81b;padding-bottom:15px;margin-bottom:30px;}.header a{color:#f5b81b;text-decoration:none;}.msg-card{background:#111833;padding:20px;border-radius:15px;margin-bottom:15px;border-right:3px solid #f5b81b;}.msg-card h4{color:#f5b81b;}.msg-card small{opacity:0.6;}</style>
</head>
<body><div class="container"><div class="header"><h1>✉️ رسائل العملاء</h1><a href="/admin">← العودة</a></div>{% for msg in msgs|reverse %}<div class="msg-card"><h4>{{ msg.name }} ({{ msg.email }})</h4><p><strong>الهاتف:</strong> {{ msg.phone }}</p><p>{{ msg.msg }}</p><small>{{ msg.time }}</small></div>{% else %}<p>لا توجد رسائل.</p>{% endfor %}</div></body>
</html>
"""

ADMIN_SETTINGS_HTML = """
<!DOCTYPE html>
<html dir="rtl"><head><meta charset="UTF-8"><title>الإعدادات</title>
<style>*{margin:0;padding:0;box-sizing:border-box;font-family:Tahoma;}body{background:#0a0e1a;color:#fff;padding:20px;}.container{max-width:800px;margin:auto;}.header{display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #f5b81b;padding-bottom:15px;margin-bottom:30px;}.header a{color:#f5b81b;text-decoration:none;}.form-settings{background:#111833;padding:30px;border-radius:15px;}.form-settings label{display:block;margin-top:15px;color:#f5b81b;}.form-settings input,.form-settings textarea{width:100%;padding:12px;margin:5px 0;border-radius:10px;border:none;background:#0a0e1a;color:#fff;}.form-settings button{background:#f5b81b;border:none;padding:12px 30px;border-radius:10px;font-weight:bold;cursor:pointer;margin-top:20px;}</style>
</head>
<body><div class="container"><div class="header"><h1>⚙️ الإعدادات</h1><a href="/admin">← العودة</a></div><div class="form-settings"><form method="POST"><label>اسم الشركة</label><input type="text" name="company_name" value="{{ settings.company_name }}"><label>الشعار</label><input type="text" name="company_slogan" value="{{ settings.company_slogan }}"><label>الهاتف</label><input type="text" name="phone" value="{{ settings.phone }}"><label>البريد الإلكتروني</label><input type="email" name="email" value="{{ settings.email }}"><label>العنوان</label><input type="text" name="address" value="{{ settings.address }}"><label>عنوان الهيرو</label><input type="text" name="hero_title" value="{{ settings.hero_title }}"><label>نص الهيرو</label><input type="text" name="hero_subtitle" value="{{ settings.hero_subtitle }}"><label>مواعيد النشر (مفصولة بفاصلة) مثل 08:00,14:00</label><input type="text" name="publish_times" value="{{ settings.publish_times|join(',') }}"><label>عدد أيام الاحتفاظ بالمقالات (للتظيف)</label><input type="number" name="cleanup_days" value="{{ settings.cleanup_days }}"><button type="submit">💾 حفظ الإعدادات</button></form></div></div></body>
</html>
"""

ADMIN_SYSTEM_HTML = """
<!DOCTYPE html>
<html dir="rtl"><head><meta charset="UTF-8"><title>النظام</title>
<style>*{margin:0;padding:0;box-sizing:border-box;font-family:Tahoma;}body{background:#0a0e1a;color:#fff;padding:20px;}.container{max-width:800px;margin:auto;}.header{display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #f5b81b;padding-bottom:15px;margin-bottom:30px;}.header a{color:#f5b81b;text-decoration:none;}.sys-card{background:#111833;padding:20px;border-radius:15px;margin-bottom:15px;border-right:3px solid #f5b81b;}.sys-card .status{font-size:24px;}.sys-card .label{opacity:0.6;}</style>
</head>
<body><div class="container"><div class="header"><h1>🖥️ حالة النظام</h1><a href="/admin">← العودة</a></div><div class="sys-card"><h3>📊 إحصائيات النظام</h3><p><span class="label">المقالات:</span> {{ posts_count }}</p><p><span class="label">المناقصات:</span> {{ tenders_count }}</p><p><span class="label">الرسائل:</span> {{ msgs_count }}</p><p><span class="label">المحادثات:</span> {{ chats_count }}</p><p><span class="label">السجلات:</span> {{ logs_count }}</p></div><div class="sys-card"><h3>⏰ وقت التشغيل</h3><p>{{ now }}</p></div></div></body>
</html>
"""

# ================================================================
# تشغيل التطبيق
# ================================================================

if __name__ == '__main__':
    settings = load_settings()
    PUBLISH_TIMES = settings.get("publish_times", ["08:00", "14:00"])
    CLEANUP_DAYS = settings.get("cleanup_days", 30)

    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()

    print("=" * 60)
    print("🚀 نظام ركاز الشامل يعمل (نسخة الإنتاج النهائية - آمنة)")
    print("🌐 الموقع: http://127.0.0.1:5000")
    print("🔐 لوحة التحكم: http://127.0.0.1:5000/admin/login (مخفية)")
    print("👤 اسم المستخدم: admin")
    print("🔑 كلمة المرور: k7#9mX2!qL5@vP8 (غيّرها فوراً!)")
    print("=" * 60)
    print("📌 الميزات الأمنية:")
    print("   ✅ حماية CSP و Talisman")
    print("   ✅ تقييد الطلبات (Rate Limiting)")
    print("   ✅ تنظيف المدخلات (Sanitization)")
    print("   ✅ جلسات آمنة (HTTPOnly, SameSite)")
    print("   ✅ لوحة تحكم محمية بتسجيل الدخول")
    print("   ✅ أزرار تحكم فوري (نشر/جلب مناقصات)")
    print("=" * 60)

    app.run(host='0.0.0.0', port=5000, debug=False)