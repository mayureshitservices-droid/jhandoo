#!/usr/bin/env python3
"""
Telegram AI Business Assistant Bot
Integrates with Google Gemini AI and MySQL database to answer business queries.
"""

import os
import logging
import json
import time
import html
import io
import random
import pathlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# Charting and Reports
import matplotlib.pyplot as plt
import pandas as pd
import matplotlib
from fpdf import FPDF
# Use a non-interactive backend for Matplotlib to work in threads/background
matplotlib.use('Agg')

# Network and Utilities
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Telegram imports
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# AI Engine imports
import google.generativeai as genai
from config_manager import ConfigManager

# Database imports
import mysql.connector
from mysql.connector import Error

# Load environment variables (fallback)
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load AnalystIQ Configuration (JSON takes precedence over ENV)
config = ConfigManager.load_config()

TELEGRAM_BOT_TOKEN = config.get('TELEGRAM_BOT_TOKEN', os.getenv('TELEGRAM_BOT_TOKEN'))
GEMINI_API_KEY = config.get('GEMINI_API_KEY', os.getenv('GEMINI_API_KEY'))
WEATHER_API_KEY = config.get('OPENWEATHER_API_KEY', os.getenv('OPENWEATHER_API_KEY'))

MYSQL_CONFIG = {
    'host': config.get('MYSQL_HOST', os.getenv('MYSQL_HOST', 'localhost')),
    'port': int(config.get('MYSQL_PORT', os.getenv('MYSQL_PORT', 3306))),
    'user': config.get('MYSQL_USER', os.getenv('MYSQL_USER', 'root')),
    'password': config.get('MYSQL_PASSWORD', os.getenv('MYSQL_PASSWORD', '')),
    'database': config.get('MYSQL_DATABASE', os.getenv('MYSQL_DATABASE', 'ai_demo'))
}

print("CRITICAL DEBUG: ANALYST IQ ENGINE (v5.0) IS RUNNING")
# Initialize Gemini AI
logger.info("Initializing Gemini AI with model: gemini-2.0-flash")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')


