from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
import mysql.connector
import os
import requests
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables from .env
load_dotenv()

# Secrets from .env
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MYSQL_CONFIG = {
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE")
}

# FastAPI app setup
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for dev/testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request body model
class ChatRequest(BaseModel):
    session_id: str
    message: str

# Fetch products from MySQL
def fetch_products():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT name, price, description FROM products")
    products = cursor.fetchall()
    conn.close()
    return products

# Construct chatbot prompt
def build_prompt(user_input, products):
    product_text = "\n".join(
        f"{p['name']} - ${p['price']:.2f} - {p['description']}" for p in products
    )
    return f"""You are a product support chatbot.

Available products:
{product_text}

User asked: "{user_input}"
Reply based on the product info above.
"""

# Call Groq API
def call_groq_ai(prompt):
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama3-8b-8192",
            "messages": [{"role": "user", "content": prompt}]
        }
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

# Save chat to MySQL
def save_chat(session_id, user_message, bot_response):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_history (session_id, user_message, bot_response) VALUES (%s, %s, %s)",
        (session_id, user_message, bot_response)
    )
    conn.commit()
    conn.close()

# Main chat endpoint
@app.post("/chat")
def chat_endpoint(chat: ChatRequest):
    products = fetch_products()
    prompt = build_prompt(chat.message, products)
    reply = call_groq_ai(prompt)
    save_chat(chat.session_id, chat.message, reply)
    return {"response": reply}
