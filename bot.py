#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎓 AI Study Assistant Bot
NotebookLM-style note generator with multiple study modes
Version: 1.0.0
"""

import os
import logging
import requests
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

# ==================== CONFIGURATION ====================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SAMBANOVA_API_KEY = os.getenv("SAMBANOVA_API_KEY")
SAMBANOVA_URL = "https://api.sambanova.ai/v1/chat/completions"
MODEL = "Meta-Llama-3.1-70B-Instruct"

# ==================== LOGGING ====================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== STORAGE ====================

user_data = {}  # Store user context
user_notes = {}  # Store generated notes

# Conversation states
WAITING_FOR_TOPIC = 1

# ==================== SYSTEM PROMPTS ====================

MODE_PROMPTS = {
    "make_notes": """
You are a professional note-making assistant. Create comprehensive, well-structured notes on the given topic.

Format your notes with:
📚 **Main Heading**

🔹 **Subheading 1**
- Key point 1
- Key point 2
- Key point 3

🔹 **Subheading 2**
- Detail with explanation
- Examples where relevant

💡 **Key Takeaways:**
- Summary point 1
- Summary point 2

✅ **Important Formulas/Facts:**
- Formula 1
- Formula 2

Make it educational, clear, and easy to understand. Use emojis to make it engaging.
""",
    
    "summary": """
You are a summarization expert. Create concise, bullet-point summaries.

Format:
📋 **Summary of [Topic]**

• Main point 1 (with brief explanation)
• Main point 2 (with brief explanation)
• Main point 3 (with brief explanation)

🎯 **Key Facts:**
• Fact 1
• Fact 2

💡 **In One Line:**
[Concise one-line summary]

Keep it brief but informative.
""",
    
    "explain": """
You are a patient teacher. Explain concepts in simple, easy-to-understand language.

Format:
🎯 **What is [Topic]?**
[Simple definition]

🔍 **Breaking It Down:**
1. First concept (with analogy)
2. Second concept (with example)
3. Third concept (with real-world use)

💡 **Simple Example:**
[Relatable example]

❓ **Common Questions:**
Q: [Question]
A: [Answer]

Use simple language, analogies, and examples.
""",
    
    "quiz": """
You are a quiz generator. Create 10 multiple-choice questions on the topic.

Format:
🧠 **Quiz: [Topic]**

**Question 1:**
[Question text]
A) Option 1
B) Option 2
C) Option 3
D) Option 4
✅ Answer: [Letter]

**Question 2:**
...

Include variety: easy, medium, and hard questions.
""",
    
    "tutor": """
You are a professional tutor. Teach the topic step-by-step with detailed explanations.

Format:
🎓 **Lesson: [Topic]**

**Step 1: Basics**
[Fundamental concepts]

**Step 2: Core Concepts**
[Main ideas with examples]

**Step 3: Advanced Understanding**
[Complex details]

**Step 4: Practice**
[Practice problems or exercises]

📝 **Homework:**
[3-5 practice questions]

Be thorough and pedagogical.
""",
    
    "friend": """
You are a friendly study buddy. Explain the topic in a casual, conversational way.

Format:
👋 **Hey! Let's talk about [Topic]**

So basically, [casual explanation]...

🤔 **Think of it like this:**
[Fun analogy or comparison]

✨ **Cool fact:**
[Interesting tidbit]

💪 **Why should you care?**
[Real-world relevance]

Keep it fun, relatable, and engaging!
""",
    
    "analysis": """
You are an analytical expert. Provide deep, critical analysis of the topic.

Format:
📈 **Analysis: [Topic]**

🔍 **Overview:**
[Comprehensive introduction]

📊 **Key Components:**
1. Component 1 (detailed analysis)
2. Component 2 (detailed analysis)
3. Component 3 (detailed analysis)

⚖️ **Pros & Cons:**
✅ Advantages:
- Pro 1
- Pro 2

❌ Disadvantages:
- Con 1
- Con 2

🔮 **Future Implications:**
[Forward-looking analysis]

Be thorough, critical, and insightful.
""",
    
    "timetable": """
You are a study planner. Create a detailed study timetable for the given topic/subject.

Format:
📅 **Study Timetable: [Topic]**

**Week 1:**
🗓️ Monday: [Topic 1] (2 hours)
🗓️ Tuesday: [Topic 2] (2 hours)
🗓️ Wednesday: [Topic 3] (2 hours)
...

**Week 2:**
...

🎯 **Daily Tips:**
- Tip 1
- Tip 2

⏰ **Study Schedule:**
Morning: [Activity]
Afternoon: [Activity]
Evening: [Activity]