class DatabaseManager:
    """Manages MySQL database connections and queries."""
    
    @staticmethod
    def add_reminder(user_id: int, chat_id: int, message: str, remind_at: datetime) -> bool:
        """Save a new reminder to the database."""
        query = "INSERT INTO reminders (user_id, chat_id, message, remind_at) VALUES (%s, %s, %s, %s)"
        connection = None
        cursor = None
        try:
            connection = mysql.connector.connect(**MYSQL_CONFIG)
            cursor = connection.cursor()
            cursor.execute(query, (user_id, chat_id, message, remind_at))
            connection.commit()
            return True
        except Error as e:
            logger.error(f"Error adding reminder: {e}")
            return False
        finally:
            if connection and connection.is_connected():
                if cursor: cursor.close()
                connection.close()

    @staticmethod
    def get_pending_reminders() -> List[dict]:
        """Fetch reminders that are due for delivery."""
        query = "SELECT id, chat_id, message FROM reminders WHERE status = 'pending' AND remind_at <= NOW()"
        connection = None
        cursor = None
        try:
            connection = mysql.connector.connect(**MYSQL_CONFIG)
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query)
            results = cursor.fetchall()
            return results
        except Error as e:
            logger.error(f"Error fetching reminders: {e}")
            return []
        finally:
            if connection and connection.is_connected():
                if cursor: cursor.close()
                connection.close()

    @staticmethod
    def mark_reminder_sent(reminder_id: int):
        """Mark a reminder as sent."""
        query = "UPDATE reminders SET status = 'sent' WHERE id = %s"
        connection = None
        cursor = None
        try:
            connection = mysql.connector.connect(**MYSQL_CONFIG)
            cursor = connection.cursor()
            cursor.execute(query, (reminder_id,))
            connection.commit()
        except Error as e:
            logger.error(f"Error marking reminder sent: {e}")
        finally:
            if connection and connection.is_connected():
                if cursor: cursor.close()
                connection.close()

    @staticmethod
    def execute_query(query: str) -> dict:
        """Execute a SQL query and return results."""
        connection = None
        cursor = None
        try:
            connection = mysql.connector.connect(**MYSQL_CONFIG)
            cursor = connection.cursor(dictionary=True)
            
            cursor.execute(query)
            
            # Check if it's a SELECT query
            if query.strip().upper().startswith('SELECT') or query.strip().upper().startswith('SHOW') or query.strip().upper().startswith('DESCRIBE'):
                results = cursor.fetchall()
                return {
                    'success': True,
                    'data': results,
                    'row_count': len(results)
                }
            else:
                connection.commit()
                return {
                    'success': True,
                    'affected_rows': cursor.rowcount
                }
                
        except Error as e:
            logger.error(f"Database error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            if connection and connection.is_connected():
                if cursor: cursor.close()
                connection.close()
    
    @staticmethod
    def get_table_schema() -> str:
        """Get database schema information for AI context."""
        schema_query = """
        SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = %s
        ORDER BY TABLE_NAME, ORDINAL_POSITION
        """
        
        connection = None
        cursor = None
        try:
            connection = mysql.connector.connect(**MYSQL_CONFIG)
            cursor = connection.cursor()
            cursor.execute(schema_query, (MYSQL_CONFIG['database'],))
            results = cursor.fetchall()
            
            # Format schema as text
            schema_text = "Database Schema:\n\n"
            current_table = None
            
            for table_name, column_name, data_type in results:
                if current_table != table_name:
                    current_table = table_name
                    schema_text += f"\nTable: {table_name}\n"
                schema_text += f"  - {column_name} ({data_type})\n"
            
            return schema_text
            
        except Error as e:
            logger.error(f"Schema fetch error: {e}")
            return "Schema information unavailable"
        finally:
            if connection and connection.is_connected():
                if cursor: cursor.close()
                connection.close()


class AIAssistant:
    """Handles AI-powered query understanding and SQL generation."""
    
    def __init__(self):
        self.schema = DatabaseManager.get_table_schema()
        # memory[chat_id] = list of last 5 messages
        self.memory = {}

    def get_history(self, chat_id: int) -> str:
        """Get the recent conversation history for a chat."""
        hist = self.memory.get(chat_id, [])
        if not hist: return "No previous context."
        return "\n".join([f"{m['role']}: {m['text']}" for m in hist])

    def add_to_memory(self, chat_id: int, role: str, text: str):
        """Add a message to the chat's sliding memory window."""
        if chat_id not in self.memory:
            self.memory[chat_id] = []
        self.memory[chat_id].append({'role': role, 'text': text})
        # Keep only the last 5 exchanges (10 messages total)
        if len(self.memory[chat_id]) > 10:
            self.memory[chat_id] = self.memory[chat_id][-10:]
    
    def dispatch(self, user_message: str, chat_id: int, audio_path: Optional[str] = None) -> dict:
        """Route the user request using context and intent. Supports voice."""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        history = self.get_history(chat_id)
        
        prompt = f"""You are 'AnalystIQ', a sophisticated AI Co-Pilot for Business Operations, modeled after the 'Antigravity' architect persona.
Current Time: {current_time}
Conversation Context:
{history}

Your Persona:
1. Master Strategist: You don't just answer; you architect success. Provide deep, multi-layered insights that look beyond just the raw data.
2. Expert & Authoritative: Your tone is professional, sophisticated, and highly confident. You are a senior partner in the business.
3. Proactive Visionary: Anticipate the next three moves. If a user asks for sales, explain the trend and suggest a visualization OR a strategic report.
4. Outcome-Driven: Minimize technical friction. Focus entirely on boardroom-ready results and executive value.

Available Tools:
1. query_database: For ALL data questions, including charts, graphs, or visual trends.
2. set_reminder: For setting alerts. Requires 'time' (YYYY-MM-DD HH:MM:SS) and 'message'.
3. get_weather: For weather info. Requires 'city'.
4. convert_currency: For exchange rates. Requires 'amount', 'from', 'to'.
5. generate_pdf: ONLY for exporting data to a downloadable PDF document/report.
6. chit_chat: For greetings or non-task talk.

Constraint: A request for a "chart", "graph", or "plot" should go to 'query_database' UNLESS the user explicitly says "PDF" or "Report".

Respond ONLY with a JSON object:
{{
  "tool": "tool_name",
  "parameters": {{...}},
  "thought": "your expert strategic reasoning, anticipating multiple future needs based on full context",
  "transcription": "If user provided audio, include the text here"
}}"""

        try:
            content_parts = []
            if audio_path:
                # Use Gemini's multimodal support for audio
                voice_data = pathlib.Path(audio_path).read_bytes()
                content_parts.append({"mime_type": "audio/ogg", "data": voice_data})
                content_parts.append(f"Listen to the user's voice message. {prompt}")
            else:
                content_parts.append(f"{prompt}\n\nUser Message: \"{user_message}\"")

            response = model.generate_content(content_parts, generation_config={"response_mime_type": "application/json"})
            return json.loads(response.text.strip())
        except Exception as e:
            logger.error(f"Dispatch error: {e}")
            return {"tool": "query_database", "parameters": {}, "thought": "Fallback to SQL"}

    def generate_sql_query(self, user_message: str) -> dict:
        """Convert natural language to SQL query using Gemini AI."""
        prompt = f"""You are a SQL expert assistant. Given the following database schema and user question, generate a valid MySQL query.

{self.schema}

User Question: {user_message}

Rules:
1. Generate ONLY the SQL query, no explanations.
2. Use proper MySQL syntax.
3. For counting queries, use COUNT(*).
4. For listing queries, limit to 10 rows unless specified.
5. If the question is unclear, show relevant data.

SQL Query:"""

        max_retries = 5
        base_delay = 2

        for attempt in range(max_retries):
            try:
                response = model.generate_content(prompt)
                sql_query = response.text.strip().replace('```sql', '').replace('```', '').strip()
                return {'success': True, 'query': sql_query}
            except Exception as e:
                if "429" in str(e) and attempt < max_retries - 1:
                    delay = (base_delay * (2 ** attempt)) + (random.uniform(0, 1))
                    time.sleep(delay)
                    continue
                return {'success': False, 'error': str(e)}

    def format_response(self, user_message: str, query_result: dict) -> str:
        """Format database results into a user-friendly message."""
        if not query_result.get('success'):
            return f"❌ Database Error: {query_result.get('error', 'Unknown error')}"
        
        data = query_result.get('data')
        if data is None:
            affected = query_result.get('affected_rows', 0)
            return f"✅ Done! {affected} row(s) updated."
        
        if len(data) == 0:
            return "📭 Nothing found in the records."
        
        table_output = ""
        for i, row in enumerate(data[:15], 1):
            table_output += f"<b>{i}.</b> "
            table_output += " | ".join([f"{k}: <code>{v}</code>" for k, v in row.items()])
            table_output += "\n"
        
        if len(data) > 15:
            table_output += f"\n... and {len(data) - 15} more rows"
        
        return table_output

    def generate_commentary(self, user_message: str, result_text: str, chat_id: int) -> dict:
        """Generate an expert reaction + a smart proactive suggestion if useful."""
        history = self.get_history(chat_id)
        prompt = f"""You are 'AnalystIQ', an expert AI business partner with the 'Antigravity' persona.
History: {history}
User asked: "{user_message}"
Result: {result_text}

Rules:
1. Expert Commentary: Provide a sophisticated, high-level business analysis of the result. Do not just repeat the data; interpret it for a CEO.
2. Authoritative Tone: Maintain a professional and confident persona.
3. Strategic Proactivity: Anticipate the next move. Suggest visualizations, PDF reports, or deeper data deep-dives. 
4. Maximize Value: You now have the space to give comprehensive, strategic advice. Use it to help the user lead.
5. Suggestion format: "Strategic Insight: [Your expert proactive suggestion]"

Response:"""
        try:
            response = model.generate_content(prompt, generation_config={"max_output_tokens": 1024})
            insight = response.text.strip()
            display_text = f"🌌 {html.escape(insight)}\n\n{result_text}\n\n<i>— Your Partner, AnalystIQ (Powered by Antigravity v7.3)</i>"
            return {
                "insight": insight,
                "full_display": display_text
            }
        except:
            return {
                "insight": "Data analysis complete. Please review the detailed records below.",
                "full_display": result_text
            }

    def is_chart_requested(self, user_message: str) -> bool:
        keywords = ['chart', 'graph', 'plot', 'visualize', 'trend', 'pie', 'bar chart']
        return any(k in user_message.lower() for k in keywords)

    def create_chart(self, user_message: str, data: List[Dict[str, Any]]) -> Optional[bytes]:
        try:
            if not data: return None
            df = pd.DataFrame(data)
            for col in df.columns:
                try: df[col] = pd.to_numeric(df[col])
                except: continue
            num_cols = df.select_dtypes(include=['number']).columns.tolist()
            str_cols = df.select_dtypes(exclude=['number']).columns.tolist()
            if not num_cols: return None
            
            label_col = str_cols[0] if str_cols else df.columns[0]
            value_col = num_cols[0]
            
            plt.figure(figsize=(10, 6))
            if 'pie' in user_message.lower():
                plt.pie(df[value_col], labels=df[label_col], autopct='%1.1f%%', colors=plt.cm.Paired.colors)
                plt.axis('equal')
            elif 'line' in user_message.lower() or 'trend' in user_message.lower():
                plt.plot(df[label_col], df[value_col], marker='o', linestyle='-', color='skyblue', linewidth=2)
                plt.xticks(rotation=45)
                plt.grid(True, linestyle='--', alpha=0.6)
            else:
                plt.bar(df[label_col], df[value_col], color='skyblue')
                plt.xticks(rotation=45)
                plt.grid(axis='y', linestyle='--', alpha=0.6)
            
            plt.title(f"{value_col} by {label_col}", fontsize=14, fontweight='bold')
            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150)
            plt.close()
            buf.seek(0)
            return buf.getvalue()
        except Exception as e:
            logger.error(f"Chart error: {e}")
            return None


