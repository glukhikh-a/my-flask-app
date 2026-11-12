import sqlite3
from flask import Flask, request, redirect, url_for, session, g, render_template_string

app = Flask(__name__)
app.secret_key = "dev-secret-key"

DB_PATH = "vulnerable.db"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_username TEXT NOT NULL,
        author TEXT NOT NULL,
        text TEXT NOT NULL
    )""")
    conn.execute(
        "INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)",
        ("admin", "Sup3rSecretAdminPass!"),
    )
    conn.commit()
    conn.close()


LAYOUT = """
<!doctype html>
<html lang="ru">
<head><meta charset="utf-8"><title>VulnApp</title></head>
<body style="font-family: sans-serif; max-width: 640px; margin: 40px auto;">
  <h2><a href="/">VulnApp</a></h2>
  <nav>
    {% if session.get('username') %}
      Вы вошли как <b>{{ session['username'] }}</b> ·
      <a href="/profile/{{ session['username'] }}">мой профиль</a> ·
      <a href="/logout">выйти</a>
    {% else %}
      <a href="/register">регистрация</a> · <a href="/login">вход</a>
    {% endif %}
  </nav>
  <hr>
  {{ body|safe }}
</body>
</html>
"""


def render(body_html, **ctx):
    return render_template_string(LAYOUT, body=render_template_string(body_html, **ctx))


@app.route("/")
def index():
    return render("<p>Тестовый стенд.</p>")


REGISTER_FORM = """
<h3>Регистрация</h3>
<form method="post">
  Логин: <input name="username"><br><br>
  Пароль: <input name="password" type="password"><br><br>
  <button type="submit">Зарегистрироваться</button>
</form>
"""


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, password),
            )
            db.commit()
        except sqlite3.IntegrityError:
            return render("<p style='color:red'>Такой пользователь уже существует.</p>")
        return redirect(url_for("login"))
    return render(REGISTER_FORM)


LOGIN_FORM = """
<h3>Вход</h3>
<form method="post">
  Логин: <input name="username"><br><br>
  Пароль: <input name="password" type="password"><br><br>
  <button type="submit">Войти</button>
</form>
"""


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        db = get_db()

        # собираем запрос строкой - тут и прячется SQL-инъекция
        query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
        user = db.execute(query).fetchone()

        if user:
            session["username"] = user["username"]
            return redirect(url_for("profile", username=user["username"]))
        return render("<p style='color:red'>Неверный логин или пароль.</p>" + LOGIN_FORM)

    return render(LOGIN_FORM)


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("index"))


PROFILE_PAGE = """
<h3>Профиль: {{ profile_username }}</h3>

<h4>Комментарии</h4>
{% for c in comments %}
  <div style="border:1px solid #ccc; padding:6px; margin:6px 0;">
    <b>{{ c.author }}:</b> {{ c.text|safe }}
  </div>
{% else %}
  <p><i>Комментариев пока нет.</i></p>
{% endfor %}

{% if session.get('username') %}
<h4>Оставить комментарий</h4>
<form method="post" action="/profile/{{ profile_username }}/comment">
  <textarea name="text" rows="3" cols="40"></textarea><br>
  <button type="submit">Отправить</button>
</form>
{% else %}
<p><a href="/login">Войдите</a>, чтобы оставить комментарий.</p>
{% endif %}
"""


@app.route("/profile/<username>")
def profile(username):
    db = get_db()
    comments = db.execute(
        "SELECT author, text FROM comments WHERE profile_username = ? ORDER BY id",
        (username,),
    ).fetchall()
    return render(PROFILE_PAGE, profile_username=username, comments=comments)


@app.route("/profile/<username>/comment", methods=["POST"])
def add_comment(username):
    if "username" not in session:
        return redirect(url_for("login"))
    text = request.form.get("text", "")
    db = get_db()
    db.execute(
        "INSERT INTO comments (profile_username, author, text) VALUES (?, ?, ?)",
        (username, session["username"], text),
    )
    db.commit()
    return redirect(url_for("profile", username=username))


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
