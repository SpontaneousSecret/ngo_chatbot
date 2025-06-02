from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from tools.pdf_tool import extract_text_from_pdf
from tools.language_tool import detect_language, translate_text
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import os
import sys
import warnings
from dotenv import load_dotenv
from typing import List, Optional
import uuid
from pydantic import BaseModel
from datetime import datetime
import gc

# Suppress bitsandbytes warnings and force CPU usage
os.environ["BITSANDBYTES_NOWELCOME"] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = ""
warnings.filterwarnings("ignore", message=".*bitsandbytes.*")
warnings.filterwarnings("ignore", message=".*quantization.*")

load_dotenv()

app = FastAPI()

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve homepage
@app.get("/")
def serve_home():
    return FileResponse("static/index.html")

# CORS middleware - More permissive for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Model configuration
MODEL_CONFIG = {
    "id": "SpontaneousSecret/llama2-aviationgpt",
    "max_tokens": 256,
    "description": "Aviation-focused GPT model (PEFT Adapter)"
}

# Global model variables
hf_model = None
hf_tokenizer = None

# Model loading function - Simple approach for PEFT adapter
def get_model_and_tokenizer():
    global hf_model, hf_tokenizer
    
    if hf_model is None or hf_tokenizer is None:
        try:
            model_id = MODEL_CONFIG["id"]
            print(f"Loading Aviation GPT PEFT adapter: {model_id}")
            
            # Load tokenizer
            hf_tokenizer = AutoTokenizer.from_pretrained(model_id)
            if hf_tokenizer.pad_token is None:
                hf_tokenizer.pad_token = hf_tokenizer.eos_token
            
            # Install PEFT if needed
            try:
                from peft import PeftModel
            except ImportError:
                print("Installing PEFT...")
                import subprocess
                subprocess.check_call([sys.executable, "-m", "pip", "install", "peft"])
                from peft import PeftModel
            
            # Use your Aviation GPT PEFT adapter with compatible base model
            
            # First, try to load PEFT config to get the exact base model
            try:
                from peft import PeftConfig
                peft_config = PeftConfig.from_pretrained(model_id)
                original_base = peft_config.base_model_name_or_path
                print(f"Original base model from PEFT config: {original_base}")
                
                # Map quantized models to their non-quantized equivalents
                base_model_mapping = {
                    "unsloth/llama-2-7b-bnb-4bit": "NousResearch/Llama-2-7b-hf",
                    "unsloth/llama-2-13b-bnb-4bit": "NousResearch/Llama-2-13b-hf", 
                }
                
                # Use non-quantized equivalent for Mac M1 compatibility
                if original_base in base_model_mapping:
                    base_model_id = base_model_mapping[original_base]
                    print(f"Using non-quantized equivalent: {base_model_id}")
                else:
                    # Fallback to a compatible Llama-2-7b model
                    base_model_id = "NousResearch/Llama-2-7b-hf"
                    print(f"Using fallback compatible model: {base_model_id}")
                    
            except Exception as config_error:
                print(f"Could not read PEFT config: {config_error}")
                # Default to compatible Llama-2-7b for your Aviation GPT
                base_model_id = "NousResearch/Llama-2-7b-hf"
                print(f"Using default compatible model: {base_model_id}")
            
            print(f"Loading base model for Aviation GPT adapter: {base_model_id}")
            
            # Load base model optimized for 8GB Mac M1
            base_model = AutoModelForCausalLM.from_pretrained(
                base_model_id,
                torch_dtype=torch.float16,  # Use float16 for memory efficiency
                device_map="cpu",           # Force CPU to avoid GPU memory issues
                trust_remote_code=True,
                low_cpu_mem_usage=True,     # Important for 8GB RAM
                load_in_4bit=False,         # No quantization on CPU
                load_in_8bit=False          # No quantization on CPU
            )
            
            print("Loading PEFT adapter...")
            
            # Load PEFT adapter
            hf_model = PeftModel.from_pretrained(base_model, model_id)
            
            # Set to eval mode
            hf_model.eval()
            gc.collect()
            print("Aviation GPT model loaded successfully!")
            
        except Exception as e:
            error_msg = f"Error loading model: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)
    
    return hf_model, hf_tokenizer