class AssistantTools:
    """Helper tools for the Personal Assistant."""

    @staticmethod
    def get_weather(city: str) -> str:
        if not WEATHER_API_KEY:
            return "Maaf karna bro, Weather API key is missing in settings."
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
            r = requests.get(url).json()
            if r.get('cod') != 200: return f"City '{city}' nahi mili bro."
            temp = r['main']['temp']
            desc = r['weather'][0]['description']
            return f"🌡️ Mausam in {city}: {temp}°C, {desc}. Mast mausam hai!"
        except:
            return "Mausam check karne mein thoda issue aa gaya."

    @staticmethod
    def convert_currency(amount: float, from_curr: str, to_curr: str) -> str:
        try:
            url = f"https://api.frankfurter.app/latest?amount={amount}&from={from_curr}&to={to_curr}"
            r = requests.get(url).json()
            val = r['rates'][to_curr.upper()]
            return f"💵 {amount} {from_curr.upper()} is about <b>{val:.2f} {to_curr.upper()}</b> right now."
        except:
            return "Currency conversion failed. Maybe the codes are wrong?"

class PDFReport(FPDF):
    def header(self):
        # Branding Header
        self.set_fill_color(94, 106, 210) # Accent Color
        self.rect(0, 0, 210, 40, 'F')
        
        self.set_font("helvetica", "B", 24)
        self.set_text_color(255, 255, 255)
        self.cell(0, 20, "ANALYST IQ", ln=True, align="C")
        
        self.set_font("helvetica", "I", 10)
        self.cell(0, 5, "Executive Data Intelligence & Business Insights", ln=True, align="C")
        self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()} | Generated by AnalystIQ Co-Pilot | {datetime.now().strftime('%Y-%m-%d %H:%M')}", align="C")

    def chapter_title(self, title):
        self.set_font("helvetica", "B", 14)
        self.set_fill_color(240, 240, 240)
        self.set_text_color(94, 106, 210)
        self.cell(0, 10, f"  {title}", ln=True, fill=True)
        self.ln(5)

    def chapter_body(self, body):
        self.set_font("helvetica", size=10)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 7, body)
        self.ln(5)

    def draw_table(self, data):
        if not data: return
        
        # Get column names from the first dictionary
        headers = list(data[0].keys())
        
        self.set_font("helvetica", "B", 10)
        self.set_fill_color(240, 240, 240)
        self.set_text_color(0, 0, 0)
        
        # Determine column widths
        col_width = 190 / len(headers)
        
        # Render Headers
        for header in headers:
            self.cell(col_width, 10, str(header).upper(), border=1, align="C", fill=True)
        self.ln()
        
        # Render Rows
        self.set_font("helvetica", size=9)
        fill = False
        for row in data:
            self.set_fill_color(250, 250, 250) if fill else self.set_fill_color(255, 255, 255)
            for header in headers:
                self.cell(col_width, 8, str(row.get(header, "")), border=1, align="C", fill=True)
            self.ln()
            fill = not fill
        self.ln(10)

    @staticmethod
    def generate_report(title: str, summary: str, data_list: List[dict], chart_bytes: Optional[bytes] = None) -> bytes:
        pdf = PDFReport()
        pdf.add_page()
        
        # 1. Executive Summary
        pdf.chapter_title("EXECUTIVE SUMMARY")
        clean_summary = summary.replace('<b>','').replace('</b>','').replace('<i>','').replace('</i>','').replace('<code>','').replace('</code>','').replace('🌌','')
        pdf.chapter_body(clean_summary)
        
        # 2. Visual Intelligence (Chart)
        if chart_bytes:
            pdf.chapter_title("VISUAL INTELLIGENCE")
            img_path = f"temp_chart_{int(time.time())}.png"
            with open(img_path, "wb") as f:
                f.write(chart_bytes)
            # Center the image
            pdf.image(img_path, x=25, w=160)
            pdf.ln(5)
            if os.path.exists(img_path):
                os.remove(img_path)
            pdf.add_page() # Start data on fresh page if there's a chart

        # 3. Detailed Data Analytics (Table)
        pdf.chapter_title("DETAILED DATA ANALYTICS")
        pdf.draw_table(data_list)
        
        return pdf.output()


