# Joy Girl - Render.com Deployment Guide

## Why Render Instead of Hugging Face?

**Hugging Face Free Spaces CANNOT connect to external APIs** like Telegram due to DNS resolution restrictions. You get errors like:
```
[Errno -5] No address associated with hostname
```

**Render.com Free Tier ALLOWS external API calls** and works perfectly with Telegram!

---

## Step-by-Step Deployment

### Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. Create a new repository called `joy-girl-api`
3. Make it **Private** (recommended for security)
4. Don't initialize with README

### Step 2: Push Code to GitHub

```bash
# Navigate to the render-backend folder
cd /home/z/my-project/joy-girl-ultimate/render-backend

# Initialize git
git init

# Add all files
git add .

# Commit
git commit -m "Initial Joy Girl API"

# Add your GitHub remote (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/joy-girl-api.git

# Push
git branch -M main
git push -u origin main
```

### Step 3: Deploy on Render.com

1. Go to https://dashboard.render.com/
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub account
4. Select the `joy-girl-api` repository
5. Configure:
   - **Name**: `joy-girl-api` (or any name you want)
   - **Region**: Choose closest to you
   - **Branch**: `main`
   - **Root Directory**: Leave blank
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: `Free`

6. **IMPORTANT**: Add Environment Variables (click "Advanced"):
   | Key | Value |
   |-----|-------|
   | `DEEPSEEK_API_KEY` | Your DeepSeek API key |
   | `TELEGRAM_BOT_TOKEN` | Your Telegram bot token from @BotFather |
   | `TELEGRAM_CHAT_ID` | `7662478522` (your chat ID) |

7. Click **"Deploy Web Service"**

### Step 4: Wait for Deployment

- Render will build and deploy your service
- This takes 2-5 minutes
- Once done, you'll get a URL like: `https://joy-girl-api.onrender.com`

### Step 5: Set Telegram Webhook

After deployment is complete, open this URL in your browser:

```
https://YOUR-APP-NAME.onrender.com/telegram/setWebhook?webhook_url=https://YOUR-APP-NAME.onrender.com/telegram/webhook
```

Replace `YOUR-APP-NAME` with your actual Render app name.

You should see:
```json
{"ok": true, "result": true, "description": "Webhook was set"}
```

### Step 6: Test the Integration

1. **Test the API root:**
   ```
   https://YOUR-APP-NAME.onrender.com/
   ```
   Should return:
   ```json
   {"status": "Joy Girl API", "version": "4.0.0", ...}
   ```

2. **Test Telegram notification:**
   ```
   https://YOUR-APP-NAME.onrender.com/telegram/notify
   ```
   (Make a POST request or use curl)
   You should receive a Telegram message!

### Step 7: Update ESP32 Config

Edit `/home/z/my-project/joy-girl-ultimate/esp32-firmware/include/config.h`:

```cpp
#define BACKEND_HOST "your-app-name.onrender.com"  // Your Render URL
```

### Step 8: Flash ESP32

```bash
cd /home/z/my-project/joy-girl-ultimate/esp32-firmware
pio run -t upload
```

---

## Quick Test Commands

```bash
# Test if API is running
curl https://your-app-name.onrender.com/

# Test notification (should send Telegram message)
curl -X POST https://your-app-name.onrender.com/telegram/notify

# Check webhook status
curl https://your-app-name.onrender.com/telegram/webhookInfo
```

---

## Troubleshooting

### "Service Unavailable" or 502 Error
- Wait a few minutes - free tier services sleep after inactivity
- First request wakes up the service (takes ~30 seconds)

### Telegram not receiving messages
1. Check environment variables are set correctly
2. Check logs in Render dashboard
3. Verify webhook is set correctly

### ESP32 Connection Errors
1. Make sure WiFi credentials are correct
2. Make sure BACKEND_HOST is updated correctly
3. Check Render service is running

---

## Your Configuration

- **Telegram Chat ID**: `7662478522`
- **Telegram Bot**: Already created
- **DeepSeek API**: You have the key
- **Render Free Tier**: 750 hours/month (enough for 24/7)

---

## File Structure

```
render-backend/
├── app.py           # FastAPI application
├── requirements.txt # Python dependencies
└── render.yaml      # Render configuration (optional)
```

The free tier works perfectly for this project! 🎉
