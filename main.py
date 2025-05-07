from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from tools.pdf_tool import extract_text_from_pdf
from tools.language_tool import detect_language, translate_text
# Add PEFT and transformers imports
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize model and tokenizer cache
hf_models = {}
hf_tokenizers = {}

# Available models configuration
AVAILABLE_MODELS = {
    "aviation-gpt": {
        "id": "SpontaneousSecret/llama2-aviationgpt",
        "base_model": "unsloth/llama-2-7b-bnb-4bit",
        "provider": "huggingface-peft",
        "max_tokens": 2048,  # Adjust based on your model's capabilities
        "description": "Aviation-focused GPT model based on Llama 2"
    },
    # You can add more models if needed
}

DEFAULT_MODEL = "aviation-gpt"

# Function to get or load HuggingFace PEFT model and tokenizer
def get_hf_model_and_tokenizer(model_config):
    model_id = model_config["id"]
    if model_id not in hf_models:
        try:
            # Load tokenizer from base model
            base_model_id = model_config.get("base_model", model_id)
            tokenizer = AutoTokenizer.from_pretrained(base_model_id)
            
            # Special handling for PEFT models
            if model_config["provider"] == "huggingface-peft":
                print(f"Loading PEFT model: {model_id} with base model: {base_model_id}")
                # Load the base model first
                base_model = AutoModelForCausalLM.from_pretrained(
                    base_model_id,
                    torch_dtype=torch.float16,
                    device_map="auto"
                )
                # Then load the PEFT model on top
                model = PeftModel.from_pretrained(base_model, model_id)
            else:
                # Regular model loading
                model = AutoModelForCausalLM.from_pretrained(
                    model_id,
                    torch_dtype=torch.float16,
                    device_map="auto"
                )
            
            model.eval()  # Set to evaluation mode
            hf_models[model_id] = model
            hf_tokenizers[model_id] = tokenizer
            print(f"Successfully loaded model and tokenizer for {model_id}")
        except Exception as e:
            print(f"Error loading model {model_id}: {str(e)}")
            raise
    
    return hf_models[model_id], hf_tokenizers[model_id]

# In-memory conversation storage
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
    
    # Generate response based on provider
    english_response = ""
    if model_config["provider"] == "huggingface-peft":
        try:
            # Get model and tokenizer
            model, tokenizer = get_hf_model_and_tokenizer(model_config)
            
            # Format conversation for Llama 2
            prompt = format_llama2_conversation(model_messages)
            
            # Tokenize the input
            inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
            
            # Generate response
            with torch.no_grad():
                output = model.generate(
                    inputs["input_ids"],
                    max_new_tokens=1024,  # Adjust as needed
                    temperature=0.7,
                    top_p=0.9,
                    do_sample=True,
                    pad_token_id=tokenizer.eos_token_id
                )
            
            # Decode the output
            full_response = tokenizer.decode(output[0], skip_special_tokens=True)
            
            # Extract just the assistant's response
            english_response = extract_assistant_response(full_response, prompt)
            
        except Exception as e:
            english_response = f"Error generating response: {str(e)}"
    
    # Add assistant message to conversation
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

# Helper function to format conversation for Llama 2
def format_llama2_conversation(messages):
    """
    Format the conversation for Llama 2 model.
    """
    system_prompt = "You are a helpful, respectful and honest assistant. Always answer as helpfully as possible, while being safe. Your answers should not include any harmful, unethical, racist, sexist, toxic, dangerous, or illegal content. Please ensure that your responses are socially unbiased and positive in nature.\n\nIf a question does not make any sense, or is not factually coherent, explain why instead of answering something not correct. If you don't know the answer to a question, please don't share false information."
    
    # Check for system message
    for i, message in enumerate(messages):
        if message["role"] == "system":
            system_prompt = message["content"]
            messages.pop(i)
            break
    
    formatted_prompt = f"<s>[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n\n"
    
    for i, message in enumerate(messages):
        role = message["role"]
        content = message["content"]
        
        if role == "user":
            if i == len(messages) - 1:  # Last message
                formatted_prompt += f"{content} [/INST]"
            else:
                formatted_prompt += f"{content} [/INST]"
        elif role == "assistant":
            formatted_prompt += f" {content} </s><s>[INST] "
    
    return formatted_prompt

# Helper function to extract assistant's response
def extract_assistant_response(full_response, prompt):
    """
    Extract just the assistant's response from the full model output.
    """
    # For Llama 2, the response comes after the last [/INST] token
    if "[/INST]" in full_response:
        response = full_response.split("[/INST]")[-1].strip()
        
        # Remove any trailing </s> tokens
        response = response.split("</s>")[0].strip()
        
        # Remove any trailing [INST] tag if present
        if "[INST]" in response:
            response = response.split("[INST]")[0].strip()
    else:
        # Fallback: if the model output doesn't contain [/INST]
        # just return everything after the prompt
        response = full_response[len(prompt):].strip()
    
    return response

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

