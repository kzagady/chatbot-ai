from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from openai import OpenAI
import os
import json
import uuid
from datetime import datetime

# OpenAI klient
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

# Zezwól na wszystkie połączenia (np. z index.html)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CHATS_DIR = "chats"
os.makedirs(CHATS_DIR, exist_ok=True)

# ======= FUNKCJE POMOCNICZE =======

def chat_file_path(chat_id):
    return os.path.join(CHATS_DIR, f"{chat_id}.json")

def load_chat(chat_id):
    path = chat_file_path(chat_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return [{"role": "system", "content": "Jesteś pomocnym i przyjacielskim asystentem."}]

def save_chat(chat_id, history):
    with open(chat_file_path(chat_id), "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# ======= ENDPOINTY API =======

@app.post("/new-chat")
def new_chat():
    chat_id = str(uuid.uuid4())
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = f"Nowa rozmowa {now}"
    history = [
        {"role": "system", "content": "Jesteś pomocnym i przyjacielskim asystentem."},
        {"meta": {"title": title, "created": now}}
    ]
    save_chat(chat_id, history)
    return {"chat_id": chat_id, "title": title}

@app.get("/chats")
def list_chats():
    files = os.listdir(CHATS_DIR)
    chats = []
    for file in files:
        if file.endswith(".json"):
            chat_id = file.replace(".json", "")
            path = chat_file_path(chat_id)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                meta = next((m for m in data if "meta" in m), {})
                title = meta.get("meta", {}).get("title", "Bez tytułu")
                created = meta.get("meta", {}).get("created", "Brak daty")
                chats.append({
                    "chat_id": chat_id,
                    "title": title,
                    "created": created
                })
    return sorted(chats, key=lambda x: x["created"], reverse=True)

@app.get("/load-chat/{chat_id}")
def get_chat(chat_id: str):
    return load_chat(chat_id)

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_message = data.get("message")
    chat_id = data.get("chat_id")

    if not chat_id:
        return {"error": "Brakuje chat_id"}

    history = load_chat(chat_id)
    history = [m for m in history if "role" in m]

    history.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=history
    )

    reply = response.choices[0].message.content
    history.append({"role": "assistant", "content": reply})

    # Przywróć metadane
    full_history = load_chat(chat_id)
    meta = [m for m in full_history if "meta" in m]
    save_chat(chat_id, meta + history)

    return {"reply": reply}

@app.post("/rename-chat")
def rename_chat(data: dict):
    chat_id = data.get("chat_id")
    new_title = data.get("title")

    if not chat_id or not new_title:
        return {"error": "Brakuje chat_id lub title"}

    path = chat_file_path(chat_id)
    if not os.path.exists(path):
        return {"error": "Nie znaleziono rozmowy"}

    with open(path, "r", encoding="utf-8") as f:
        content = json.load(f)

    for item in content:
        if "meta" in item:
            item["meta"]["title"] = new_title

    save_chat(chat_id, content)
    return {"success": True, "chat_id": chat_id, "new_title": new_title}

@app.delete("/delete-chat/{chat_id}")
def delete_chat(chat_id: str):
    path = chat_file_path(chat_id)
    if os.path.exists(path):
        os.remove(path)
        return JSONResponse(content={"success": True, "deleted": chat_id})
    return JSONResponse(content={"error": "Rozmowa nie istnieje"}, status_code=404)

# ======= STRONA STARTOWA (index.html) =======

@app.get("/")
def serve_index():
    return FileResponse("index.html")
