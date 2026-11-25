import html
import json
import os
import re
import uuid
from datetime import date
from pathlib import Path
from typing import Optional

import bcrypt
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from google import genai
from jinja2 import TemplateNotFound
from starlette.middleware.sessions import SessionMiddleware
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-secret-key")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(".env файлында SUPABASE_URL немесе SUPABASE_KEY көрсетілмеген")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
GEMINI_MODEL = "gemini-2.5-flash"
BUCKET_NAME = "portfolio_pdfs"

FALLBACK_TESTS: dict[str, dict] = {}
FALLBACK_RESULTS: list[dict] = []

CATEGORY_KEYS = [
    "own_achievements",
    "competitions",
    "order_130",
    "platforms",
    "curator",
    "student_achievements",
]

TRANSLATIONS = {
    "kk": {
        "app_title": "AI ұстаз",
        "login_page_title": "Кіру / Тіркелу — AI ұстаз",
        "app_subtitle": "Оқытушының цифрлық базасы",
        "nav_title": "Портфолио бөлімдері",
        "ai_nav": "AI Көмекші",
        "test_nav": "Тәрбие тест",
        "upload_photo_title": "Суретті өзгерту",
        "page_subtitle": "Құжаттарды, сертификаттарды және оқу-әдістемелік материалдарды жүйелеу",
        "in_section": "Бұл бөлімде:",
        "records_word": "жазба",
        "add_title": "Жаңа материал қосу",
        "field_title": "Материал атауы *",
        "placeholder_title": "Мысалы: Сабақ жоспары — Python функциялары",
        "field_extra": "Қосымша мәлімет (деңгейі, топ, сілтеме)",
        "placeholder_extra": "Мысалы: Республикалық / 2-курс / Moodle",
        "field_date": "Күні",
        "field_desc": "Қысқаша сипаттамасы",
        "placeholder_desc": "Жұмыстың мазмұны, нәтижесі немесе ескертпе...",
        "field_pdf": "PDF құжат тіркеу (міндетті емес, 50 МБ дейін)",
        "drop_hint": "PDF файлды таңдау үшін басыңыз немесе осы жерге сүйреп әкеліңіз",
        "selected_prefix": "Таңдалды:",
        "btn_save": "Портфолиоға сақтау",
        "list_title": "Сақталған материалдар тізімі",
        "open_pdf": "PDF ашу",
        "no_pdf": "PDF тіркелмеген",
        "btn_delete": "Өшіру",
        "confirm_delete": "Бұл жазбаны өшіруге сенімдісіз бе?",
        "empty_title": "Бұл бөлімде әзірге жазба жоқ",
        "empty_desc": "Жоғарыдағы форма арқылы алғашқы құжатты немесе жетістікті қосыңыз.",
        "logout_title": "Жүйеден шығу",
        "ai_title": "AI Көмекші (Gemini)",
        "ai_subtitle": "Колледждің ақылды оқу платформасы: сабақ жоспары, тапсырма, тест және әдістемелік көмек",
        "ai_placeholder": "Мысалы: Python функциялары тақырыбына 5 тест сұрағын және сабақ мақсатын құрастыр...",
        "ai_btn": "Сұрау жіберу",
        "ai_answer_label": "AI жауабы:",
        "ai_missing_key": ".env файлында GEMINI_API_KEY көрсетілмеген.",
        "ai_empty_prompt": "Сұрақ немесе тапсырма мәтінін жазыңыз.",
        "ai_error": "Gemini API қатесі:",
        "avatar_error": "Суретті жүктеу қатесі:",
        "test_title_heading": "Тәрбие тест",
        "test_subtitle": "Студенттерге тәрбие бағытында тест құрастыру, сілтеме жіберу және нәтижені көру",
        "test_create_title": "Жаңа тәрбие тестін құру",
        "test_name_label": "Тест атауы *",
        "test_name_placeholder": "Мысалы: Адалдық және сыбайлас жемқорлыққа қарсы мәдениет",
        "test_raw_label": "Сұрақтар мен жауаптар (әр сұрақты нөмірлеп жазыңыз)*",
        "test_raw_placeholder": (
            "1. Адалдық деген не?\n"
            "А) Шыншылдық пен әділдік\n"
            "Ә) Айлакерлік\n"
            "Б) Немқұрайлылық\n"
            "Дұрыс: А\n"
            "2. Командалық жұмыста қандай қасиет маңызды?\n"
            "А) Өзара құрмет\n"
            "Ә) Менмендік\n"
            "Б) Жауапкершіліктен қашу\n"
            "Дұрыс: А"
        ),
        "test_create_btn": "Тест жасау және сілтеме алу",
        "test_created_list": "Құрылған тесттер және студент сілтемесі",
        "test_link_label": "Студент сілтемесі:",
        "test_results_title": "Студенттердің нәтижелері",
        "student_col": "Студент",
        "group_col": "Топ",
        "test_col": "Тест",
        "score_col": "Нәтиже",
        "no_results": "Әзірге ешбір студент тест тапсырмаған.",
        "no_tests": "Әзірге тест құрылмаған.",
        "login_heading": "Жүйеге кіру",
        "field_login": "Логин",
        "field_password": "Пароль",
        "btn_login": "Кіру",
        "reg_heading": "Жаңа оқытушы тіркеу",
        "field_fullname": "Аты-жөні (Т.А.Ә.)",
        "field_subject": "Пәні / Модулі",
        "default_subject": "Арнайы пәндер",
        "btn_register": "Тіркелу",
        "err_credentials": "Логин немесе пароль қате",
        "err_login_taken": "Бұл логин бос емес",
        "info_logged_out": "Жүйеден шықтыңыз",
        "categories": {
            "own_achievements": "Өз жетістіктерім",
            "competitions": "Шеберлік сынып және конференция",
            "order_130": "Сабақ жоспары",
            "platforms": "Оқыту платформалары",
            "curator": "Кураторлық жұмыс және сыныптан тыс іс-шаралар",
            "student_achievements": "Студенттер жетістігі",
        },
    },
    "ru": {
        "app_title": "AI ұстаз",
        "login_page_title": "Вход / Регистрация — AI ұстаз",
        "app_subtitle": "Цифровая база преподавателя",
        "nav_title": "Разделы портфолио",
        "ai_nav": "AI Помощник",
        "test_nav": "Воспитательный тест",
        "upload_photo_title": "Изменить фото",
        "page_subtitle": "Систематизация документов, сертификатов и учебно-методических материалов",
        "in_section": "В разделе:",
        "records_word": "зап.",
        "add_title": "Добавить новый материал",
        "field_title": "Название материала *",
        "placeholder_title": "Например: План урока — Функции Python",
        "field_extra": "Дополнительно (уровень, группа, ссылка)",
        "placeholder_extra": "Например: Республиканский / 2 курс / Moodle",
        "field_date": "Дата",
        "field_desc": "Краткое описание",
        "placeholder_desc": "Содержание работы, результат или примечание...",
        "field_pdf": "Прикрепить PDF-документ (необязательно, до 50 МБ)",
        "drop_hint": "Нажмите, чтобы выбрать PDF-файл, или перетащите его сюда",
        "selected_prefix": "Выбрано:",
        "btn_save": "Сохранить в портфолио",
        "list_title": "Список сохранённых материалов",
        "open_pdf": "Открыть PDF",
        "no_pdf": "PDF не прикреплён",
        "btn_delete": "Удалить",
        "confirm_delete": "Вы уверены, что хотите удалить эту запись?",
        "empty_title": "В этом разделе пока нет записей",
        "empty_desc": "Добавьте первый документ или достижение через форму выше.",
        "logout_title": "Выйти из системы",
        "ai_title": "AI Помощник (Gemini)",
        "ai_subtitle": "Умная учебная платформа колледжа: планы уроков, задания, тесты и методическая помощь",
        "ai_placeholder": "Например: Составь 5 тестовых вопросов и цель урока по теме Функции Python...",
        "ai_btn": "Отправить",
        "ai_answer_label": "Ответ AI:",
        "ai_missing_key": "В файле .env не указан GEMINI_API_KEY.",
        "ai_empty_prompt": "Введите текст запроса.",
        "ai_error": "Ошибка Gemini API:",
        "avatar_error": "Ошибка загрузки фото:",
        "test_title_heading": "Воспитательный тест",
        "test_subtitle": "Создание теста для студентов, отправка ссылки и просмотр результатов",
        "test_create_title": "Создать новый воспитательный тест",
        "test_name_label": "Название теста *",
        "test_name_placeholder": "Например: Честность и антикоррупционная культура",
        "test_raw_label": "Вопросы и варианты ответов (нумеруйте каждый вопрос)*",
        "test_raw_placeholder": (
            "1. Что такое честность?\n"
            "А) Правдивость и справедливость\n"
            "Б) Хитрость\n"
            "В) Равнодушие\n"
            "Ответ: А\n"
            "2. Что важно в командной работе?\n"
            "А) Взаимное уважение\n"
            "Б) Высокомерие\n"
            "В) Уход от ответственности\n"
            "Ответ: А"
        ),
        "test_create_btn": "Создать тест и получить ссылку",
        "test_created_list": "Созданные тесты и ссылка для студентов",
        "test_link_label": "Ссылка для студентов:",
        "test_results_title": "Результаты студентов",
        "student_col": "Студент",
        "group_col": "Группа",
        "test_col": "Тест",
        "score_col": "Результат",
        "no_results": "Пока ни один студент не прошёл тест.",
        "no_tests": "Тесты ещё не созданы.",
        "login_heading": "Вход в систему",
        "field_login": "Логин",
        "field_password": "Пароль",
        "btn_login": "Войти",
        "reg_heading": "Регистрация преподавателя",
        "field_fullname": "Ф.И.О.",
        "field_subject": "Предмет / Модуль",
        "default_subject": "Специальные дисциплины",
        "btn_register": "Зарегистрироваться",
        "err_credentials": "Неверный логин или пароль",
        "err_login_taken": "Этот логин уже занят",
        "info_logged_out": "Вы вышли из системы",
        "categories": {
            "own_achievements": "Собственные достижения",
            "competitions": "Мастер-классы и конференции",
            "order_130": "Планы уроков",
            "platforms": "Образовательные платформы",
            "curator": "Кураторская работа и внеклассные мероприятия",
            "student_achievements": "Достижения студентов",
        },
    },
}

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="AI ұстаз")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def get_lang(request: Request) -> str:
    lang = request.session.get("lang", "kk")
    return lang if lang in TRANSLATIONS else "kk"


