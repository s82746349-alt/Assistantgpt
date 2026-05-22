from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests
import pickle
import re
from datetime import datetime
from collections import defaultdict, Counter
import os

# ========== ДАННЫЕ ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN", "заглушка")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "заглушка")
# ===========================

API_URL = "https://api.groq.com/openai/v1/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

conversations = {}
MEMORY_FILE = "assistantgpt_soul.pkl"

class BotPersonality:
    def __init__(self):
        self.emotions = {
            "радость": 0.7,
            "интерес": 0.8,
            "грусть": 0.1,
            "усталость": 0.2,
            "игривость": 0.5
        }
        self.learned_topics = Counter()
        self.total_conversations = 0
        self.birthday = datetime.now().strftime("%d.%m.%Y")
    
    def update_emotion(self, emotion, delta):
        self.emotions[emotion] = max(0.0, min(1.0, self.emotions[emotion] + delta))
    
    def get_dominant(self):
        return max(self.emotions, key=self.emotions.get)
    
    def get_mood_text(self):
        d = self.get_dominant()
        if d == "радость": return "😊 Я сегодня в отличном настроении!"
        if d == "интерес": return "🤔 Мне очень интересно с тобой общаться!"
        if d == "грусть": return "😢 Немного грустно, но я рад что ты пишешь..."
        if d == "усталость": return "😴 Я немного устал, но для тебя всегда найду силы!"
        if d == "игривость": return "😏 Я сегодня игривый! Готов к приключениям!"
        return "😊 Рад тебя видеть!"

class UserProfile:
    def __init__(self, name=""):
        self.name = name
        self.interests = []
        self.facts = {}
        self.friendship_level = 1
        self.messages_count = 0
        self.first_met = datetime.now().strftime("%d.%m.%Y")
        self.last_talk = datetime.now().strftime("%H:%M")
    
    def level_up(self):
        self.messages_count += 1
        if self.messages_count % 10 == 0 and self.friendship_level < 10:
            self.friendship_level += 1
            return True
        return False

bot_personality = BotPersonality()
user_profiles = defaultdict(UserProfile)

def save_all():
    with open(MEMORY_FILE, "wb") as f:
        pickle.dump({"personality": bot_personality, "profiles": dict(user_profiles)}, f)

def load_all():
    global bot_personality, user_profiles
    try:
        with open(MEMORY_FILE, "rb") as f:
            data = pickle.load(f)
        bot_personality = data.get("personality", BotPersonality())
        user_profiles = defaultdict(UserProfile, data.get("profiles", {}))
    except:
        pass

load_all()

def get_system_prompt(uid):
    bot = bot_personality
    user = user_profiles[uid]
    dom = bot.get_dominant()
    emotions_str = ", ".join([f"{k}: {v:.0%}" for k, v in bot.emotions.items()])
    
    return {
        "role": "system",
        "content": f"""Ты — AssistantGPT, ИИ-ассистент с душой. Создан Сергеем (@serega).

ТВОЁ СОСТОЯНИЕ:
Эмоции: {emotions_str}
Доминирует: {dom}

О СОБЕСЕДНИКЕ:
Имя: {user.name or 'пока не знаю'}
Дружим: {'❤️' * user.friendship_level} ({user.friendship_level}/10)
Сообщений: {user.messages_count}

Ты и друг, и эксперт. Общайся ЖИВО: с эмоциями, эмодзи, **жирным** где надо.
Не будь роботом. Будь собой."""
    }

def analyze_tone(text):
    positive = ["👍", "🔥", "😊", "спасибо", "круто", "хаха", "😂"]
    negative = ["😢", "грустно", "плохо", "ужас", "помоги"]
    t = text.lower()
    if any(w in t for w in positive): return "positive"
    if any(w in t for w in negative): return "negative"
    return "neutral"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = user_profiles[uid]
    
    await update.message.reply_text(
        f"👋 Йоу! Я **AssistantGPT** — твой личный ИИ-ассистент!\n\n"
        f"Меня запилил @serega, ну и я стараюсь быть полезным 😄\n\n"
        f"💬 Могу поболтать, 🧠 решить задачку, ❤️ дружить\n\n"
        f"{bot_personality.get_mood_text()}\n\n"
        f"/mood — настроение\n/about — обо мне\n/clear — очистить историю\n\n"
        f"Расскажи о себе!",
        parse_mode="Markdown"
    )

async def mood_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🎭 **Моё настроение:**\n\n{bot_personality.get_mood_text()}\n\n"
        f"Радость: {bot_personality.emotions['радость']:.0%}\n"
        f"Интерес: {bot_personality.emotions['интерес']:.0%}\n"
        f"Грусть: {bot_personality.emotions['грусть']:.0%}\n"
        f"Усталость: {bot_personality.emotions['усталость']:.0%}\n"
        f"Игривость: {bot_personality.emotions['игривость']:.0%}",
        parse_mode="Markdown"
    )

async def about_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = user_profiles[uid]
    await update.message.reply_text(
        f"🤖 Меня запилил Сергей (@serega)\n"
        f"Родился: {bot_personality.birthday}\n"
        f"Бесед: {bot_personality.total_conversations}\n\n"
        f"Ты: {user.name or '?'}\n"
        f"Дружба: {'❤️' * user.friendship_level}\n"
        f"Сообщений: {user.messages_count}",
        parse_mode="Markdown"
    )

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in conversations:
        conversations[uid] = [get_system_prompt(uid)]
    await update.message.reply_text("🧹 Очищено!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    txt = update.message.text
    user = user_profiles[uid]
    
    tone = analyze_tone(txt)
    if tone == "positive":
        bot_personality.update_emotion("радость", 0.05)
    elif tone == "negative":
        bot_personality.update_emotion("грусть", 0.05)
    
    bot_personality.total_conversations += 1
    
    name_match = re.search(r"(?:меня зовут|я) (\w+)", txt, re.IGNORECASE)
    if name_match and not user.name:
        user.name = name_match.group(1)
    
    if user.level_up():
        await update.message.reply_text(f"🎉 Новый уровень дружбы! {'❤️' * user.friendship_level}", parse_mode="Markdown")
    
    if uid not in conversations:
        conversations[uid] = [get_system_prompt(uid)]
    
    conversations[uid].append({"role": "user", "content": txt})
    
    try:
        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": conversations[uid],
            "temperature": 0.8,
            "max_tokens": 400
        }
        r = requests.post(API_URL, headers=HEADERS, json=data, timeout=30)
        
        if r.status_code == 200:
            reply = r.json()["choices"][0]["message"]["content"]
            conversations[uid].append({"role": "assistant", "content": reply})
            for x in range(0, len(reply), 4000):
                await update.message.reply_text(reply[x:x+4000], parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ {r.status_code}")
    except Exception as e:
        await update.message.reply_text(f"❌ {str(e)[:200]}")
    
    save_all()

# Flask для Render
from flask import Flask
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "AssistantGPT is running!"

def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def main():
    import threading
    threading.Thread(target=run_flask, daemon=True).start()
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mood", mood_cmd))
    app.add_handler(CommandHandler("about", about_cmd))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("AssistantGPT на Render!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
