import logging
import json
import os
import asyncio
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration Paths - Expand user profile
OPENCLAW_CONFIG_PATH = os.path.expandvars(r"%USERPROFILE%\.openclaw\openclaw.json")
AUTH_PROFILES_PATH = os.path.expandvars(r"%USERPROFILE%\.openclaw\auth-profiles.json")

def load_json_config(path):
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config from {path}: {e}")
        return {}

# Load Initial Config
config = load_json_config(OPENCLAW_CONFIG_PATH)
TELEGRAM_TOKEN = config.get("channels", {}).get("telegram", {}).get("botToken") or os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    logger.error("Telegram Bot Token not found in .env or openclaw.json")
    print("Error: No Telegram Token found.")
    exit(1)

# Agent Router Configuration
# Agent Router Configuration
AGENT_ROUTING = {
    # Specific agents first to avoid partial matches on generic words
    "reviewer": ["review", "check", "audit", "assess", "kiểm tra", "đánh giá", "sao chép"],
    "writer": ["write blog", "post", "content", "viết bài", "soạn thảo", "sáng tạo"],
    # Coder last as it has generic terms like 'code'
    "coder": ["code", "fix", "bug", "implement", "function", "class", "viết hàm", "viết code", "sửa lỗi", "lập trình"],
}
DEFAULT_AGENT = "defaults" 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Hi {user.mention_html()}! I am the OpenClaw Multi-Agent Bridge.\nI can route your requests to different agents (Coder, Reviewer, etc.) powered by Google Gemini.\nJust mention an agent or chat!",
        parse_mode='HTML'
    )

def route_message(message_text: str) -> str:
    """Determine which agent should handle the message."""
    message_text_lower = message_text.lower()
    for agent, keywords in AGENT_ROUTING.items():
        if any(keyword in message_text_lower for keyword in keywords):
            return agent
    return DEFAULT_AGENT

def _detect_provider(model: str) -> str:
    """Auto-detect provider from model name."""
    m = model.lower().replace(" (free)", "").strip()
    if m.startswith("google/") or "gemini" in m: return "google"
    elif m.startswith("groq/") or "groq" in m or "llama" in m or "mixtral" in m: return "groq"
    elif m.startswith("gpt-") or m.startswith("o1") or m.startswith("o3") or m.startswith("openai/"): return "openai"
    elif m.startswith("claude") or m.startswith("anthropic/"): return "anthropic"
    elif m.startswith("openrouter/"): return "openrouter"
    elif m.startswith("deepseek/"): return "deepseek"
    elif m.startswith("mistral/"): return "mistral"
    elif m.startswith("xai/") or m.startswith("grok"): return "xai"
    elif m.startswith("huggingface/"): return "huggingface"
    elif m.startswith("ollama/"): return "ollama"
    return "google"

def get_api_key_for_agent(agent_name: str, config: dict, auth_profiles: dict, provided_model: str = "") -> tuple[str, str]:
    """Retrieves (API Key, Provider) for the specific agent based on its model."""
    provider = _detect_provider(provided_model)
    profiles = auth_profiles.get("profiles", {})
    api_key = None
    
    specific_keys = [f"{provider}:{agent_name}", f"{provider}:defaults"]
    for candidate in specific_keys:
        if candidate in profiles:
            api_key = profiles[candidate].get("key") or profiles[candidate].get("apiKey")
            if api_key: break
            
    if not api_key:
        for k, v in profiles.items():
            if isinstance(v, dict):
                p_name = v.get("provider")
                if p_name == provider or (":" in k and k.split(":")[0] == provider):
                    api_key = v.get("key") or v.get("apiKey")
                    if api_key: break
                    
    # Fallback cuối
    if not api_key and provider == "google":
        for k, v in profiles.items():
            if isinstance(v, dict):
                candidate_key = v.get("key") or v.get("apiKey")
                if candidate_key:
                    return candidate_key, provider
                    
    return api_key, provider