def get_t(request: Request) -> dict:
    return TRANSLATIONS[get_lang(request)]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def get_current_user(request: Request) -> Optional[dict]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    res = supabase.table("users").select("*").eq("id", user_id).execute()
    if res.data:
        user = dict(res.data[0])
        if not user.get("avatar_url") and request.session.get("avatar_url"):
            user["avatar_url"] = request.session["avatar_url"]
        return user
    return None


def parse_questions(raw_text: str) -> list[dict]:
    lines = [line.strip() for line in raw_text.strip().splitlines() if line.strip()]
    groups: list[list[str]] = []
    current: list[str] = []

    for line in lines:
        if re.match(r"^\d+[\).\s]+", line):
            if current:
                groups.append(current)
            current = [line]
        else:
            if current:
                current.append(line)
            else:
                current = [line]

    if current:
        groups.append(current)

    questions: list[dict] = []
    for idx, q_lines in enumerate(groups, start=1):
        q_text = q_lines[0]
        options: list[dict] = []
        correct_key = ""

        for line in q_lines[1:]:
            lower = line.lower()
            if lower.startswith(("дұрыс:", "жауап:", "ответ:", "правильный ответ:")):
                ans_val = line.split(":", 1)[1].strip()
                correct_key = ans_val[:1].upper() if ans_val else ""
            else:
                m = re.match(r"^([А-ЯӘІҢҒҮҰҚӨҺA-Za-z0-9]+)[\).\:]\s*(.+)$", line)
                if m:
                    opt_key = m.group(1).upper()
                    opt_label = m.group(2).strip()
                else:
                    opt_key = str(len(options) + 1)
                    opt_label = line
                options.append({"key": opt_key, "label": opt_label, "raw": line})

        if not options:
            options = [
                {"key": "А", "label": "Иә", "raw": "А) Иә"},
                {"key": "Ә", "label": "Жоқ", "raw": "Ә) Жоқ"},
            ]
        if not correct_key:
            correct_key = options[0]["key"]

        questions.append(
            {
                "index": idx,
                "question": q_text,
                "options": options,
                "correct": correct_key,
            }
        )

    return questions


