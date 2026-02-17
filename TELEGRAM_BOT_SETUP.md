# Telegram AI Business Assistant - Setup Guide

## 🎯 Overview

This bot allows you to query your MySQL database using natural language via Telegram. It uses Google Gemini AI to understand your questions and convert them to SQL queries.

## 📋 Prerequisites

- ✅ Python 3.10+ (You have Python 3.14.3)
- ✅ MySQL database running (Your `ai_demo` database)
- ✅ Telegram account
- ✅ Google Gemini API key

## 🚀 Quick Start

### Step 1: Create Your Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Start a chat and send `/newbot`
3. Follow the prompts:
   - Choose a name (e.g., "My Business Assistant")
   - Choose a username (must end in 'bot', e.g., "mycompany_assistant_bot")
4. **Save the bot token** - you'll need it in Step 3

### Step 2: Install Dependencies

Open PowerShell in the project directory and run:

```powershell
cd d:\spenca\spenca-tesla
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

1. Copy the example environment file:
   ```powershell
   copy .env.example .env
   ```

2. Edit `.env` file and add your credentials:
   - `TELEGRAM_BOT_TOKEN` - Paste the token from BotFather
   - `GEMINI_API_KEY` - Paste your Gemini API key
   - Database settings are already configured

### Step 4: Run the Bot

```powershell
python telegram_bot.py
```

You should see:
```
INFO - Starting Telegram AI Business Assistant Bot...
INFO - Bot is running! Press Ctrl+C to stop.
```

### Step 5: Test the Bot

1. Open Telegram and search for your bot username
2. Start a chat and send `/start`
3. Try asking: "How many employees do we have?"

## 💬 Example Questions

- "How many employees do we have?"
- "Show me all tables in the database"
- "List the last 5 sales transactions"
- "What's in the employees table?"
- "Show me all tasks"

## 🎮 Bot Commands

- `/start` - Welcome message and introduction
- `/help` - Show help and usage examples
- `/schema` - View database structure

## 🔧 Troubleshooting

### Bot doesn't respond
- Check that `telegram_bot.py` is still running
- Verify your bot token in `.env` is correct
- Check internet connection

### Database errors
- Ensure MySQL is running
- Verify database credentials in `.env`
- Check that `ai_demo` database exists

### AI errors
- Verify Gemini API key is valid
- Check internet connection
- Ensure you haven't exceeded API quota

## 🛑 Stopping the Bot

Press `Ctrl+C` in the PowerShell window where the bot is running.

## 🔄 Running Bot 24/7 (Optional)

To keep the bot running even when you close PowerShell:

### Option 1: Use Windows Task Scheduler
1. Create a batch file `start_bot.bat`:
   ```batch
   @echo off
   cd d:\spenca\spenca-tesla
   python telegram_bot.py
   ```
2. Create a scheduled task to run this on startup

### Option 2: Use `pythonw` (runs in background)
```powershell
pythonw telegram_bot.py
```

### Option 3: Deploy to a cloud server (for production)
Consider services like:
- Google Cloud Platform
- AWS EC2
- Azure VM
- DigitalOcean

## 📊 Features

✅ Natural language query processing  
✅ Automatic SQL generation via Gemini AI  
✅ User-friendly response formatting  
✅ Database schema awareness  
✅ Error handling and logging  
✅ Query transparency (shows SQL used)  

## 🔐 Security Notes

- Never share your `.env` file
- Keep your bot token secret
- The `.env` file is gitignored by default
- Consider using read-only database user for production

## 📝 Next Steps

After testing locally, you might want to:
- Add more advanced query features
- Implement data visualization (charts)
- Add WhatsApp integration
- Set up reminders and notifications
- Deploy to a cloud server for 24/7 availability
