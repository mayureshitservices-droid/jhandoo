import eel
import os
import sys
import subprocess
import webbrowser
import requests
import google.generativeai as genai
import mysql.connector
from config_manager import ConfigManager

# Handle "Engine Mode" for standalone EXE
if "--engine" in sys.argv:
    try:
        import telegram_bot
        telegram_bot.main()
    except Exception as e:
        print(f"ENGINE CRASH: {e}")
    sys.exit(0)

# Initialize Eel
eel.init('web')

# GLOBAL STATE
bot_process = None

# --- Python API exposed to JS ---

@eel.expose
def open_url(url):
    webbrowser.open(url)
    return True

@eel.expose
def validate_full_config():
    config = ConfigManager.load_config()
    errors = []
    
    # 1. Check MySQL
    try:
        conn = mysql.connector.connect(
            host=config.get('MYSQL_HOST', 'localhost'),
            user=config.get('MYSQL_USER', 'root'),
            password=config.get('MYSQL_PASSWORD', ''),
            database=config.get('MYSQL_DATABASE', 'ai_demo'),
            port=int(config.get('MYSQL_PORT', 3306)),
            connect_timeout=3
        )
        if conn.is_connected():
            conn.close()
        else:
            errors.append("Database: Connection failed (is MySQL running?)")
    except Exception as e:
        errors.append(f"Database: {str(e)}")

    # 2. Check Gemini
    gemini_key = config.get('GEMINI_API_KEY')
    if not gemini_key:
        errors.append("Gemini: API Key is missing in Settings.")
    else:
        try:
            genai.configure(api_key=gemini_key)
            # Try to list models as a lightweight check
            genai.list_models()
        except Exception as e:
            errors.append(f"Gemini: Invalid API Key or Network issue ({str(e)})")

    # 3. Check Telegram
    bot_token = config.get('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        errors.append("Telegram: Bot Token is missing in Settings.")
    else:
        try:
            t_url = f"https://api.telegram.org/bot{bot_token}/getMe"
            resp = requests.get(t_url, timeout=5).json()
            if not resp.get('ok'):
                errors.append(f"Telegram: {resp.get('description', 'Invalid token')}")
        except Exception as e:
            errors.append("Telegram: Could not connect to API (Check internet)")

    return {
        "success": len(errors) == 0,
        "errors": errors
    }

@eel.expose
def get_config():
    return ConfigManager.load_config()

@eel.expose
def save_config(new_keys):
    config = ConfigManager.load_config()
    config.update(new_keys)
    ConfigManager.save_config(config)
    return True

@eel.expose
def test_db(db_data):
    try:
        # Save current inputs first to be safe
        config = ConfigManager.load_config()
        config.update(db_data)
        ConfigManager.save_config(config)
        
        conn = mysql.connector.connect(
            host=db_data['MYSQL_HOST'],
            user=db_data['MYSQL_USER'],
            password=db_data['MYSQL_PASSWORD'],
            database=db_data['MYSQL_DATABASE'],
            port=3306,
            connect_timeout=5
        )
        if conn.is_connected():
            conn.close()
            return True
    except Exception as e:
        print(f"DB Connection Error: {e}")
    return False

@eel.expose
def toggle_bot():
    global bot_process
    if bot_process is None:
        # Start the bot engine
        try:
            bot_process = subprocess.Popen(
                [sys.executable, "--engine"],
                stdout=None,
                stderr=None,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            return True
        except Exception as e:
            print(f"Failed to start engine: {e}")
            return False
    else:
        # Stop the bot engine
        bot_process.terminate()
        bot_process = None
        return True

def start_app():
    # Attempt to use Chrome/Edge for a "Chromeless" look
    try:
        eel.start('index.html', size=(1100, 850), mode='edge', block=True)
    except:
        # Fallback to default browser
        eel.start('index.html', size=(1100, 850), block=True)

if __name__ == "__main__":
    start_app()