async def process_with_model(agent_name: str, message_text: str, history_context: str = "") -> str:
    """Calls the appropriate API to generate a response."""
    current_config = load_json_config(OPENCLAW_CONFIG_PATH)
    auth_profiles = load_json_config(AUTH_PROFILES_PATH)
    
    # Lấy Agent Config
    agent_conf = current_config.get("agents", {}).get(agent_name, {})
    if not agent_conf and agent_name == DEFAULT_AGENT:
         agent_conf = current_config.get("agents", {}).get("defaults", {})
         
    model_id = agent_conf.get("model", {}).get("primary", "google/gemini-2.0-flash-thinking-exp-1219")
    clean_model_id = model_id.replace(" (Free)", "").strip()
    
    api_key, provider = get_api_key_for_agent(agent_name, current_config, auth_profiles, clean_model_id)
    
    if provider == "ollama":
        api_key = "dummy"
    elif not api_key:
        return f"[System] Lỗi: Không tìm thấy API Key cho agent '{agent_name}'. Vui lòng cấu hình trên giao diện."

    # Khử tiền tố model
    if provider in ["google", "groq", "openai", "anthropic", "deepseek", "mistral", "xai", "ollama"]:
        if "/" in clean_model_id and clean_model_id.startswith(provider + "/"):
            clean_model_id = clean_model_id.split("/", 1)[1]

    try:
        full_prompt = f"Context:\n{history_context}\n\nUser: {message_text}\n\nYou are {agent_name}."
        
        if provider == "google":
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name=clean_model_id, 
                generation_config={"temperature": 0.7, "top_p": 0.95, "max_output_tokens": 8192}
            )
            response = await asyncio.to_thread(model.generate_content, full_prompt)
            return response.text
            
        elif provider in ["openai", "groq", "openrouter", "deepseek", "mistral", "xai"]:
            import urllib.request, json as _json
            endpoints = {
                "openai": "https://api.openai.com/v1/chat/completions",
                "groq": "https://api.groq.com/openai/v1/chat/completions",
                "openrouter": "https://openrouter.ai/api/v1/chat/completions",
                "deepseek": "https://api.deepseek.com/chat/completions",
                "mistral": "https://api.mistral.ai/v1/chat/completions",
                "xai": "https://api.x.ai/v1/chat/completions"
            }
            data = {
                "model": clean_model_id,
                "messages": [{"role": "user", "content": full_prompt}],
                "temperature": 0.7
            }
            headers = {
                "Authorization": f"Bearer {api_key}", 
                "Content-Type": "application/json",
                "User-Agent": "OpenClawBridge/1.0"
            }
            if provider == "openrouter": headers["HTTP-Referer"] = "https://github.com/hoang"
            
            req = urllib.request.Request(endpoints[provider], data=_json.dumps(data).encode('utf-8'), headers=headers)
            def _call():
                with urllib.request.urlopen(req, timeout=45) as r:
                    return _json.loads(r.read())["choices"][0]["message"]["content"]
            
            return await asyncio.to_thread(_call)
            
        elif provider == "anthropic":
            import urllib.request, json as _json
            data = {"model": clean_model_id, "max_tokens": 4096, "messages": [{"role": "user", "content": full_prompt}]}
            headers = {
                "x-api-key": api_key, 
                "anthropic-version": "2023-06-01", 
                "content-type": "application/json",
                "User-Agent": "OpenClawBridge/1.0"
            }
            req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=_json.dumps(data).encode('utf-8'), headers=headers)
            def _call():
                with urllib.request.urlopen(req, timeout=45) as r:
                    return _json.loads(r.read())["content"][0]["text"]
            return await asyncio.to_thread(_call)
            
        else:
            return f"[System] Provider '{provider}' chưa được hỗ trợ trên Bridge."

    except Exception as e:
        logger.error(f"API Error ({provider}): {e}")
        return f"[System] Lỗi kết nối {provider}: {str(e)}"

import argparse
import sys

# ... imports ...

# Shared History Directory
HISTORY_DIR = os.path.expandvars(r"%USERPROFILE%\.openclaw\history")
os.makedirs(HISTORY_DIR, exist_ok=True)

def append_to_history(chat_id, sender, message):
    """Appends a message to the shared history file."""
    try:
        path = os.path.join(HISTORY_DIR, f"{chat_id}.txt")
        timestamp = asyncio.get_event_loop().time() # Or datetime
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{sender}]: {message}\n")
    except Exception as e:
        logger.error(f"Failed to write history: {e}")

def get_history(chat_id, limit=2000): # limit chars or lines? Chars for prompt context
    """Reads the last N characters of history."""
    try:
        path = os.path.join(HISTORY_DIR, f"{chat_id}.txt")
        if not os.path.exists(path): return ""
        
        with open(path, "r", encoding="utf-8") as f:
            # Simple read all for now, maybe tail later
            content = f.read()
            return content[-limit:] if limit else content
    except Exception as e:
        logger.error(f"Failed to read history: {e}")
        return ""



# Update handle_message to use FORCED_AGENT if set
async def handle_message_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    user_msg = update.message.text
    user_name = update.effective_user.first_name
    
    # 1. Log incoming user message to shared history
    append_to_history(chat_id, user_name, user_msg)
    
    if FORCED_AGENT:
        target_agent = FORCED_AGENT
    else:
        target_agent = route_message(user_msg)
    
    logger.info(f"Routing message to agent: {target_agent}")
    
    # Notify user we are working
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    # 2. Get Shared History
    history_context = get_history(chat_id)
    
    # Route to actual AI
    response_text = await process_with_model(target_agent, user_msg, history_context)
    
    # 3. Log outgoing agent message to shared history
    append_to_history(chat_id, target_agent, response_text)
    
    # Format response
    if FORCED_AGENT:
         final_response = response_text 
    else:
         final_response = f"<b>[{target_agent.upper()}]</b>\n{response_text}"
    
    try:
        await context.bot.send_message(chat_id=chat_id, text=final_response, parse_mode='HTML')
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=final_response)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="OpenClaw Telegram Bridge")
    parser.add_argument("--agent", type=str, help="Specific agent ID to run exclusively (e.g., ap1)", default=None)
    parser.add_argument("--token", type=str, help="Telegram Bot Token", default=None)
    args = parser.parse_args()

    # If --agent is provided, this instance will ONLY route to that agent
    FORCED_AGENT = args.agent
    if args.token:
        TELEGRAM_TOKEN = args.token

    if FORCED_AGENT:
        logger.info(f"Target Agent FORCED to: {FORCED_AGENT.upper()}")
        
    print(f"[{FORCED_AGENT or 'Default Bot'}] Requesting start...")
    try:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message_wrapper))
        
        logger.info("Application configured. Starting polling...")
        print(f"[{FORCED_AGENT or 'Default Bot'}] Started.")
        app.run_polling(drop_pending_updates=True)
    except KeyboardInterrupt:
        print("\nBridge stopped.")