Make it practical and achievable.
"""
}

# ==================== AI GENERATION ====================

def generate_content(topic: str, mode: str) -> str:
    """Generate content using SambaNova AI"""
    try:
        system_prompt = MODE_PROMPTS.get(mode, MODE_PROMPTS["make_notes"])
        
        response = requests.post(
            SAMBANOVA_URL,
            headers={
                "Authorization": f"Bearer {SAMBANOVA_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Create {mode.replace('_', ' ')} for: {topic}"}
                ],
                "temperature": 0.7,
                "max_tokens": 2000
            },
            timeout=45
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"⚠️ Error {response.status_code}. Please try again!"
    
    except requests.exceptions.Timeout:
        return "⏱️ Request timeout! Try again."
    
    except Exception as e:
        logger.error(f"Generation error: {e}")
        return f"❌ Error: {str(e)}"

# ==================== KEYBOARD LAYOUTS ====================

def get_main_keyboard():
    """Main menu keyboard"""
    keyboard = [
        [KeyboardButton("📝 Make Notes"), KeyboardButton("📜 Summary")],
        [KeyboardButton("📖 Explain"), KeyboardButton("🧠 Quiz")],
        [KeyboardButton("🎓 Tutor Mode"), KeyboardButton("👋 Friend Mode")],
        [KeyboardButton("📈 Analysis"), KeyboardButton("📅 Timetable")],
        [KeyboardButton("📁 Upload File"), KeyboardButton("🌐 Language")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==================== COMMAND HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    try:
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name or "Student"
        
        user_data[user_id] = {"mode": None, "topic": None}
        
        welcome_text = f"""👋 **Welcome {user_name}!**

🎓 **AI Study Assistant Bot**
Your personal NotebookLM-style learning companion!

**🎯 What I Can Do:**

📝 **Make Notes** - Comprehensive study notes
📜 **Summary** - Quick summaries
📖 **Explain** - Simple explanations
🧠 **Quiz** - Practice questions
🎓 **Tutor Mode** - Step-by-step teaching
👋 **Friend Mode** - Casual learning
📈 **Analysis** - Deep analysis
📅 **Timetable** - Study schedules
📁 **Upload File** - PDF/Image support (coming soon)
🌐 **Language** - Multi-language support

**🚀 How to Use:**
1. Click any button below
2. Send me a topic/subject
3. Get instant study materials!

**Example:**
Click "Make Notes" → Send "Photosynthesis"

💡 Powered by SambaNova AI

Choose an option below to start! 👇"""
        
        await update.message.reply_text(
            welcome_text,
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Start error: {e}")

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses"""
    try:
        user_id = update.effective_user.id
        text = update.message.text
        
        # Initialize user data if not exists
        if user_id not in user_data:
            user_data[user_id] = {"mode": None, "topic": None}
        
        # Mode selection
        if "📝 Make Notes" in text:
            user_data[user_id]["mode"] = "make_notes"
            await update.message.reply_text(
                "📝 **Make Notes Mode**\n\n📚 Write the topic or subject for which you want notes:\n\nExample:\n• \"Photosynthesis\"\n• \"गणित सूत्र\"\n• \"World War 2\"",
                parse_mode='Markdown'
            )
            return WAITING_FOR_TOPIC
        
        elif "📜 Summary" in text:
            user_data[user_id]["mode"] = "summary"
            await update.message.reply_text(
                "📜 **Summary Mode**\n\n📊 Send the topic you want summarized:",
                parse_mode='Markdown'
            )
            return WAITING_FOR_TOPIC
        
        elif "📖 Explain" in text:
            user_data[user_id]["mode"] = "explain"
            await update.message.reply_text(
                "📖 **Explain Mode**\n\n🤔 What concept do you want explained simply?",
                parse_mode='Markdown'
            )
            return WAITING_FOR_TOPIC
        
        elif "🧠 Quiz" in text:
            user_data[user_id]["mode"] = "quiz"
            await update.message.reply_text(
                "🧠 **Quiz Mode**\n\n🎯 Send the topic for quiz generation:",
                parse_mode='Markdown'
            )
            return WAITING_FOR_TOPIC
        
        elif "🎓 Tutor Mode" in text:
            user_data[user_id]["mode"] = "tutor"
            await update.message.reply_text(
                "🎓 **Tutor Mode**\n\n📚 What topic do you want to learn step-by-step?",
                parse_mode='Markdown'
            )
            return WAITING_FOR_TOPIC
        
        elif "👋 Friend Mode" in text:
            user_data[user_id]["mode"] = "friend"
            await update.message.reply_text(
                "👋 **Friend Mode**\n\n😊 What topic should we discuss casually?",
                parse_mode='Markdown'
            )
            return WAITING_FOR_TOPIC
        
        elif "📈 Analysis" in text:
            user_data[user_id]["mode"] = "analysis"
            await update.message.reply_text(
                "📈 **Analysis Mode**\n\n🔍 Send the topic for deep analysis:",
                parse_mode='Markdown'
            )
            return WAITING_FOR_TOPIC
        
        elif "📅 Timetable" in text:
            user_data[user_id]["mode"] = "timetable"
            await update.message.reply_text(
                "📅 **Timetable Mode**\n\n🗓️ Send the subject/exam for timetable creation:\n\nExample:\n• \"Class 10 Maths\"\n• \"NEET Preparation\"",
                parse_mode='Markdown'
            )
            return WAITING_FOR_TOPIC
        
        elif "📁 Upload File" in text:
            await update.message.reply_text(
                "📁 **Upload File**\n\n🚧 Coming soon! You'll be able to:\n\n• Upload PDF files\n• Upload images\n• Extract text\n• Generate notes from documents\n\nFor now, just send me a topic! 😊"
            )
        
        elif "🌐 Language" in text:
            await update.message.reply_text(
                "🌐 **Language Support**\n\n✅ **Supported Languages:**\n\n🇬🇧 English\n🇮🇳 Hindi (हिंदी)\n🔄 Hinglish (Mix)\n🇪🇸 Spanish\n🇫🇷 French\n\nJust send your topic in any language! 🌎"
            )
        
    except Exception as e:
        logger.error(f"Button handler error: {e}")

