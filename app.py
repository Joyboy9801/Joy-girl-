"""
Joy Girl API - Render.com Backend
Uses DeepSeek API for AI responses
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

app = FastAPI(title="Joy Girl API", version="4.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration - DeepSeek API
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

# ============== MODELS ==============

class ChatRequest(BaseModel):
    message: str
    max_tokens: int = 60

# ============== AI RESPONSE (DeepSeek) ==============

async def get_ai_response(prompt: str, max_tokens: int = 60) -> str:
    """Get response from DeepSeek API"""

    if not DEEPSEEK_API_KEY:
        return "Error: DEEPSEEK_API_KEY not set"

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
        print(f"AI error: {e}")
        return "Oops! Connection error!"

# ============== HELPER FUNCTIONS ==============

def chunk_text(text: str, max_chunk_size: int = 120) -> List[str]:
    """Split text into OLED-friendly chunks"""
    chunks = []
    words = text.split()
    current_chunk = ""

    for word in words:
        if len(current_chunk) + len(word) + 1 <= max_chunk_size:
            current_chunk += (" " if current_chunk else "") + word
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = word

    if current_chunk:
        chunks.append(current_chunk)

    return chunks

async def send_telegram_message(chat_id: str, text: str):
    """Send message to Telegram"""
    if not TELEGRAM_BOT_TOKEN:
        print("Telegram error: BOT_TOKEN not set")
        return False

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML"
                }
            )
            print(f"Telegram send response: {response.status_code}")
            return response.status_code == 200
        except Exception as e:
            print(f"Telegram send error: {e}")
            return False

async def download_telegram_file(file_id: str) -> bytes:
    """Download file from Telegram"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        file_info = await client.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
        )
        file_data = file_info.json()

        if not file_data.get("ok"):
            raise Exception("Could not get file info")

        file_path = file_data["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        file_response = await client.get(file_url)

        return file_response.content

async def transcribe_audio(audio_data: bytes) -> str:
    """Transcribe audio using OpenAI Whisper (optional)"""

    openai_key = os.getenv("OPENAI_API_KEY", "")

    if openai_key:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
                    f.write(audio_data)
                    temp_path = f.name

                with open(temp_path, "rb") as f:
                    response = await client.post(
                        "https://api.openai.com/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {openai_key}"},
                        files={"file": ("audio.ogg", f, "audio/ogg")},
                        data={"model": "whisper-1"}
                    )

                os.unlink(temp_path)

                if response.status_code == 200:
                    return response.json().get("text", "")
        except Exception as e:
            print(f"Whisper error: {e}")

    return "Hello Joy Girl"

# ============== ENDPOINTS ==============