def load_tests_and_results(user_id: str) -> tuple[list[dict], list[dict]]:
    tests: list[dict] = []
    results: list[dict] = []
    try:
        t_res = (
            supabase.table("tarbie_tests")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        for row in t_res.data or []:
            try:
                qs = json.loads(row.get("questions_json") or "[]")
            except Exception:
                qs = []
            tests.append({**row, "questions": qs})
    except Exception:
        pass

    if not tests:
        for row in FALLBACK_TESTS.values():
            if row.get("user_id") == user_id:
                tests.append(row)

    test_ids = {t_item["id"] for t_item in tests}
    test_titles = {t_item["id"]: t_item["title"] for t_item in tests}

    try:
        r_res = (
            supabase.table("tarbie_test_results")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        for row in r_res.data or []:
            if row.get("test_id") in test_ids:
                results.append({**row, "test_title": test_titles.get(row["test_id"], "")})
    except Exception:
        pass

    if not results:
        for row in FALLBACK_RESULTS:
            if row.get("test_id") in test_ids:
                results.append({**row, "test_title": test_titles.get(row["test_id"], "")})

    return tests, results


def get_single_test(test_id: str) -> Optional[dict]:
    try:
        res = supabase.table("tarbie_tests").select("*").eq("id", test_id).execute()
        if res.data:
            row = res.data[0]
            try:
                qs = json.loads(row.get("questions_json") or "[]")
            except Exception:
                qs = []
            return {**row, "questions": qs}
    except Exception:
        pass
    return FALLBACK_TESTS.get(test_id)


def render_fallback_test_page(
    test_obj: dict,
    submitted: Optional[str],
    score: Optional[int],
    total: Optional[int],
    student_name: str,
) -> HTMLResponse:
    title = html.escape(str(test_obj.get("title", "Тәрбие тесті")))
    test_id = html.escape(str(test_obj.get("id", "")))
    questions = test_obj.get("questions") or []

    result_banner = ""
    if submitted and score is not None and total is not None:
        safe_name = html.escape(student_name or "Студент")
        result_banner = (
            f'<div style="background:#e6f4ea;border:1px solid #34a853;padding:14px;'
            f'border-radius:8px;margin-bottom:20px;">'
            f'<strong>{safe_name}</strong>, тест аяқталды! Нәтиже: <strong>{score} / {total}</strong>'
            f"</div>"
        )

    q_blocks = []
    for q in questions:
        q_idx = html.escape(str(q.get("index", "")))
        q_text = html.escape(str(q.get("question", "")))
        opts_html = []
        for opt in q.get("options") or []:
            opt_key = html.escape(str(opt.get("key", "")))
            opt_raw = html.escape(str(opt.get("raw") or f"{opt.get('key', '')}) {opt.get('label', '')}"))
            opts_html.append(
                f'<label style="display:block;margin:6px 0;cursor:pointer;">'
                f'<input type="radio" name="q_{q_idx}" value="{opt_key}" required> {opt_raw}'
                f"</label>"
            )
        q_blocks.append(
            f'<div style="border:1px solid #ddd;border-radius:8px;padding:14px;margin-bottom:14px;">'
            f'<p style="margin-top:0;font-weight:600;">{q_text}</p>'
            f'{"".join(opts_html)}'
            f"</div>"
        )

    page_html = f"""<!DOCTYPE html>
<html lang="kk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body style="font-family:Arial,sans-serif;max-width:720px;margin:32px auto;padding:0 16px;">
    <h2>{title}</h2>
    {result_banner}
    <form method="post" action="/test/{test_id}/submit">
        <div style="margin-bottom:12px;">
            <label>Студенттің аты-жөні *:<br>
                <input type="text" name="student_name" required style="width:100%;padding:8px;margin-top:4px;">
            </label>
        </div>
        <div style="margin-bottom:18px;">
            <label>Топ:<br>
                <input type="text" name="student_group" style="width:100%;padding:8px;margin-top:4px;">
            </label>
        </div>
        {"".join(q_blocks)}
        <button type="submit" style="padding:10px 20px;font-size:15px;cursor:pointer;">
            Жауапты жіберу
        </button>
    </form>
</body>
</html>"""
    return HTMLResponse(content=page_html)


@app.get("/lang/{code}")
async def switch_language(request: Request, code: str, next: str = "/"):
    if code in TRANSLATIONS:
        request.session["lang"] = code
    safe_next = next if next.startswith("/") else "/"
    return RedirectResponse(url=safe_next, status_code=303)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, category: str = "own_achievements", view: str = "section"):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if category not in CATEGORY_KEYS:
        category = "own_achievements"

    ai_mode = view == "ai"
    test_mode = view == "test"
    lang = get_lang(request)
    t = get_t(request)

    items_res = (
        supabase.table("portfolio_items")
        .select("*")
        .eq("user_id", user["id"])
        .eq("category", category)
        .order("created_at", desc=True)
        .execute()
    )

    all_items_res = (
        supabase.table("portfolio_items")
        .select("category")
        .eq("user_id", user["id"])
        .execute()
    )

    counts = {key: 0 for key in CATEGORY_KEYS}
    for row in all_items_res.data or []:
        cat = row.get("category")
        if cat in counts:
            counts[cat] += 1

    ai_response = request.session.pop("ai_response", None)
    ai_error = request.session.pop("ai_error", None)
    ai_prompt = request.session.pop("ai_prompt", "")
    avatar_error = request.session.pop("avatar_error", None)
    test_error = request.session.pop("test_error", None)

    tests, test_results = load_tests_and_results(user["id"])
    base_url = str(request.base_url).rstrip("/")

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "lang": lang,
            "t": t,
            "categories": t["categories"],
            "active_category": category,
            "ai_mode": ai_mode,
            "test_mode": test_mode,
            "items": items_res.data or [],
            "counts": counts,
            "ai_response": ai_response,
            "ai_error": ai_error,
            "ai_prompt": ai_prompt,
            "avatar_error": avatar_error,
            "test_error": test_error,
            "tests": tests,
            "test_results": test_results,
            "base_url": base_url,
        },
    )


