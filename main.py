from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import sqlite3
import random
import re
import os
from datetime import datetime

app = FastAPI()

# Имя файла базы данных
DB_NAME = "participants.db"

def init_db():
    """Создает таблицу, если её нет"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS participants
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  timestamp TEXT, 
                  name TEXT, 
                  age INTEGER, 
                  phone TEXT)''')
    conn.commit()
    conn.close()

# Вызываем инициализацию при старте приложения
init_db()

# Функция очистки телефона
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
        
        # Записываем в базу данных
        c.execute("INSERT INTO participants (timestamp, name, age, phone) VALUES (?, ?, ?, ?)",
                  (timestamp, name, int(age), valid_phone))
        conn.commit()
        conn.close()
        
        return {"status": "success"}
    except Exception as e:
        print(f"Error saving to db: {e}")
        return JSONResponse(status_code=500, content={"message": "Internal Server Error"})

PRIZES = [
    {"id": 1, "name": "Бесплатный мастер класс", "weight": 60},  
    {"id": 2, "name": "Брелок", "weight": 10},                  
    {"id": 3, "name": "Наклейки", "weight": 10},                
    {"id": 4, "name": "3D стикер", "weight": 10},               
    {"id": 5, "name": "Секретный приз", "weight": 10}     # ИЗМЕНЕНО НАЗВАНИЕ
]

@app.get("/api/spin")
async def get_spin_result():
    weights = [p["weight"] for p in PRIZES]
    chosen_prize = random.choices(PRIZES, weights=weights)[0]
    return {"prize_id": chosen_prize["id"], "prize_name": chosen_prize["name"]}

# Монтируем статику
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
