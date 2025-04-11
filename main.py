from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from tools.pdf_tool import extract_text_from_pdf
from tools.language_tool import detect_language, translate_text
from groq import Groq
import os
from dotenv import load_dotenv
from typing import List, Dict, Optional
import uuid
from pydantic import BaseModel
import json
from datetime import datetime

load_dotenv()

app = FastAPI()

# Serve static files from /static path
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve the HTML as homepage
@app.get("/")
def serve_home():
    return FileResponse("static/index.html")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Available models configuration
AVAILABLE_MODELS = {
    "llama3-8b": {
        "id": "llama3-8b-8192",
        "provider": "groq",
        "max_tokens": 8192,
        "description": "Llama 3 8B - Fast responses with good quality"
    },
    "llama3-70b": {
        "id": "llama3-70b-8192",
        "provider": "groq",
        "max_tokens": 8192,
        "description": "Llama 3 70B - High quality responses"
    },
    "mixtral-8x7b": {
        "id": "mixtral-8x7b-32768", 
        "provider": "groq",
        "max_tokens": 32768,
        "description": "Mixtral 8x7B - Good for longer contexts"
    },
    "gemma-7b": {
        "id": "gemma-7b-it",
        "provider": "groq",
        "max_tokens": 8192,
        "description": "Gemma 7B - Google's efficient model"
    }
}

DEFAULT_MODEL = "llama3-8b"

# In-memory conversation storage
# In production, use a database instead
conversations = {}

class Message(BaseModel):
    role: str
    content: str
    timestamp: str

class Conversation(BaseModel):
    id: str
    messages: List[Message]
    model_id: str
    created_at: str
    last_updated: str

# Create a new conversation or get existing one
def get_conversation(conversation_id: Optional[str] = None) -> Conversation:
    if conversation_id and conversation_id in conversations:
        return conversations[conversation_id]
    
    new_id = conversation_id or str(uuid.uuid4())
    now = datetime.now().isoformat()
    conversations[new_id] = Conversation(
        id=new_id,
        messages=[],
        model_id=DEFAULT_MODEL,
        created_at=now,
        last_updated=now
    )
    return conversations[new_id]

@app.get("/models")
async def list_models():
    return {"models": AVAILABLE_MODELS}

@app.get("/conversations")
async def get_conversations():
    return {
        "conversations": [
            {
                "id": conv_id,
                "model_id": conv.model_id,
                "created_at": conv.created_at,
                "last_updated": conv.last_updated,
                "message_count": len(conv.messages)
            }
            for conv_id, conv in conversations.items()
        ]
    }

@app.get("/conversations/{conversation_id}")
async def get_conversation_by_id(conversation_id: str):
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversations[conversation_id]

@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    if conversation_id in conversations:
        del conversations[conversation_id]
    return {"success": True}

@app.post("/chat")
async def chat(
    message: str = Form(...), 
    pdf: Optional[UploadFile] = File(None),
    model_id: str = Form(DEFAULT_MODEL),
    conversation_id: Optional[str] = Form(None)
):
    # Validate model
    if model_id not in AVAILABLE_MODELS:
        raise HTTPException(status_code=400, detail=f"Model {model_id} not available. Choose from: {list(AVAILABLE_MODELS.keys())}")
    
    # Get or create conversation
    conversation = get_conversation(conversation_id)
    conversation.model_id = model_id
    conversation.last_updated = datetime.now().isoformat()
    
    context = ""

    # Process PDF if provided
    if pdf:
        try:
            pdf_bytes = await pdf.read()
            context = extract_text_from_pdf(pdf_bytes)
        except Exception as e:
            context = f"(PDF Error: {str(e)})"

    # Detect language and translate if needed
    lang = detect_language(message)
    english_message = translate_text(message, lang)
    
    # Add user message to conversation history
    user_message = Message(
        role="user",
        content=english_message,
        timestamp=datetime.now().isoformat()
    )
    conversation.messages.append(user_message)
    
    # Build model messages from conversation history
    model_messages = []
    for msg in conversation.messages:
        model_messages.append({
            "role": msg.role, 
            "content": msg.content
        })
    
    # Add context from PDF if available
    if context:
        # Insert context as a system message at the beginning
        model_messages.insert(0, {
            "role": "system", 
            "content": f"The user has provided a document with the following content. Use this as context for your responses:\n\n{context}"
        })
    
    # Select model configuration
    model_config = AVAILABLE_MODELS[model_id]
    
    # Call the LLM API
    chat_completion = client.chat.completions.create(
        model=model_config["id"],
        messages=model_messages
    )

    english_response = chat_completion.choices[0].message.content.strip()
    
    now=datetime.now().isoformat()

    ai_message = Message(
    role="assistant",
    content=english_response,
    timestamp=datetime.now().isoformat()
    )
    conversation.messages.append(ai_message)
    
    # Translate response back to original language if needed
    translated_response = translate_text(english_response, lang, reverse=True)

    return {
        "response": translated_response,
        "conversation_id": conversation.id,
        "model_id": model_id
    }

# Get model info
@app.get("/models/{model_id}")
async def get_model_info(model_id: str):
    if model_id not in AVAILABLE_MODELS:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    return AVAILABLE_MODELS[model_id]

# Set model for conversation
@app.put("/conversations/{conversation_id}/model")
async def set_conversation_model(conversation_id: str, model_id: str = Form(...)):
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if model_id not in AVAILABLE_MODELS:
        raise HTTPException(status_code=400, detail=f"Model {model_id} not available")
    
    conversations[conversation_id].model_id = model_id
    conversations[conversation_id].last_updated = datetime.now().isoformat()
    
    return {"success": True, "conversation_id": conversation_id, "model_id": model_id}