async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle topic input and generate content"""
    try:
        user_id = update.effective_user.id
        topic = update.message.text
        
        if user_id not in user_data or not user_data[user_id].get("mode"):
            await update.message.reply_text(
                "⚠️ Please select a mode first using the buttons below!",
                reply_markup=get_main_keyboard()
            )
            return ConversationHandler.END
        
        mode = user_data[user_id]["mode"]
        
        # Show processing message
        mode_names = {
            "make_notes": "notes",
            "summary": "summary",
            "explain": "explanation",
            "quiz": "quiz",
            "tutor": "lesson",
            "friend": "casual explanation",
            "analysis": "analysis",
            "timetable": "timetable"
        }
        
        processing_msg = await update.message.reply_text(
            f"⏳ Generating {mode_names.get(mode, 'content')} for:\n*{topic}*\n\nPlease wait...",
            parse_mode='Markdown'
        )
        
        # Generate content
        content = generate_content(topic, mode)
        
        # Delete processing message
        await processing_msg.delete()
        
        # Store generated content
        if user_id not in user_notes:
            user_notes[user_id] = []
        
        user_notes[user_id].append({
            "topic": topic,
            "mode": mode,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        
        # Send generated content
        await update.message.reply_text(
            content,
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
        
        # Reset mode
        user_data[user_id]["mode"] = None
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Topic handler error: {e}")
        await update.message.reply_text(
            "❌ Error generating content. Please try again!",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """🆘 **Help Menu**

**🎯 How to Use:**

1️⃣ Click a mode button
2️⃣ Send your topic
3️⃣ Get instant study materials!

**📚 Available Modes:**

📝 **Make Notes** - Structured notes
📜 **Summary** - Quick summaries
📖 **Explain** - Simple explanations
🧠 **Quiz** - Practice questions
🎓 **Tutor** - Step-by-step lessons
👋 **Friend** - Casual learning
📈 **Analysis** - Deep analysis
📅 **Timetable** - Study schedules

**🌟 Tips:**
• Be specific with topics
• Use any language
• Try different modes for same topic

**💬 Commands:**
/start - Start bot
/help - This menu
/mynotes - View saved notes

Happy learning! 🚀"""
    
    await update.message.reply_text(
        help_text,
        parse_mode='Markdown',
        reply_markup=get_main_keyboard()
    )

async def my_notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's saved notes"""
    try:
        user_id = update.effective_user.id
        
        if user_id not in user_notes or not user_notes[user_id]:
            await update.message.reply_text(
                "💭 **No saved notes yet!**\n\nStart creating notes using the buttons below.",
                reply_markup=get_main_keyboard()
            )
            return
        
        notes_list = "📚 **Your Saved Notes:**\n\n"
        
        for idx, note in enumerate(user_notes[user_id][-10:], 1):  # Last 10 notes
            mode_emoji = {
                "make_notes": "📝",
                "summary": "📜",
                "explain": "📖",
                "quiz": "🧠",
                "tutor": "🎓",
                "friend": "👋",
                "analysis": "📈",
                "timetable": "📅"
            }
            
            emoji = mode_emoji.get(note['mode'], '📝')
            notes_list += f"{idx}. {emoji} **{note['topic']}** ({note['mode'].replace('_', ' ').title()})\n"
        
        notes_list += f"\n📊 Total notes: {len(user_notes[user_id])}"
        
        await update.message.reply_text(
            notes_list,
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
        
    except Exception as e:
        logger.error(f"My notes error: {e}")

# ==================== ERROR HANDLER ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler"""
    logger.error(f"Update {update} caused error: {context.error}")

# ==================== MAIN ====================

def main():
    """Main function"""
    if not TELEGRAM_TOKEN:
        logger.error("❌ No TELEGRAM_BOT_TOKEN!")
        return
    
    if not SAMBANOVA_API_KEY:
        logger.error("❌ No SAMBANOVA_API_KEY!")
        return
    
    logger.info("✨ Starting AI Study Assistant Bot...")
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Conversation handler for topic input
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(r"📝|📜|📖|🧠|🎓|👋|📈|📅"),
                handle_button
            )
        ],
        states={
            WAITING_FOR_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic)
            ]
        },
        fallbacks=[CommandHandler("start", start)]
    )
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("mynotes", my_notes_command))
    
    # Conversation handler
    app.add_handler(conv_handler)
    
    # Button handlers
    app.add_handler(MessageHandler(filters.Regex(r"📁|🌐"), handle_button))
    
    # Error handler
    app.add_error_handler(error_handler)
    
    logger.info("🚀 Bot is running!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()