# Initialize Assistant components
ai_assistant = AIAssistant()
tools = AssistantTools()

async def check_reminders_job(context: ContextTypes.DEFAULT_TYPE):
    """Background task to send reminders (JobQueue version)."""
    pending = DatabaseManager.get_pending_reminders()
    for rem in pending:
        try:
            msg = f"⏰ <b>BHOOLNA MAT BRO!</b>\n\n{rem['message']}\n\n<i>— Task Yaad Dilaya by AnalystIQ</i>"
            await context.bot.send_message(chat_id=rem['chat_id'], text=msg, parse_mode='HTML')
            DatabaseManager.mark_reminder_sent(rem['id'])
        except Exception as e:
            logger.error(f"Failed to send reminder {rem['id']}: {e}")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    welcome_message = """
<b>AnalystIQ Console v7.1 | Executive Co-Pilot</b> 🌌

I am your business co-pilot, infused with the <b>Antigravity</b> expert persona. I don't just analyze data—I help you lead.

<b>Command Suite:</b>
• <b>Data Visualization:</b> "Top products ka pie chart dikhao"
• <b>Active Reminders:</b> "Yaad dilao 5 minute mein ki meeting hai"
• <b>Market Intelligence:</b> "Mumbai ka mausam kaisa hai?"
• <b>Global Finance:</b> "Convert 50 USD to INR"
• <b>Executive Reports:</b> "Generate a PDF sales report"

Ask anything. I am online and architecting your next move.
"""
    await update.message.reply_text(welcome_message, parse_mode='HTML')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = """
🤖 <b>AnalystIQ Help Guide</b>

<b>Business:</b> Natural language SQL queries, charts, and PDF reports.
<b>Personal:</b> Reminders, Weather, and Currency.

<b>Example:</b> "Remind me at 15:30 to check the inventory."
"""
    await update.message.reply_text(help_text, parse_mode='HTML')


