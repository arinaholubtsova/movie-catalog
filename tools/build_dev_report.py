from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "Movie_Catalog_Development_Testing_Refactoring_Holubtsova.docx"


def border(cell):
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right"):
        element = borders.find(qn(f"w:{edge}"))
        if element is None:
            element = OxmlElement(f"w:{edge}")
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "4")
        element.set(qn("w:color"), "D9D9D9")


def shade(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def table(doc, headers, rows, widths):
    t = doc.add_table(rows=1, cols=len(headers))
    t.autofit = False
    t.style = "Table Grid"
    for i, (header, width) in enumerate(zip(headers, widths)):
        t.columns[i].width = Inches(width)
        t.rows[0].cells[i].text = header
        shade(t.rows[0].cells[i], "DDE7F4")
    for row in rows:
        cells = t.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = str(value)
    for row in t.rows:
        for i, cell in enumerate(row.cells):
            border(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cell.width = Inches(widths[i])
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_after = Pt(0)
                for run in paragraph.runs:
                    run.font.size = Pt(8.5)
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(0)
    spacer.paragraph_format.space_before = Pt(0)
    spacer.add_run(" ").font.size = Pt(2)


def body(doc, text):
    p = doc.add_paragraph(text)
    p.paragraph_format.space_after = Pt(4)
    return p


doc = Document()
section = doc.sections[0]
section.top_margin = Inches(.65)
section.bottom_margin = Inches(.65)
section.left_margin = Inches(.85)
section.right_margin = Inches(.85)
styles = doc.styles
styles["Normal"].font.name = "Times New Roman"
styles["Normal"].font.size = Pt(10.5)
styles["Normal"].paragraph_format.line_spacing = 1.08
for name, size in (("Title", 15), ("Heading 1", 13), ("Heading 2", 11.5)):
    style = styles[name]
    style.font.name = "Times New Roman"
    style.font.size = Pt(size)
    style.font.bold = True
    style.font.color.rgb = RGBColor(0, 0, 0)
    style.paragraph_format.space_before = Pt(10)
    style.paragraph_format.space_after = Pt(5)
title_style_ppr = styles["Title"].element.get_or_add_pPr()
title_border = title_style_ppr.find(qn("w:pBdr"))
if title_border is not None:
    title_style_ppr.remove(title_border)

title = doc.add_paragraph(style="Title")
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
title.add_run("Розробка тестування та рефакторинг каталогу фільмів")
p = doc.add_paragraph("Продовження проєкту «Каталог фільмів з адаптивними рекомендаціями на основі попереднього вибору користувача». Розділи 3–4 описують реалізацію оновлених вимог станом на 4 листопада 2026 року, фактичні перевірки та зміни структури коду.")
p.paragraph_format.space_after = Pt(7)
body(doc, "Виконала: Голубцова Орина Євгенівна · Київ, 2026")

doc.add_heading("3. Development", level=1)
doc.add_heading("3.1. Архітектура та середовище", level=2)
body(doc, "Створено клієнт серверний вебзастосунок. React і TypeScript відповідають за каталог, особисті дії та адміністративний інтерфейс. FastAPI надає REST API й OpenAPI документацію. SQLAlchemy 2 реалізує моделі та доступ до даних, Alembic містить початкову міграцію. У Docker Compose застосунок працює з PostgreSQL 16; для локальних автоматизованих тестів використовується ізольована SQLite БД.")
body(doc, "Структура backend розділена на модулі database, models, auth, catalog, interactions, recommendation, schemas і main. Це відповідає схемі з розділу 2: поточні стани Rating, Favorite, Watchlist і Watched зберігаються окремо, а кожна зміна додає історичну подію UserInteraction.")

doc.add_heading("3.2. Реалізовані функції", level=2)
table(doc, ["Вимоги", "Реалізація"], [
    ("FR3.1–FR3.5", "Реєстрація, вхід і вихід; каталог по 20 записів; пошук за назвою й текстом; 13 жанрів, точний рік або діапазон, рейтинг 0–10, сортування, деталі."),
    ("FR3.6–FR3.10", "Оцінка 1–5 із оновленням одного актуального запису; Favorites, Watchlist, Watched; історія подій з часом і значенням."),
    ("FR3.11–FR3.15", "Профіль інтересів, cosine similarity, Top K, виключення watched, cold start, similar movies і пояснення причини."),
    ("FR3.16–FR3.17", "Адміністративне керування фільмами та жанрами; синхронізація з налаштованого JSON джерела з підсумком created, updated, skipped."),
    ("FR3.18–FR3.20", "Зміна email з перевіркою унікальності; зміна пароля після перевірки поточного; видалення профілю після підтвердження з очищенням персональних даних."),
], [1.25, 5.35])

doc.add_heading("3.3. Алгоритм рекомендацій", level=2)
body(doc, "Для фільму формується sparse набір ознак з жанрів, ключових слів, режисерів і до п’яти акторів. Вага взаємодії: 0,60 × max((rating − 3)/2, 0) + 0,25 × Favorite + 0,10 × Watched + 0,05 × Watchlist. Профіль є зваженим середнім ознак фільмів. Candidate score дорівнює cosine similarity; Top K вибирається без повного сортування. Якщо позитивного профілю немає, застосовується рейтинг і кількість оцінок як cold start. Профіль перераховується при кожному запиті, тому наступний запит після підтвердженої зміни використовує актуальний стан.")

doc.add_heading("3.4. Запуск і API", level=2)
body(doc, "Команда docker compose up --build запускає PostgreSQL, backend і frontend. Сторінка доступна на localhost:8080, OpenAPI — на localhost:8080/api/docs. Перед запуском потрібно задати паролі й JWT_SECRET у .env. Для зовнішнього розгортання необхідно додати HTTPS/TLS. На поточній машині застосунок запущено локально з SQLite: frontend на localhost:5174, API на localhost:8000/docs. Скрипт запуску обирає вільний порт frontend.")

doc.add_page_break()
doc.add_heading("4. Testing and Refactoring", level=1)
doc.add_heading("4.1. Автоматизоване тестування", level=2)
body(doc, "Виконано unit та integration тести через pytest і FastAPI TestClient. Тести використовують окрему БД з активними foreign keys для кожного сценарію. Після рефакторингу команда pytest -q завершилась успішно: 15 tests passed. Production build React і TypeScript також завершився успішно. Додатково пройдено наскрізний сценарій у браузері Chrome.")
table(doc, ["Перевірка", "Результат"], [
    ("Пошук, фільтрація, пагінація, деталі", "Склад і порядок результатів відповідають параметрам запиту."),
    ("Auth і роль Administrator", "Відсутній, пошкоджений і прострочений токен, повторна email і звичайний User проти admin API відхиляються; logout відкликає токен."),
    ("Rating, списки, історія", "Оцінка оновлюється без дубля; зміни списків створюють події; повторне додавання не створює зайву подію."),
    ("Рекомендації", "Перевірено математичний профіль, cold start, Top K, спадання score, explanations, виключення watched і оновлення після нової оцінки."),
    ("Admin і sync", "Перевірено CRUD, заборону видалення використаного жанру та підрахунок створених, оновлених і пропущених записів."),
    ("Оновлені вимоги", "Комбіновані фільтри й сторінка з 20 записів; зміна email і пароля; підтвердження видалення, очищення персональних таблиць; інвалідація кешів після змін."),
], [2.1, 4.5])
body(doc, "Покриття саме гілок становить 8/8 (100%) для interactions.py та 33/40 (82,5%) для recommendation.py; сумарний показник statement + branch — 94%. Ціль NFR4.5 ≥80% для обох модулів виконана. Початкова Alembic migration застосована; схема для оновлених функцій змін не потребує. Seed додає 12 демонстраційних фільмів і 13 дозволених жанрів без дублікатів.")

doc.add_heading("4.2. Перевірки нефункціональних вимог", level=2)
table(doc, ["Вимога", "Стан на момент звіту"], [
    ("NFR4.1 Performance", "Фінальний 30-хвилинний тест: P95 пошуку 879,64 мс (ціль 800 мс не виконана); рекомендацій 954,22 мс (ціль 1200 мс виконана локально)."),
    ("NFR4.2 Security", "Автоматичні негативні тести автентифікації та ролей пройдено. TLS потребує конфігурації під час зовнішнього розгортання."),
    ("NFR4.3 Reliability", "1800,20 с без перерв; 124 241 HTTP 200, один обрив з’єднання, 0 HTTP 5xx. 80 підтверджених записів, 0 розбіжностей. Локальні критерії виконано."),
    ("NFR4.4 Usability", "П’ять автоматизованих браузерних сесій пройшли чотири сценарії; реальних учасників немає, тому людська метрика не виміряна."),
    ("NFR4.5 Maintainability", "Модулі розділено; покриття гілок: interactions 100%, recommendation 82,5%."),
], [1.75, 4.85])

doc.add_heading("4.3. Рефакторинг", level=2)
body(doc, "Логіку rating і персональних списків винесено з HTTP маршрутів до окремого модуля. Поточний стан і UserInteraction змінюються в одній транзакції. Перерахунок рейтингу на шкалі 0–10 використовує одну функцію. Пошук винесено в catalog.py з обмеженим кешем сторінок; рекомендації кешують готові Top-K та очищують кеш після змін користувача й каталогу. Порівняно з початковим 30-хвилинним запуском 4 листопада P95 пошуку знизився з 1197,90 до 879,64 мс, рекомендацій — з 1712,28 до 954,22 мс. Локальний запуск перевіряє порт в IPv4 й IPv6.")

doc.add_heading("4.4. Підсумок", level=2)
body(doc, "Реалізовано FR3.1–FR3.20. П’ятнадцять автоматичних тестів, збірка, браузерний сценарій і локальна перевірка надійності пройшли. Пошук усе ще перевищує ціль P95 на 79,64 мс; результати Windows/SQLite не є перевіркою на PostgreSQL 16 і 2 vCPU/4 GB RAM. NFR4.4 потребує п’яти реальних учасників. Повні протоколи й обмеження наведено в reports/TEST_RESULTS_2026-11-04.md.")

footer = section.footer.paragraphs[0]
footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
footer.add_run("Каталог фільмів · Розділи 3–4")
doc.save(OUTPUT)
print(OUTPUT)