# Data models
class Message(BaseModel):
    role: str
    content: str
    timestamp: str

class Conversation(BaseModel):
    id: str
    messages: List[Message]
    created_at: str
    last_updated: str

# In-memory storage
conversations = {}

def get_conversation(conversation_id: Optional[str] = None) -> Conversation:
    if conversation_id and conversation_id in conversations:
        return conversations[conversation_id]
    
    new_id = conversation_id or str(uuid.uuid4())
    now = datetime.now().isoformat()
    conversations[new_id] = Conversation(
        id=new_id,
        messages=[],
        created_at=now,
        last_updated=now
    )
    return conversations[new_id]

# System prompt (customize this)
def get_system_prompt():
    return """You are an aviation expert AI assistant specialized in aircraft training, procedures, and technical knowledge. 
You provide accurate, safety-focused information about aviation topics including:
- Aircraft systems and operations
- Flight procedures and regulations  
- Weather and navigation
- Safety protocols and emergency procedures
- Pilot training and certification

Always prioritize safety and accuracy in your responses."""

def get_user_prompt_template(user_message: str, context: str = "") -> str:
    if context:
        return f"""Context from document: {context}

User Question: {user_message}

Please provide a comprehensive answer based on the context and your aviation knowledge."""
    else:
        return f"""User Question: {user_message}

Please provide a helpful and accurate response."""

# Chat endpoint - AUTO-LOADS MODEL ON FIRST MESSAGE
@app.post("/chat")
async def chat(
    message: str = Form(...), 
    pdf: Optional[UploadFile] = File(None),
    conversation_id: Optional[str] = Form(None)
):
    conversation = get_conversation(conversation_id)
    conversation.last_updated = datetime.now().isoformat()
    
    context = ""

    # Process PDF if provided
    if pdf:
        try:
            pdf_bytes = await pdf.read()
            context = extract_text_from_pdf(pdf_bytes)
        except Exception as e:
            context = f"(PDF processing failed: {str(e)})"

    # Detect language and translate
    try:
        lang = detect_language(message)
        english_message = translate_text(message, lang)
    except Exception as e:
        lang = "en"
        english_message = message
        print(f"Language detection error: {e}")
    
    # Add user message
    user_message = Message(
        role="user",
        content=english_message,
        timestamp=datetime.now().isoformat()
    )
    conversation.messages.append(user_message)
    
    # *** AUTO-LOAD MODEL ON FIRST MESSAGE ***
    if hf_model is None:
        print("🚀 Loading Aviation GPT model for first use...")
        try:
            get_model_and_tokenizer()
            print("✅ Model loaded successfully!")
        except Exception as e:
            print(f"❌ Model loading failed: {e}")
            # Add error response and return
            ai_message = Message(
                role="assistant",
                content=f"I'm sorry, but I couldn't load the Aviation GPT model. Error: {str(e)}. Please try restarting the server or check your internet connection.",
                timestamp=datetime.now().isoformat()
            )
            conversation.messages.append(ai_message)
            return {
                "response": ai_message.content,
                "conversation_id": conversation.id
            }
    
    # Build messages for model
    model_messages = [{"role": "system", "content": get_system_prompt()}]
    
    # Add recent conversation history (last 6 messages)
    recent_messages = conversation.messages[-6:] if len(conversation.messages) > 6 else conversation.messages
    for msg in recent_messages[:-1]:
        model_messages.append({"role": msg.role, "content": msg.content})
    
    # Add current message with context
    formatted_message = get_user_prompt_template(english_message, context)
    model_messages.append({"role": "user", "content": formatted_message})
    
    # Generate response
    english_response = ""
    try:
        model, tokenizer = get_model_and_tokenizer()
        prompt = format_llama2_conversation(model_messages)
        
        # Tokenize input
        inputs = tokenizer(
            prompt, 
            return_tensors="pt", 
            max_length=1024,
            truncation=True
        )
        
        # Move to model device
        model_device = next(model.parameters()).device
        inputs = {k: v.to(model_device) for k, v in inputs.items()}
        
        # Generate
        with torch.no_grad():
            try:
                output = model.generate(
                    inputs["input_ids"],
                    attention_mask=inputs.get("attention_mask"),
                    max_new_tokens=128,
                    temperature=0.7,
                    top_p=0.9,
                    do_sample=True,
                    pad_token_id=tokenizer.eos_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                    use_cache=True
                )
                
                full_response = tokenizer.decode(output[0], skip_special_tokens=True)
                english_response = extract_assistant_response(full_response, prompt)
                
                del output
                gc.collect()
                
            except torch.OutOfMemoryError:
                english_response = "ERROR: Out of memory. Try with a shorter message or restart the server."
            except Exception as gen_e:
                english_response = f"ERROR: Generation failed - {str(gen_e)}"
                
    except Exception as e:
        english_response = f"ERROR: Model inference failed - {str(e)}"
    
    # Add AI response
    ai_message = Message(
        role="assistant",
        content=english_response,
        timestamp=datetime.now().isoformat()
    )
    conversation.messages.append(ai_message)
    
    # Translate back if needed
    try:
        if lang != "en" and not english_response.startswith("ERROR:"):
            translated_response = translate_text(english_response, lang, reverse=True)
        else:
            translated_response = english_response
    except Exception as e:
        translated_response = english_response
        print(f"Translation error: {e}")

    return {
        "response": translated_response,
        "conversation_id": conversation.id
    }