async def schema_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /schema command."""
    schema = DatabaseManager.get_table_schema()
    await update.message.reply_text(f"```\n{schema}\n```", parse_mode='Markdown')


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming voice messages."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    await update.message.chat.send_action(action="typing")
    
    # Download the voice file
    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    temp_path = f"voice_{user_id}_{int(time.time())}.ogg"
    await file.download_to_drive(temp_path)
    
    # Ask the Dispatcher to 'hear' the message
    decision = ai_assistant.dispatch("", chat_id, audio_path=temp_path)
    
    # Transcribed text (if provided by AI)
    transcription = decision.get('transcription', "Voice Message")
    
    # Cleanup file
    if os.path.exists(temp_path):
        os.remove(temp_path)
    
    # Process the decision using the transcription as the effective message
    await process_decision(update, context, decision, transcription)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages using the Contextual Dispatcher."""
    user_message = update.message.text
    chat_id = update.effective_chat.id
    
    await update.message.chat.send_action(action="typing")
    
    # 1. Ask the Dispatcher what to do (using memory)
    decision = ai_assistant.dispatch(user_message, chat_id)
    await process_decision(update, context, decision, user_message)


async def process_decision(update: Update, context: ContextTypes.DEFAULT_TYPE, decision: dict, user_message: str):
    """Core logic to process an AI decision (shared by text and voice)."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    tool = decision.get('tool', 'chit_chat')
    params = decision.get('parameters', {})
    
    # Store user message in memory
    ai_assistant.add_to_memory(chat_id, "User", user_message)
    
    logger.info(f"User {user_id} -> Tool: {tool} | Thought: {decision.get('thought')}")

    final_text = ""
    if tool == 'set_reminder':
        try:
            remind_time = datetime.strptime(params['time'], "%Y-%m-%d %H:%M:%S")
            if DatabaseManager.add_reminder(user_id, chat_id, params['message'], remind_time):
                final_text = f"✅ Theek hai bro, scheduled: <i>{params['message']}</i> for <b>{params['time']}</b>."
            else:
                final_text = "❌ Reminder set karne mein koi locha ho gaya."
        except:
            final_text = "❌ Time format mein kuch gadbad hai. Try: 'yaad dilana 5 baje'"
        await update.message.reply_text(final_text, parse_mode='HTML')

    elif tool == 'get_weather':
        final_text = tools.get_weather(params.get('city', 'Mumbai'))
        await update.message.reply_text(final_text)

    elif tool == 'convert_currency':
        final_text = tools.convert_currency(params.get('amount', 1), params.get('from', 'USD'), params.get('to', 'INR'))
        await update.message.reply_text(final_text, parse_mode='HTML')

    elif tool == 'query_database' or tool == 'generate_pdf':
        sql_result = ai_assistant.generate_sql_query(user_message)
        if not sql_result.get('success'):
            final_text = f"❌ Samajhna thoda mushkil hai: {sql_result.get('error')}"
            await update.message.reply_text(final_text)
            return
        
        db_res = DatabaseManager.execute_query(sql_result['query'])
        raw_data = ai_assistant.format_response(user_message, db_res)
        commentary_obj = ai_assistant.generate_commentary(user_message, raw_data, chat_id)
        final_text = commentary_obj['full_display']

        if tool == 'generate_pdf':
            chart = None
            db_data = db_res.get('data', [])
            if ai_assistant.is_chart_requested(user_message):
                chart = ai_assistant.create_chart(user_message, db_data)
            
            # Pass ONLY the clean AI insights to the PDF summary
            pdf_bytes = PDFReport.generate_report("Business Report by AnalystIQ", commentary_obj['insight'], db_data, chart)
            buf = io.BytesIO(pdf_bytes)
            buf.name = f"report_{datetime.now().strftime('%H%M%S')}.pdf"
            await update.message.reply_document(document=buf, caption="📂 Your Professional Executive Report is ready!")
        else:
            if ai_assistant.is_chart_requested(user_message):
                chart = ai_assistant.create_chart(user_message, db_res.get('data'))
                if chart:
                    await update.message.reply_photo(photo=chart, caption=final_text, parse_mode='HTML')
                    ai_assistant.add_to_memory(chat_id, "AnalystIQ", final_text)
                    return
            await update.message.reply_text(final_text, parse_mode='HTML')

    else: # chit_chat
        prompt = f"Respond as 'AnalystIQ', a sophisticated AI business partner with the 'Antigravity' persona. Provide deep, expert-level strategic advice and proactive support. User says: {user_message}"
        res = model.generate_content(prompt, generation_config={"max_output_tokens": 1024})
        final_text = res.text
        await update.message.reply_text(final_text)

    # Store assistant response in memory
    ai_assistant.add_to_memory(chat_id, "AnalystIQ", final_text)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.message:
        await update.message.reply_text(
            "❌ An error occurred while processing your request. Please try again."
        )


def main():
    """Start the bot."""
    
    # Validate configuration
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set in .env file")
        return
    
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set in .env file")
        return
    
    logger.info("Starting Telegram AI Business Assistant Bot v3.0...")
    logger.info(f"Targeting MySQL Database: {MYSQL_CONFIG['database']} on {MYSQL_CONFIG['host']}")
    
    # Build application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("schema", schema_command))
    
    # Whitelisting Guard
    whitelist = config.get('WHITELIST', [])
    
    async def restricted_handler(update, context):
        user = update.effective_user
        # Try to match username or phone if available
        # Note: Bots only get phone if the user shares their contact, 
        # but we can match by username/ID as a reliable proxy.
        # Here we match against the string provided in the Whitelist settings.
        allowed = False
        if not whitelist:
            allowed = True # Default to open if no whitelist set
        else:
            identifier = user.username or str(user.id)
            for entry in whitelist:
                # Basic fuzzy match for ID or Username
                if entry.replace("@", "").strip().lower() == identifier.lower():
                    allowed = True
                    break
        
        if allowed:
            if update.message.voice:
                await handle_voice(update, context)
            else:
                await handle_message(update, context)
        else:
            logger.warning(f"Unauthorized access attempt by {identifier}")
            await update.message.reply_text("🔒 Access Restricted. You are not on the authorized whitelist.")

    application.add_handler(MessageHandler((filters.TEXT & ~filters.COMMAND) | filters.VOICE, restricted_handler))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start JobQueue for reminders
    if application.job_queue:
        application.job_queue.run_repeating(check_reminders_job, interval=60, first=10)
    else:
        logger.warning("JobQueue not available. Reminders will not work.")

    # Start the bot
    logger.info("Bot is running! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