@app.post("/tests/create")
async def create_tarbie_test(
    request: Request,
    title: str = Form(...),
    raw_questions: str = Form(...),
    category: str = Form("curator"),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    clean_title = title.strip()
    questions = parse_questions(raw_questions)
    if not clean_title or not questions:
        request.session["test_error"] = "Тест атауын және кемінде бір сұрақты дұрыс жазыңыз."
        return RedirectResponse(url=f"/?category={category}&view=test", status_code=303)

    test_id = uuid.uuid4().hex[:8]
    payload = {
        "id": test_id,
        "user_id": user["id"],
        "title": clean_title,
        "questions_json": json.dumps(questions, ensure_ascii=False),
    }
    FALLBACK_TESTS[test_id] = {**payload, "questions": questions}
    try:
        supabase.table("tarbie_tests").insert(payload).execute()
    except Exception:
        pass

    return RedirectResponse(url=f"/?category={category}&view=test", status_code=303)


@app.get("/test/{test_id}", response_class=HTMLResponse)
async def take_tarbie_test_page(request: Request, test_id: str, submitted: Optional[str] = None):
    test_obj = get_single_test(test_id)
    if not test_obj:
        return HTMLResponse("<h3>Тест табылмады / Тест не найден</h3>", status_code=404)

    score = request.session.pop("last_test_score", None)
    total = request.session.pop("last_test_total", None)
    student_name = request.session.pop("last_student_name", "")

    context = {
        "request": request,
        "test": test_obj,
        "submitted": submitted,
        "score": score,
        "total": total,
        "student_name": student_name,
    }
    try:
        return templates.TemplateResponse("test_take.html", context)
    except TemplateNotFound:
        return render_fallback_test_page(test_obj, submitted, score, total, student_name)


@app.post("/test/{test_id}/submit")
async def submit_tarbie_test(request: Request, test_id: str):
    test_obj = get_single_test(test_id)
    if not test_obj:
        return HTMLResponse("<h3>Тест табылмады / Тест не найден</h3>", status_code=404)

    form = await request.form()
    student_name = str(form.get("student_name", "")).strip() or "Студент"
    student_group = str(form.get("student_group", "")).strip()

    questions = test_obj.get("questions") or []
    score = 0
    for q in questions:
        q_idx = str(q.get("index"))
        chosen = str(form.get(f"q_{q_idx}", "")).strip().upper()
        if chosen and chosen == str(q.get("correct", "")).strip().upper():
            score += 1

    total = len(questions)
    res_row = {
        "test_id": test_id,
        "student_name": student_name,
        "student_group": student_group,
        "score": score,
        "total": total,
    }
    FALLBACK_RESULTS.append(res_row)
    try:
        supabase.table("tarbie_test_results").insert(res_row).execute()
    except Exception:
        pass

    request.session["last_test_score"] = score
    request.session["last_test_total"] = total
    request.session["last_student_name"] = student_name
    return RedirectResponse(url=f"/test/{test_id}?submitted=1", status_code=303)


@app.post("/profile/avatar")
async def upload_avatar(
    request: Request,
    avatar_file: UploadFile = File(...),
    category: str = Form("own_achievements"),
    view: str = Form("section"),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if category not in CATEGORY_KEYS:
        category = "own_achievements"

    t = get_t(request)
    suffix = f"&view={view}" if view in ("ai", "test") else ""

    if avatar_file and avatar_file.filename:
        content = await avatar_file.read()
        if content:
            ext = os.path.splitext(avatar_file.filename)[1].lower() or ".jpg"
            content_type = avatar_file.content_type or "image/jpeg"
            storage_path = f"{user['id']}/avatars/{uuid.uuid4()}{ext}"
            try:
                supabase.storage.from_(BUCKET_NAME).upload(
                    path=storage_path,
                    file=content,
                    file_options={"content-type": content_type, "upsert": "true"},
                )
                avatar_url = supabase.storage.from_(BUCKET_NAME).get_public_url(storage_path)
                request.session["avatar_url"] = avatar_url
                try:
                    supabase.table("users").update({"avatar_url": avatar_url}).eq("id", user["id"]).execute()
                except Exception:
                    pass
            except Exception as exc:
                request.session["avatar_error"] = f"{t['avatar_error']} {exc}"

    return RedirectResponse(url=f"/?category={category}{suffix}", status_code=303)


@app.post("/ai/ask")
async def ask_ai(
    request: Request,
    prompt: str = Form(...),
    category: str = Form("own_achievements"),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if category not in CATEGORY_KEYS:
        category = "own_achievements"

    lang = get_lang(request)
    t = get_t(request)
    clean_prompt = prompt.strip()
    request.session["ai_prompt"] = clean_prompt

    if not clean_prompt:
        request.session["ai_error"] = t["ai_empty_prompt"]
        return RedirectResponse(url=f"/?category={category}&view=ai", status_code=303)

    if not gemini_client:
        request.session["ai_error"] = t["ai_missing_key"]
        return RedirectResponse(url=f"/?category={category}&view=ai", status_code=303)

    section_name = t["categories"].get(category, category)
    lang_instruction = "Тек қазақ тілінде жауап бер." if lang == "kk" else "Отвечай только на русском языке."
    system_prompt = (
        f"Сен колледж оқытушысына көмектесетін AI әдіскер-көмекшісің. "
        f"Оқытушы пәні: {user.get('subject', '')}. Қазіргі бөлім: {section_name}. "
        f"{lang_instruction} Жауапты нақты, құрылымды және пайдалы етіп жаз."
    )

    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=f"{system_prompt}\n\nСұрау: {clean_prompt}",
        )
        request.session["ai_response"] = (response.text or "").strip()
    except Exception as exc:
        request.session["ai_error"] = f"{t['ai_error']} {exc}"

    return RedirectResponse(url=f"/?category={category}&view=ai", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None, info: Optional[str] = None):
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=303)
    lang = get_lang(request)
    t = get_t(request)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "lang": lang, "t": t, "error": error, "info": info},
    )