# Helper functions
def format_llama2_conversation(messages):
    system_prompt = ""
    conversation_messages = []
    
    for message in messages:
        if message["role"] == "system":
            system_prompt = message["content"]
        else:
            conversation_messages.append(message)
    
    if system_prompt:
        formatted_prompt = f"<s>[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n\n"
    else:
        formatted_prompt = "<s>[INST] "
    
    for i, message in enumerate(conversation_messages):
        role = message["role"]
        content = message["content"]
        
        if role == "user":
            if i == 0 and system_prompt:
                formatted_prompt += f"{content} [/INST]"
            elif i == len(conversation_messages) - 1:
                formatted_prompt += f"{content} [/INST]"
            else:
                formatted_prompt += f"{content} [/INST]"
        elif role == "assistant":
            formatted_prompt += f" {content} </s><s>[INST] "
    
    return formatted_prompt

def extract_assistant_response(full_response, prompt):
    try:
        if "[/INST]" in full_response:
            response = full_response.split("[/INST]")[-1].strip()
            response = response.split("</s>")[0].strip()
            if "[INST]" in response:
                response = response.split("[INST]")[0].strip()
        else:
            response = full_response[len(prompt):].strip()
        
        if len(response.strip()) < 5:
            return "I apologize, but I couldn't generate a proper response. Please try rephrasing your question."
        
        return response
        
    except Exception as e:
        return f"ERROR: Response extraction failed - {str(e)}"

# Other endpoints
@app.get("/conversations")
async def get_conversations():
    return {
        "conversations": [
            {
                "id": conv_id,
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

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "device": "CPU (8GB Mac M1 optimized)",
        "model": "Aviation GPT (PEFT Adapter)",
        "model_loaded": hf_model is not None
    }

@app.get("/test")
async def test_endpoint():
    return {"message": "Backend is working!", "timestamp": datetime.now().isoformat()}

@app.post("/load-model")
async def load_model():
    """Manually load the Aviation GPT model"""
    try:
        print("Starting manual model loading...")
        model, tokenizer = get_model_and_tokenizer()
        return {
            "status": "success",
            "message": "Aviation GPT model loaded successfully!",
            "model_loaded": True
        }
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Failed to load model: {str(e)}",
            "model_loaded": False
        }