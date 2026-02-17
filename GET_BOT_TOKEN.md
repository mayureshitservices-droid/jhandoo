# How to Get Your Existing Bot Token

Since you already have the "jhandoo" bot, you just need to retrieve its token from BotFather.

## Steps to Get Token for Existing Bot

1. **Open Telegram** and search for `@BotFather`

2. **Start a chat** with BotFather

3. **Send this command:**
   ```
   /mybots
   ```

4. **Select your bot** "jhandoo" from the list

5. **Click "API Token"**

6. **Copy the token** - it will look something like:
   ```
   123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ```

7. **Paste it in your `.env` file:**
   - Open: `d:\spenca\spenca-tesla\.env`
   - Find the line: `TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here`
   - Replace with: `TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

8. **Add your Gemini API key** on the next line:
   - Find: `GEMINI_API_KEY=your_gemini_api_key_here`
   - Replace with your actual Gemini API key

9. **Save the file**

10. **Run the bot:**
    ```powershell
    cd d:\spenca\spenca-tesla
    python telegram_bot.py
    ```

11. **Test it:**
    - Open your existing "jhandoo" bot in Telegram
    - Send: `/start`
    - Ask: "How many employees do we have?"

That's it! Your existing bot will now have AI database query capabilities! 🎉
