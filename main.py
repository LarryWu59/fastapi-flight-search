from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests
import csv
from io import StringIO
from datetime import datetime
import os

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ===== 預先抓取航空公司英文 + 中文對照表 =====
chinese_name_map = {
    "BR": "長榮航空",
    "CI": "中華航空",
    "JL": "日本航空",
    "NH": "全日空",
    "UA": "美國聯合航空",
    "DL": "達美航空",
    "AA": "美國航空",
    "TR": "酷航",
    "SL": "泰國獅子航空",
    "KE": "大韓航空",
    "OZ": "韓亞航空",
    "CX": "國泰航空",
    "SQ": "新加坡航空"
}

def get_airline_map():
    url = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat"
    res = requests.get(url)
    reader = csv.reader(StringIO(res.text))
    airline_map = {}
    for row in reader:
        if len(row) < 8:
            continue
        iata = row[3]
        name_en = row[1]
        country = row[6]
        active = row[7]
        if iata and active == "Y":
            airline_map[iata] = {
                "name_en": name_en,
                "name_zh": chinese_name_map.get(iata, ""),
                "country": country
            }
    return airline_map

airline_iata_map = get_airline_map()

def extract_airline_code_from_link(link: str) -> str:
    if "t=" in link:
        token = link.split("t=")[1]
        return token[:2]
    return ""

# ===== 查詢機票資料 =====
def get_flights(origin: str, destination: str, departure_month: str):
    url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
    params = {
        "origin": origin,
        "destination": destination,
        "departure_at": departure_month,
        "currency": "TWD",
        "token": os.getenv("TP_API_TOKEN", "0660b86f98cd4952631c049228bd4bad")
    }
    res = requests.get(url, params=params)
    data = res.json()
    results = []
    for flight in data.get("data", []):
        try:
            dep_time = datetime.fromisoformat(flight["departure_at"])
            if 0 <= dep_time.hour < 6:
                continue  # 過濾紅眼班
            flight_number = flight.get("flight_number", "")
            link = flight.get("link", "")
            airline_code = extract_airline_code_from_link(link)
            airline_info = airline_iata_map.get(airline_code, {"name_en": "未知航空", "name_zh": ""})
            results.append({
                "price": flight["price"],
                "flight_number": flight_number,
                "departure_at": flight["departure_at"],
                "airline_en": airline_info["name_en"],
                "airline_zh": airline_info["name_zh"]
            })
        except:
            continue
    return results

# ===== 路由：首頁表單 =====
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# ===== 路由：查詢結果 =====
@app.post("/search", response_class=HTMLResponse)
def search(request: Request,
           origin: str = Form(...),
           destination: str = Form(...),
           month: str = Form(...)):
    flights = get_flights(origin.upper(), destination.upper(), month)
    return templates.TemplateResponse("results.html", {"request": request, "flights": flights})