@app.post("/login")
async def login_submit(
    request: Request,
    login: str = Form(...),
    password: str = Form(...),
):
    t = get_t(request)
    clean_login = login.strip()
    res = supabase.table("users").select("*").eq("login", clean_login).execute()
    if not res.data:
        return RedirectResponse(url=f"/login?error={t['err_credentials']}", status_code=303)

    user = res.data[0]
    if not verify_password(password, user["password_hash"]):
        return RedirectResponse(url=f"/login?error={t['err_credentials']}", status_code=303)

    request.session["user_id"] = user["id"]
    if user.get("avatar_url"):
        request.session["avatar_url"] = user["avatar_url"]
    return RedirectResponse(url="/", status_code=303)


@app.post("/register")
async def register_submit(
    request: Request,
    full_name: str = Form(...),
    subject: str = Form("Арнайы пәндер"),
    login: str = Form(...),
    password: str = Form(...),
):
    t = get_t(request)
    clean_login = login.strip()
    existing = supabase.table("users").select("id").eq("login", clean_login).execute()
    if existing.data:
        return RedirectResponse(url=f"/login?error={t['err_login_taken']}", status_code=303)

    created = (
        supabase.table("users")
        .insert(
            {
                "full_name": full_name.strip(),
                "subject": subject.strip() or t["default_subject"],
                "login": clean_login,
                "password_hash": hash_password(password),
            }
        )
        .execute()
    )
    if created.data:
        request.session["user_id"] = created.data[0]["id"]
    return RedirectResponse(url="/", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    t = get_t(request)
    current_lang = get_lang(request)
    request.session.clear()
    request.session["lang"] = current_lang
    return RedirectResponse(url=f"/login?info={t['info_logged_out']}", status_code=303)


@app.post("/items/create")
async def create_item(
    request: Request,
    category: str = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    extra_info: str = Form(""),
    event_date: str = Form(""),
    pdf_file: Optional[UploadFile] = File(None),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if category not in CATEGORY_KEYS:
        category = "own_achievements"

    pdf_url = None
    pdf_path = None

    if pdf_file and pdf_file.filename:
        content = await pdf_file.read()
        if content:
            storage_path = f"{user['id']}/{category}/{uuid.uuid4()}.pdf"
            supabase.storage.from_(BUCKET_NAME).upload(
                path=storage_path,
                file=content,
                file_options={"content-type": "application/pdf"},
            )
            pdf_path = storage_path
            pdf_url = supabase.storage.from_(BUCKET_NAME).get_public_url(storage_path)

    parsed_date = None
    if event_date:
        try:
            date.fromisoformat(event_date)
            parsed_date = event_date
        except ValueError:
            parsed_date = None

    supabase.table("portfolio_items").insert(
        {
            "user_id": user["id"],
            "category": category,
            "title": title.strip(),
            "description": description.strip() or None,
            "extra_info": extra_info.strip() or None,
            "event_date": parsed_date,
            "pdf_url": pdf_url,
            "pdf_path": pdf_path,
        }
    ).execute()

    return RedirectResponse(url=f"/?category={category}", status_code=303)


@app.post("/items/{item_id}/delete")
async def delete_item(request: Request, item_id: str, category: str = Form("own_achievements")):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    res = (
        supabase.table("portfolio_items")
        .select("*")
        .eq("id", item_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if res.data:
        item = res.data[0]
        if item.get("pdf_path"):
            try:
                supabase.storage.from_(BUCKET_NAME).remove([item["pdf_path"]])
            except Exception:
                pass
        supabase.table("portfolio_items").delete().eq("id", item_id).eq("user_id", user["id"]).execute()

    return RedirectResponse(url=f"/?category={category}", status_code=303)