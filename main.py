from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
import sqlite3
import random
import re
import os
from datetime import datetime

app = FastAPI()

# --- НАСТРОЙКИ БАЗЫ ДАННЫХ ---
DB_NAME = "participants.db"

def init_db():
    """Создает таблицы, если их нет"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Таблица участников
    c.execute('''CREATE TABLE IF NOT EXISTS participants
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  timestamp TEXT, 
                  name TEXT, 
                  age INTEGER, 
                  phone TEXT UNIQUE)''')
    
    # Новая таблица для хранения выигрышей
    # Связываем по номеру телефона, так как это уникальный идентификатор пользователя в нашей системе
    c.execute('''CREATE TABLE IF NOT EXISTS winners
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  participant_phone TEXT,
                  prize_name TEXT,
                  win_timestamp TEXT)''')
                  
    conn.commit()
    conn.close()

# Вызываем инициализацию при старте приложения
init_db()

# --- ФУНКЦИИ ВАЛИДАЦИИ ---
def normalize_phone(phone_str):
    if not phone_str:
        return None
    
    # Удаляем все кроме цифр и плюса
    cleaned = re.sub(r'[^\d+]', '', str(phone_str))
    
    # Проверяем формат +7/7/8 + 10 цифр
    if len(cleaned) == 11 and (cleaned.startswith('+7') or cleaned.startswith('7') or cleaned.startswith('8')):
        return cleaned
    elif len(cleaned) == 10 and cleaned[0] != '+':
        return '7' + cleaned
        
    return None

# --- API ДЛЯ РЕГИСТРАЦИИ ---
@app.post("/api/submit")
async def submit_form(request: Request):
    data = await request.json()
    name = data.get("name")
    age = data.get("age")
    raw_phone = data.get("phone")
    
    if not all([name, age, raw_phone]):
        return JSONResponse(status_code=400, content={"message": "Missing fields"})

    valid_phone = normalize_phone(raw_phone)
    if not valid_phone:
        return JSONResponse(status_code=400, content={"message": "Invalid phone format"})

    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Используем INSERT OR IGNORE, чтобы не создавать дубликатов, если человек уже регистрировался
        # Но для нашего случая лучше просто обновлять имя/возраст, если телефон тот же
        c.execute("""INSERT INTO participants (timestamp, name, age, phone) VALUES (?, ?, ?, ?)
                     ON CONFLICT(phone) DO UPDATE SET name=excluded.name, age=excluded.age""",
                  (timestamp, name, int(age), valid_phone))
        
        conn.commit()
        conn.close()
        
        return {"status": "success"}
    except Exception as e:
        print(f"Error saving to db: {e}")
        return JSONResponse(status_code=500, content={"message": "Internal Server Error"})

# --- ЛОГИКА РУЛЕТКИ (Анти-тильт) ---

# Глобальная переменная для счетчика неудачных попыток
non_main_streak = 0

# Список призов. 
PRIZES = [
    {"id": 1, "name": "Бесплатный мастер класс", "base_weight": 60},  
    {"id": 2, "name": "Брелок", "base_weight": 10},                  
    {"id": 3, "name": "Наклейки", "base_weight": 10},                
    {"id": 4, "name": "3D стикер", "base_weight": 10},               
    {"id": 5, "name": "Секретный приз", "base_weight": 10}     
]

@app.get("/api/spin")
async def get_spin_result(request: Request):
    global non_main_streak
    
    # Получаем телефон из query параметров (фронтенд должен передавать его после регистрации)
    # В script.js мы будем добавлять &phone=... к запросу /api/spin
    user_phone_raw = request.query_params.get("phone")
    user_phone = normalize_phone(user_phone_raw) if user_phone_raw else None

    # Подготавливаем списки весов и индексов для выбора
    current_weights = []
    prize_indices = []
    
    for i, p in enumerate(PRIZES):
        weight = p["base_weight"]
        
        # ЛОГИКА АНТИ-ТИЛЬТА:
        if p["id"] == 1 and non_main_streak > 0:
            weight += (non_main_streak * 20)
            
        current_weights.append(weight)
        prize_indices.append(i)
    
    # Выбираем случайный индекс на основе взвешенных вероятностей
    chosen_index = random.choices(prize_indices, weights=current_weights, k=1)[0]
    chosen_prize = PRIZES[chosen_index]
    
    # Обновляем счетчик для следующего круга
    if chosen_prize["id"] == 1:
        non_main_streak = 0
    else:
        non_main_streak += 1
        
    # ЗАПИСЬ ВЫИГРЫША В БАЗУ ДАННЫХ
    if user_phone:
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            win_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute("INSERT INTO winners (participant_phone, prize_name, win_timestamp) VALUES (?, ?, ?)",
                      (user_phone, chosen_prize["name"], win_time))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error saving winner: {e}")
            # Не блокируем ответ пользователю, даже если запись в лог не прошла
            
    return {
        "prize_id": chosen_prize["id"], 
        "prize_name": chosen_prize["name"]
    }

# --- АДМИН ПАНЕЛЬ (Защищенная паролем) ---

ADMIN_PASSWORD = "SuperSecretWheel2026!" 

@app.get("/admin", response_class=HTMLResponse)
async def view_participants(request: Request):
    key_param = request.query_params.get("key")
    
    if not key_param or key_param != ADMIN_PASSWORD:
        return HTMLResponse(
            "<h1 style='color:red; font-family:sans-serif;'>⛔ Доступ запрещен</h1>"
            "<p>Неверный или отсутствующий ключ доступа.</p>", 
            status_code=403
        )

    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        # Получаем список участников с их последним выигрышем (если есть)
        # JOIN позволяет объединить таблицы participants и winners по телефону
        query = """
            SELECT p.timestamp, p.name, p.age, p.phone, w.prize_name, w.win_timestamp
            FROM participants p
            LEFT JOIN winners w ON p.phone = w.participant_phone
            ORDER BY p.id DESC
        """
        c.execute(query)
        rows = c.fetchall()
        conn.close()

        table_rows_html = ""
        for row in rows:
            reg_time, name, age, phone, prize_name, win_time = row
            
            safe_name = str(name).replace('<', '&lt;').replace('>', '&gt;')
            display_prize = prize_name if prize_name else "-"
            display_win_time = win_time.split()[1] if win_time else "-" # Только время победы

            table_rows_html += f"""
                <tr>
                    <td>{reg_time}</td>
                    <td>{safe_name}</td>
                    <td>{age}</td>
                    <td>{phone}</td>
                    <td style="font-weight:bold; color:{'#E91E63' if prize_name else '#ccc'}">{display_prize}</td>
                    <td>{display_win_time}</td>
                </tr>
            """

        if not table_rows_html:
            table_rows_html = "<tr><td colspan='6' style='text-align:center;'>Данных пока нет</td></tr>"

        css_styles = """
            body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f9; }
            h1 { color: #6a0dad; }
            table { width: 100%; border-collapse: collapse; background: white; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
            th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #ddd; font-size: 0.9rem;}
            th { background-color: #6a0dad; color: white; position: sticky; top: 0; }
            tr:hover { background-color: #f1f1f1; }
            .count { font-weight: bold; color: #E91E63; margin-bottom: 10px; display: block; }
        """

        html_content = f"""
        <html>
        <head>
            <title>Админка: Участники и Призы</title>
            <style>{css_styles}</style>
        </head>
        <body>
            <h1>📋 Реестр участников и выигрышей</h1>
            <span class="count">Всего записей: {len(rows)}</span>
            <table>
                <thead>
                    <tr>
                        <th>Регистрация</th>
                        <th>Имя</th>
                        <th>Возраст</th>
                        <th>Телефон</th>
                        <th>Выигранный приз</th>
                        <th>Время выигрыша</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows_html}
                </tbody>
            </table>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)

    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        return HTMLResponse(f"<h1>Ошибка!</h1><pre>{error_msg}</pre>", status_code=500)

# --- ПОДКЛЮЧЕНИЕ СТАТИКИ ---
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)