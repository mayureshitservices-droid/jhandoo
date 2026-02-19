function showPage(pageId) {
    // Hide all pages
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    // Show target
    document.getElementById('page-' + pageId).classList.add('active');

    // Update nav states
    document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));
    event.currentTarget.classList.add('active');
}

// System Browser Routing
function openExternal(url) {
    if (url) eel.open_url(url)();
}

// Intercept clicks on links that should open in system browser
document.addEventListener('click', (e) => {
    const link = e.target.closest('a[target="_blank"]');
    if (link) {
        e.preventDefault();
        openExternal(link.href);
    }
});

// System Status Logic
let isRunning = false;

async function toggleEngine() {
    const btn = document.getElementById('toggle-btn');
    const ring = document.getElementById('status-ring');
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    const desc = document.getElementById('status-desc');

    if (!isRunning) {
        // Start Sequence: Validate first
        text.innerText = "VALIDATING SETUP...";
        text.style.color = "var(--neon-cyan)";
        desc.innerText = "Checking Database, Gemini, and Telegram connectivity...";
        btn.disabled = true;

        try {
            const validation = await eel.validate_full_config()();

            if (!validation.success) {
                text.innerText = "SETUP INCOMPLETE";
                text.style.color = "#EF4444";
                desc.innerHTML = `<span style="color: #ff4b2b;">${validation.errors.join('<br>')}</span>`;
                dot.className = "dot offline";
                ring.className = "ring offline";
                btn.disabled = false;
                btn.innerText = "RETRY WAKE UP";
                return;
            }

            // If validation passes, start the bot
            const success = await eel.toggle_bot()();
            if (success) {
                isRunning = true;
                btn.innerText = "PUT TO SLEEP";
                btn.className = "btn btn-status stop active";
                ring.className = "ring online";
                dot.className = "dot online";
                text.innerText = "AI IS ACTIVELY LISTENING";
                text.style.color = "#22C55E";
                desc.innerText = "System online. Ready for Telegram commands.";
            } else {
                alert("Failed to start the engine process.");
                text.innerText = "SYSTEM ERROR";
                dot.className = "dot offline";
            }
        } catch (e) {
            console.error(e);
            text.innerText = "ENGINE ERROR";
            desc.innerText = "Could not communicate with the backend logic.";
        }
        btn.disabled = false;
    } else {
        // Stop Sequence
        await eel.toggle_bot()();
        isRunning = false;
        btn.innerText = "WAKE UP AI";
        btn.className = "btn btn-status";
        ring.className = "ring offline";
        dot.className = "dot offline";
        text.innerText = "ASSISTANT IS HAVING SOME REST";
        text.style.color = "#EF4444";
        desc.innerText = "I am currently in standby mode.";
    }
}

// Config Bridge
async function saveConfig() {
    const data = {
        GEMINI_API_KEY: document.getElementById('gemini_key').value,
        TELEGRAM_BOT_TOKEN: document.getElementById('bot_token').value,
        OPENWEATHER_API_KEY: document.getElementById('weather_key').value
    };
    await eel.save_config(data)();
    alert("Security keys have been sealed and saved.");
}

async function saveWhitelist() {
    const data = {
        WHITELIST: [
            document.getElementById('user_1').value,
            document.getElementById('user_2').value,
            document.getElementById('user_3').value
        ].filter(n => n.trim() !== "")
    };
    await eel.save_config(data)();
    alert("Whitelist authorization updated.");
}

async function testConnection() {
    const data = {
        MYSQL_HOST: document.getElementById('db_host').value,
        MYSQL_USER: document.getElementById('db_user').value,
        MYSQL_PASSWORD: document.getElementById('db_pass').value,
        MYSQL_DATABASE: document.getElementById('db_name').value
    };
    const success = await eel.test_db(data)();
    if (success) {
        alert("Database connection verified successfully.");
    } else {
        alert("Connectivity failed. Please check your credentials.");
    }
}

// Initial Load
window.addEventListener('load', async () => {
    const config = await eel.get_config()();
    if (config) {
        document.getElementById('db_host').value = config.MYSQL_HOST || 'localhost';
        document.getElementById('db_user').value = config.MYSQL_USER || 'root';
        document.getElementById('db_pass').value = config.MYSQL_PASSWORD || '';
        document.getElementById('db_name').value = config.MYSQL_DATABASE || '';

        document.getElementById('gemini_key').value = config.GEMINI_API_KEY || '';
        document.getElementById('bot_token').value = config.TELEGRAM_BOT_TOKEN || '';
        document.getElementById('weather_key').value = config.OPENWEATHER_API_KEY || '';

        if (config.WHITELIST) {
            document.getElementById('user_1').value = config.WHITELIST[0] || '';
            document.getElementById('user_2').value = config.WHITELIST[1] || '';
            document.getElementById('user_3').value = config.WHITELIST[2] || '';
        }
    }
});
