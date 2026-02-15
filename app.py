"""
Joy Girl API - Render.com Backend
Uses Groq API (free tier) or DeepSeek API for AI responses
Works with Telegram Bot webhook
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import tempfile
from typing import List
from datetime import datetime

app = FastAPI(title="Joy Girl API", version="4.1.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration - Try Groq first (free), fallback to DeepSeek
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Joy Girl personality
JOY_GIRL_SYSTEM = """You are Joy Girl, a cheerful, friendly AI assistant.
You live in a cute ESP32 device with a tiny OLED screen.
Keep responses SHORT (under 40 words) - the screen is small!
Be enthusiastic and helpful. Use emojis sometimes."""

# Store recent messages for ESP32
recent_messages: List[dict] = []
MAX_MESSAGES = 20
notification_sent_time = None
waiting_for_reply = False

class ChatRequest(BaseModel):
    message: str
    max_tokens: int = 60

async def get_ai_response(prompt: str, max_tokens: int = 60) -> str:
    """Get response from Groq API (free) or DeepSeek API"""
    
    # Try Groq first (free tier)
    if GROQ_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": GROQ_MODEL,
                        "messages": [
                            {"role": "system", "content": JOY_GIRL_SYSTEM},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": max_tokens,
                        "temperature": 0.7
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    print(f"Groq error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Groq error: {e}")
    
    # Fallback to DeepSeek
    if DEEPSEEK_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": DEEPSEEK_MODEL,
                        "messages": [
                            {"role": "system", "content": JOY_GIRL_SYSTEM},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": max_tokens,
                        "temperature": 0.7
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    print(f"DeepSeek error: {response.status_code} - {response.text}")
                    return "Sorry, my brain glitched!"
        except Exception as e:
            print(f"DeepSeek error: {e}")
            return "Oops! Connection error!"
    
    return "Error: No AI API key configured!"

async def send_telegram_message(chat_id: str, text: str):
    if not TELEGRAM_BOT_TOKEN:
        return False
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
            )
            return response.status_code == 200
        except:
            return False

@app.get("/")
async def root():
    ai_provider = "Groq" if GROQ_API_KEY else ("DeepSeek" if DEEPSEEK_API_KEY else "None")
    return {"status": "Joy Girl API", "version": "4.1.0", "ai": ai_provider}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/telegram/notify")
async def send_notification():
    global notification_sent_time, waiting_for_reply
    
    message = """🌸 <b>Joy Girl detected you!</b>

Reply to this message to chat!
💡 Your message will appear on Joy Girl's OLED screen!"""

    success = await send_telegram_message(TELEGRAM_CHAT_ID, message)
    if success:
        notification_sent_time = datetime.now()
        waiting_for_reply = True
        return {"ok": True, "message": "Notification sent!"}
    return {"ok": False, "error": "Failed to send"}

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    global waiting_for_reply
    try:
        update = await request.json()
        if "message" not in update:
            return {"status": "ignored"}

        message = update["message"]
        chat_id = str(message["chat"]["id"])
        from_user = message.get("from", {}).get("first_name", "User")
        message_id = message.get("message_id", 0)

        user_text = ""
        if "text" in message:
            user_text = message["text"]
            if user_text.startswith("/"):
                return {"status": "command"}
        else:
            return {"status": "unsupported"}

        joy_girl_response = await get_ai_response(user_text)
        await send_telegram_message(chat_id, f"🌸 {joy_girl_response}")

        msg = {
            "id": message_id,
            "text": user_text,
            "from_user": from_user,
            "timestamp": datetime.now().isoformat(),
            "response": joy_girl_response
        }
        recent_messages.append(msg)
        if len(recent_messages) > MAX_MESSAGES:
            recent_messages.pop(0)
        waiting_for_reply = False
        return {"status": "ok", "response": joy_girl_response}
    except Exception as e:
        print(f"Webhook error: {e}")
        return {"status": "error", "detail": str(e)}

@app.get("/messages")
async def get_messages(limit: int = 5, since_id: int = 0):
    filtered = [m for m in recent_messages if m["id"] > since_id]
    messages = filtered[-limit:] if filtered else []
    return {"messages": messages, "count": len(messages)}

@app.get("/telegram/setWebhook")
async def set_webhook(webhook_url: str):
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook",
            json={"url": webhook_url}
        )
        return response.json()

@app.get("/telegram/webhookInfo")
async def get_webhook_info():
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"
        )
        return response.json()

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
