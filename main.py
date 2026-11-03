from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import openpyxl
import os
import random
import re
from datetime import datetime

app = FastAPI()

DATA_FILE = "submissions.xlsx"

def init_excel():
    if not os.path.exists(DATA_FILE):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Participants"
        ws.append(["Timestamp", "Name", "Age", "Parent Phone"])
        wb.save(DATA_FILE)

init_excel()

# Функция для очистки и валидации телефона на сервере
def normalize_phone(phone_str):
    if not phone_str:
        return None
    
    # Удаляем все кроме цифр и плюса
    cleaned = re.sub(r'[^\d+]', '', phone_str)
    
    # Проверяем длину и начало
    # Допускаем: +7XXXXXXXXXX, 7XXXXXXXXXX, 8XXXXXXXXXX
    if len(cleaned) == 11 and (cleaned.startswith('+7') or cleaned.startswith('7') or cleaned.startswith('8')):
        return cleaned
    elif len(cleaned) == 10 and cleaned[0] != '+':
        # Если человек написал просто 9991234567, добавляем 7
        return '7' + cleaned
        
    return None # Неверный формат

@app.post("/api/submit")
async def submit_form(request: Request):
    data = await request.json()
    name = data.get("name")
    age = data.get("age")
    raw_phone = data.get("phone")
    
    if not all([name, age, raw_phone]):
        return JSONResponse(status_code=400, content={"message": "Missing fields"})

    # Валидация и нормализация телефона
    valid_phone = normalize_phone(raw_phone)
    if not valid_phone:
        return JSONResponse(status_code=400, content={"message": "Invalid phone format"})

    try:
        wb = openpyxl.load_workbook(DATA_FILE)
        ws = wb.active
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Записываем нормализованный номер (только цифры/плюс), чтобы в Excel было чисто
        ws.append([timestamp, name, int(age), valid_phone])
        wb.save(DATA_FILE)
        return {"status": "success"}
    except Exception as e:
        print(f"Error saving to excel: {e}")
        return JSONResponse(status_code=500, content={"message": "Internal Server Error"})

PRIZES = [
    {"id": 1, "name": "Бесплатный мастер класс", "weight": 10},  
    {"id": 2, "name": "Брелок", "weight": 30},                  
    {"id": 3, "name": "Наклейки", "weight": 40},                
    {"id": 4, "name": "3D стикер", "weight": 15},               
    {"id": 5, "name": "Пробный урок барабаны", "weight": 5}     
]

@app.get("/api/spin")
async def get_spin_result():
    weights = [p["weight"] for p in PRIZES]
    chosen_prize = random.choices(PRIZES, weights=weights)[0]
    return {"prize_id": chosen_prize["id"], "prize_name": chosen_prize["name"]}

app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)