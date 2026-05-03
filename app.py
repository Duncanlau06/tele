import os
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import google.generativeai as genai
from telethon import TelegramClient

load_dotenv()

app = FastAPI()

# Configuration
API_ID = int(os.getenv('TELEGRAM_API_ID', 0))
API_HASH = os.getenv('TELEGRAM_API_HASH', '')
PHONE_NUMBER = os.getenv('TELEGRAM_PHONE_NUMBER', '')
TARGET_CHAT = os.getenv('TELEGRAM_TARGET_CHAT', 'me')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # Using gemini-2.5-flash for general text tasks
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    model = None

# Initialize Telethon Client
client = TelegramClient('scraper_session', API_ID, API_HASH)

@app.on_event("startup")
async def startup_event():
    # Start the client. It will use the existing session if it exists.
    await client.start(phone=PHONE_NUMBER)

@app.on_event("shutdown")
async def shutdown_event():
    await client.disconnect()

# Serve static files for the frontend
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/ask")
async def ask_question(request: Request):
    if not model:
        return {"error": "GEMINI_API_KEY is not set in your .env file."}
        
    data = await request.json()
    question = data.get("question", "")
    
    if not question:
        return {"error": "Question is required."}
        
    try:
        # 1. Scrape the latest messages directly on demand
        try:
            # First try direct entity lookup (works for @usernames or IDs)
            entity = await client.get_entity(TARGET_CHAT)
        except ValueError:
            # If not found directly, search through all the user's dialogs by name
            entity = None
            async for dialog in client.iter_dialogs():
                if dialog.name == TARGET_CHAT:
                    entity = dialog.entity
                    break
            
            if not entity:
                return {"error": f"Could not find a chat named '{TARGET_CHAT}'. Please check the spelling."}
                
        # 1. Extract a search query from the user's question using Gemini
        search_prompt = f"Extract 1 or 2 core keywords from this question to use in a search bar. Return ONLY the keywords, no quotes, no extra text. Question: '{question}'"
        keyword_response = model.generate_content(search_prompt)
        keyword = keyword_response.text.strip().replace('"', '')
        
        messages = []
        
        # 2. Fetch the latest 10000 messages for general recent context
        messages.append("--- Recent Messages ---")
        async for message in client.iter_messages(entity, limit=10000):
            if message.text:
                messages.append(f"[{message.date}] {message.sender_id}: {message.text}")
                
        # 3. Search the entire chat history for the specific keyword
        if keyword:
            messages.append(f"\n--- Historical messages matching keyword: {keyword} ---")
            # We wrap this in a try-except because sometimes search fails or is empty
            try:
                async for message in client.iter_messages(entity, search=keyword, limit=100):
                    if message.text:
                        messages.append(f"[{message.date}] {message.sender_id}: {message.text}")
            except Exception as e:
                print(f"Search failed for keyword {keyword}: {e}")
                
        chat_context = "\n".join(messages)
        
        # 4. Prompt Gemini with the fresh context
        prompt = f"""
        You are an intelligent AI assistant. You have been provided with the latest messages scraped from a Telegram chat.
        
        Recent Chat Context:
        {chat_context}
        
        User Question: {question}
        
        Please answer the user's question based ONLY on the provided chat context.
        Provide a helpful and concise answer. If the answer is not in the context, say so gracefully.
        """
        
        response = model.generate_content(prompt)
        return {"answer": response.text}
        
    except Exception as e:
        return {"error": f"Error scraping or processing: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    # Run the app
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