@app.get("/")
async def root():
    return {
        "status": "Joy Girl API",
        "version": "4.0.0",
        "platform": "Render.com",
        "ai": "DeepSeek",
        "flow": "IR → Telegram → OLED"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

# ============== IR TRIGGER ==============

@app.post("/telegram/notify")
async def send_notification():
    """Called by ESP32 when IR detects motion"""
    global notification_sent_time, waiting_for_reply

    if not TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN not set")

    if not TELEGRAM_CHAT_ID:
        raise HTTPException(status_code=500, detail="TELEGRAM_CHAT_ID not set")

    message = """🌸 <b>Joy Girl detected you!</b>

Reply to this message to chat!
You can send text or voice message.

💡 Your message will appear on Joy Girl's OLED screen!"""

    success = await send_telegram_message(TELEGRAM_CHAT_ID, message)

    if success:
        notification_sent_time = datetime.now()
        waiting_for_reply = True
        return {
            "ok": True,
            "message": "Notification sent!",
            "timestamp": notification_sent_time.isoformat()
        }
    else:
        return {"ok": False, "error": "Failed to send"}

# ============== TELEGRAM WEBHOOK ==============

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Handle incoming Telegram messages"""
    global waiting_for_reply

    try:
        update = await request.json()
        print(f"Received webhook: {update}")

        if "message" not in update:
            return {"status": "ignored"}

        message = update["message"]
        chat_id = str(message["chat"]["id"])
        from_user = message.get("from", {}).get("first_name", "User")
        message_id = message.get("message_id", 0)

        user_text = ""
        message_type = "text"

        # Handle text
        if "text" in message:
            user_text = message["text"]

            if user_text.startswith("/"):
                if user_text == "/start":
                    await send_telegram_message(chat_id,
                        "🌸 Hi! I'm Joy Girl! Wave your hand over the IR sensor to chat!")
                return {"status": "command"}

        # Handle voice
        elif "voice" in message:
            message_type = "voice"
            voice = message["voice"]
            file_id = voice["file_id"]

            await send_telegram_message(chat_id, "🎧 Processing voice...")

            try:
                audio_data = await download_telegram_file(file_id)
                user_text = await transcribe_audio(audio_data)
            except Exception as e:
                print(f"Voice error: {e}")
                user_text = "I couldn't hear clearly"

            await send_telegram_message(chat_id, f"📝 You said: \"{user_text}\"")

        else:
            return {"status": "unsupported"}

        # Get AI response
        joy_girl_response = await get_ai_response(user_text)

        # Send to Telegram
        await send_telegram_message(chat_id, f"🌸 {joy_girl_response}")

        # Store for ESP32
        msg_for_esp32 = {
            "id": message_id,
            "text": user_text,
            "from_user": from_user,
            "timestamp": datetime.now().isoformat(),
            "response": joy_girl_response,
            "type": message_type
        }

        recent_messages.append(msg_for_esp32)

        if len(recent_messages) > MAX_MESSAGES:
            recent_messages.pop(0)

        waiting_for_reply = False

        return {"status": "ok", "response": joy_girl_response}

    except Exception as e:
        print(f"Webhook error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "detail": str(e)}

# ============== ESP32 POLLING ==============

@app.get("/messages")
async def get_messages(limit: int = 5, since_id: int = 0):
    """ESP32 polls for new messages"""
    filtered = [m for m in recent_messages if m["id"] > since_id]
    messages = filtered[-limit:] if filtered else []

    return {
        "messages": messages,
        "count": len(messages),
        "total": len(recent_messages),
        "waiting": waiting_for_reply
    }

@app.get("/messages/latest")
async def get_latest_message():
    if recent_messages:
        return recent_messages[-1]
    return {"message": None}

@app.delete("/messages")
async def clear_messages():
    recent_messages.clear()
    return {"status": "cleared"}

# ============== TELEGRAM SETUP ==============

@app.get("/telegram/setWebhook")
async def set_telegram_webhook(webhook_url: str):
    """Set Telegram webhook URL"""
    if not TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN not set")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook",
            json={"url": webhook_url}
        )
        result = response.json()
        print(f"SetWebhook result: {result}")
        return result

@app.get("/telegram/info")
async def get_telegram_info():
    if not TELEGRAM_BOT_TOKEN:
        return {"error": "TELEGRAM_BOT_TOKEN not set"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
        )
        return response.json()

@app.get("/telegram/webhookInfo")
async def get_webhook_info():
    if not TELEGRAM_BOT_TOKEN:
        return {"error": "TELEGRAM_BOT_TOKEN not set"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"
        )
        return response.json()

# ============== CHAT ENDPOINTS ==============

@app.post("/chat")
async def chat(request: ChatRequest):
    response = await get_ai_response(request.message, request.max_tokens)
    return {"response": response}

@app.post("/chat/esp32")
async def chat_esp32(request: ChatRequest):
    response = await get_ai_response(request.message, request.max_tokens)
    chunks = chunk_text(response)

    return {
        "chunks": chunks,
        "total_chunks": len(chunks),
        "full_text": response
    }

# Run with: uvicorn app:app --host 0.0.0.0 --port $PORT
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
