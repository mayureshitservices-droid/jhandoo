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
from typing import Optional
from dotenv import load_dotenv

# Telegram imports
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Gemini AI imports
import google.generativeai as genai

# Database imports
import mysql.connector
from mysql.connector import Error

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
MYSQL_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'database': os.getenv('MYSQL_DATABASE', 'ai_demo')
}

print("CRITICAL DEBUG: BOT VERSION 1.9 IS RUNNING")
# Initialize Gemini AI
logger.info("Initializing Gemini AI with model: gemini-2.0-flash")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')


class DatabaseManager:
    """Manages MySQL database connections and queries."""
    
    @staticmethod
    def execute_query(query: str) -> dict:
        """Execute a SQL query and return results."""
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
                cursor.close()
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
                cursor.close()
                connection.close()


class AIAssistant:
    """Handles AI-powered query understanding and SQL generation."""
    
    def __init__(self):
        self.schema = DatabaseManager.get_table_schema()
        self.conversation_history = {}
    
    def generate_sql_query(self, user_message: str, user_id: int) -> dict:
        """Convert natural language to SQL query using Gemini AI."""
        
        # Build prompt with schema context
        prompt = f"""You are a SQL expert assistant. Given the following database schema and user question, generate a valid MySQL query.

{self.schema}

User Question: {user_message}

Rules:
1. Generate ONLY the SQL query, no explanations
2. Use proper MySQL syntax
3. For counting queries, use COUNT(*)
4. For listing queries, limit to 10 rows unless specified
5. If the question is unclear, generate a query that shows relevant data
6. Do not use markdown formatting, just plain SQL

SQL Query:"""

        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                response = model.generate_content(prompt)
                sql_query = response.text.strip()
                
                # Clean up the query (remove markdown if present)
                sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
                
                logger.info(f"Generated SQL: {sql_query}")
                
                return {
                    'success': True,
                    'query': sql_query
                }
                
            except Exception as e:
                if "429" in str(e) and attempt < max_retries - 1:
                    logger.warning(f"Gemini API rate limit hit (429). Retrying in {retry_delay}s... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                    
                logger.error(f"AI generation error: {e}")
                return {
                    'success': False,
                    'error': str(e)
                }
    
    def format_response(self, user_message: str, query_result: dict) -> str:
        """Format database results into a user-friendly message."""
        
        if not query_result.get('success'):
            return f"❌ Database Error: {query_result.get('error', 'Unknown error')}"
        
        data = query_result.get('data')
        
        if data is None:
            # Non-SELECT query
            affected = query_result.get('affected_rows', 0)
            return f"✅ Query executed successfully. {affected} row(s) affected."
        
        if len(data) == 0:
            return "📭 No results found."
        
        # Format results as a table
        if len(data) == 1 and len(data[0]) == 1:
            # Single value result (like COUNT)
            key = list(data[0].keys())[0]
            value = data[0][key]
            return f"📊 <b>Result:</b> <code>{value}</code>"
        
        # Multiple rows/columns - format as text table (Internal representation)
        table_output = ""
        
        if len(data) <= 15:
            # Show all results
            for i, row in enumerate(data, 1):
                table_output += f"<b>{i}.</b> "
                table_output += " | ".join([f"{k}: <code>{v}</code>" for k, v in row.items()])
                table_output += "\n"
        else:
            # Show first 15
            for i, row in enumerate(data[:15], 1):
                table_output += f"<b>{i}.</b> "
                table_output += " | ".join([f"{k}: <code>{v}</code>" for k, v in row.items()])
                table_output += "\n"
            table_output += f"\n... and {len(data) - 15} more rows"
        
        return table_output

    def generate_commentary(self, user_message: str, formatted_data: str) -> str:
        """Generate a brief, humorous reaction to the data."""
        
        prompt = f"""You are 'Jhandoo', a witty, ultra-concise business partner.
Partner asked: "{user_message}"
Data: {formatted_data}

Rules:
1. Be extremely brief (max 1-2 short sentences).
2. One witty observation only. 
3. No robotic fluff.
4. Return PLAIN TEXT.

Response:"""

        max_retries = 2
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                # Use a smaller token limit for efficiency
                response = model.generate_content(
                    prompt, 
                    generation_config={"max_output_tokens": 100}
                )
                text = response.text.strip()
                
                # Escape HTML special characters to prevent Telegram parsing errors
                safe_text = html.escape(text)
                
                # Wrap it in nice formatting
                return f"🗨️ {safe_text}\n\n{formatted_data}\n\n<i>— Your buddy, Jhandoo</i>"
                
            except Exception as e:
                if "429" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                logger.error(f"Commentary generation error: {e}")
                # Fallback to plain data if AI fails
                return f"<b>Here's what I found:</b>\n\n{formatted_data}"


# Initialize AI Assistant
ai_assistant = AIAssistant()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    welcome_message = """
<b>Welcome to AI Business Assistant!</b>

I can help you query your business database using natural language.

<b>Examples:</b>
• "How many employees do we have?"
• "Show me all tables"
• "List the last 5 sales transactions"
• "What's the total sales amount?"

Just ask me anything about your data!

<b>Commands:</b>
/start - Show this welcome message
/help - Get help
/schema - View database schema
"""
    await update.message.reply_text(welcome_message, parse_mode='HTML')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = """
🤖 <b>AI Business Assistant Help</b>

<b>How to use:</b>
Simply type your question in natural language, and I'll query the database for you.

<b>Example questions:</b>
• "How many employees?"
• "Show me sales data"
• "List all tasks"
• "What tables exist?"

<b>Commands:</b>
/start - Welcome message
/help - This help message
/schema - View database structure

<b>Tips:</b>
• Be specific in your questions
• You can ask follow-up questions
• I understand context from previous messages
"""
    await update.message.reply_text(help_text, parse_mode='HTML')


async def schema_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /schema command - show database schema."""
    schema = DatabaseManager.get_table_schema()
    await update.message.reply_text(f"```\n{schema}\n```", parse_mode='Markdown')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages and process queries."""
    user_message = update.message.text
    user_id = update.effective_user.id
    
    logger.info(f"User {user_id} asked: {user_message}")
    
    # Send typing indicator
    await update.message.chat.send_action(action="typing")
    
    # Generate SQL query using AI
    sql_result = ai_assistant.generate_sql_query(user_message, user_id)
    
    if not sql_result.get('success'):
        await update.message.reply_text(
            f"❌ Sorry, I couldn't understand your question. Error: {sql_result.get('error')}"
        )
        return
    
    sql_query = sql_result['query']
    
    # Execute the query
    query_result = DatabaseManager.execute_query(sql_query)
    
    # Format raw table data
    raw_data = ai_assistant.format_response(user_message, query_result)
    
    # Generate human-like commentary wrapped around the data
    if query_result.get('success') and query_result.get('data') is not None:
        final_response = ai_assistant.generate_commentary(user_message, raw_data)
    else:
        final_response = raw_data
    
    await update.message.reply_text(final_response, parse_mode='HTML')


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
    
    logger.info("Starting Telegram AI Business Assistant Bot v1.7...")
    logger.info(f"Targeting MySQL Database: {MYSQL_CONFIG['database']} on {MYSQL_CONFIG['host']}")
    
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("schema", schema_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("Bot is running! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
