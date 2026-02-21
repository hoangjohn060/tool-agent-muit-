import tkinter as tk
from tkinter import messagebox, simpledialog, ttk, scrolledtext
import webbrowser
import json
import os
import shutil
import subprocess

import threading
import queue
from datetime import datetime
import sys

# Configuration Paths
USER_PROFILE = os.environ.get('USERPROFILE')
OPENCLAW_CONFIG_PATH = os.path.join(USER_PROFILE, '.openclaw', 'openclaw.json')
AUTH_PROFILES_PATH = os.path.join(USER_PROFILE, '.openclaw', 'auth-profiles.json')
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups')
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Path to the specific python executable in .venv
VENV_PYTHON = os.path.join(CURRENT_DIR, '.venv', 'Scripts', 'python.exe')
BRIDGE_SCRIPT = os.path.join(CURRENT_DIR, 'bridge_server.py')

class AgentConfigApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NullClaw Agent Manager & Bridge")
        self.root.geometry("700x600")

        self.agents = {}
        self.openclaw_data = {}
        self.auth_data = {}
        
        # Bridge State
        self.bridge_processes = {} # Map bot_name -> subprocess
        self.log_queue = queue.Queue()
        # self.is_bridge_running = False # Deprecated

        self.setup_ui()
        self.load_data()
        
        # Start checking for logs
        self.check_log_queue()

    def setup_ui(self):
        # Create Notebook (Tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tab 1: Agents
        self.agents_tab = tk.Frame(self.notebook)
        self.notebook.add(self.agents_tab, text="Agents")
        self.setup_agents_tab()

        # Tab 2: Bridge
        self.bridge_tab = tk.Frame(self.notebook)
        self.notebook.add(self.bridge_tab, text="Bridge Control")
        self.setup_bridge_tab()

        # Tab 3: Chat
        self.chat_tab = tk.Frame(self.notebook)
        self.notebook.add(self.chat_tab, text="💬 Chat")
        self.setup_chat_tab()

    def setup_agents_tab(self):
        list_frame = tk.Frame(self.agents_tab, padx=10, pady=10)
        list_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(list_frame, text="Current Agents:").pack(anchor=tk.W)
        
        self.agent_listbox = tk.Listbox(list_frame)
        self.agent_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.agent_listbox.bind('<<ListboxSelect>>', self.on_select)

        # Buttons
        btn_frame = tk.Frame(self.agents_tab, padx=10, pady=10)
        btn_frame.pack(fill=tk.X)

        tk.Button(btn_frame, text="Add New Agent", command=self.add_agent_dialog).pack(side=tk.LEFT, padx=5)
        self.save_btn = tk.Button(btn_frame, text="💾 Save Changes", command=self.save_data, state=tk.DISABLED)
        self.save_btn.pack(side=tk.RIGHT, padx=5)
        
        # Details Frame
        self.details_frame = tk.LabelFrame(self.agents_tab, text="Agent Details", padx=10, pady=10)
        self.details_frame.pack(fill=tk.X, padx=10, pady=10)

        # ── Provider (chọn trước) ──────────────────────────────────
        tk.Label(self.details_frame, text="Provider:", font=("Arial", 9, "bold")).grid(
            row=0, column=0, sticky=tk.W, pady=3)

        # Map provider_id → (emoji label, model list, key URL)
        # --- ✅ FREE PROVIDERS FIRST ---
        self.PROVIDER_MODELS = {
            "google": {
                "label": "🟢 Google Gemini — Miễn phí",
                "url": "https://aistudio.google.com/app/apikey",
                "models": [
                    "google/gemini-2.0-flash (Free)",
                    "google/gemini-2.0-flash-thinking-exp-01-21 (Free)",
                    "google/gemini-2.0-flash-lite (Free)",
                    "google/gemini-2.0-pro-exp-02-05 (Free)",
                    "google/gemini-1.5-flash (Free)",
                    "google/gemini-1.5-flash-8b (Free)",
                    "google/gemini-1.5-pro",
                ],
            },
            "groq": {
                "label": "⚡ Groq — Miễn phí (nhanh)",
                "url": "https://console.groq.com/keys",
                "models": [
                    "groq/llama-3.3-70b-versatile (Free)",
                    "groq/llama-3.1-8b-instant (Free)",
                    "groq/mixtral-8x7b-32768 (Free)",
                    "groq/gemma2-9b-it (Free)",
                    "groq/deepseek-r1-distill-llama-70b (Free)",
                ],
            },
            "openrouter": {
                "label": "🔀 OpenRouter — có model Free",
                "url": "https://openrouter.ai/keys",
                "models": [
                    "openrouter/google/gemini-2.0-flash-thinking-exp-01-21 (Free)",
                    "openrouter/deepseek/deepseek-r1 (Free)",
                    "openrouter/meta-llama/llama-3.3-70b-instruct (Free)",
                    "openrouter/mistralai/mistral-7b-instruct (Free)",
                    "openrouter/qwen/qwen-2.5-72b-instruct (Free)",
                    "openrouter/anthropic/claude-3-5-sonnet",
                    "openrouter/openai/gpt-4o",
                ],
            },
            "huggingface": {
                "label": "🤗 Hugging Face — Miễn phí",
                "url": "https://huggingface.co/settings/tokens",
                "models": [
                    "huggingface/mistralai/Mistral-7B-Instruct-v0.3 (Free)",
                    "huggingface/google/gemma-2-9b-it (Free)",
                    "huggingface/meta-llama/Meta-Llama-3-8B-Instruct (Free)",
                ],
            },
            "ollama": {
                "label": "🖥 Ollama — Local (Free)",
                "url": "https://ollama.com/library",
                "models": [
                    "ollama/llama3 (Free)",
                    "ollama/mistral (Free)",
                    "ollama/gemma2 (Free)",
                    "ollama/qwen2.5 (Free)",
                    "ollama/deepseek-r1 (Free)",
                ],
            },
            # --- 💳 PAID PROVIDERS ---
            "openai": {
                "label": "🤖 OpenAI (GPT) — Trả phí",
                "url": "https://platform.openai.com/api-keys",
                "models": [
                    "openai/gpt-4o",
                    "openai/gpt-4o-mini",
                    "openai/gpt-4-turbo",
                    "openai/o1",
                    "openai/o1-mini",
                    "openai/o3-mini",
                ],
            },
            "anthropic": {
                "label": "🧠 Anthropic (Claude) — Trả phí",
                "url": "https://console.anthropic.com/settings/keys",
                "models": [
                    "anthropic/claude-3-5-sonnet-20241022",
                    "anthropic/claude-3-5-haiku-20241022",
                    "anthropic/claude-3-opus-20240229",
                    "anthropic/claude-3-haiku-20240307",
                ],
            },
            "deepseek": {
                "label": "🌊 DeepSeek — Trả phí",
                "url": "https://platform.deepseek.com/api_keys",
                "models": [
                    "deepseek/deepseek-chat",
                    "deepseek/deepseek-reasoner",
                ],
            },
            "mistral": {
                "label": "🌪 Mistral AI — Trả phí",
                "url": "https://console.mistral.ai/api-keys/",
                "models": [
                    "mistral/mistral-large-latest",
                    "mistral/mistral-small-latest",
                    "mistral/codestral-latest",
                ],
            },
            "xai": {
                "label": "⚡ xAI (Grok) — Trả phí",
                "url": "https://console.x.ai/",
                "models": [
                    "xai/grok-2",
                    "xai/grok-2-vision",
                    "xai/grok-beta",
                ],
            },
        }


        provider_labels = [v["label"] for v in self.PROVIDER_MODELS.values()]
        self.provider_ids = list(self.PROVIDER_MODELS.keys())

        self.provider_var = tk.StringVar()
        self.provider_combo = ttk.Combobox(
            self.details_frame,
            textvariable=self.provider_var,
            values=provider_labels,
            state="readonly",
            width=35,
        )
        self.provider_combo.grid(row=0, column=1, padx=5, sticky=tk.W, pady=3)
        self.provider_combo.bind("<<ComboboxSelected>>", self._on_provider_selected)

        # Nút mở trang lấy key
        self.get_key_btn = tk.Button(
            self.details_frame, text="🔑 Lấy API Key",
            command=self.open_get_key_url,
            bg="#1565C0", fg="white", relief=tk.FLAT, padx=8
        )
        self.get_key_btn.grid(row=0, column=2, padx=5, sticky=tk.W, pady=3)

        # Label hiển thị URL lấy key (click để mở)
        self.key_url_lbl = tk.Label(
            self.details_frame,
            text="",
            fg="#1565C0",
            cursor="hand2",
            font=("Arial", 8, "underline")
        )
        self.key_url_lbl.grid(row=0, column=3, padx=8, sticky=tk.W)
        self.key_url_lbl.bind("<Button-1>", lambda e: self.open_get_key_url())

        # ── Model ID (lọc theo provider) ──────────────────────────
        tk.Label(self.details_frame, text="Model ID:", font=("Arial", 9, "bold")).grid(
            row=1, column=0, sticky=tk.W, pady=3)
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(
            self.details_frame, textvariable=self.model_var, width=50
        )
        self.model_combo.grid(row=1, column=1, padx=5, sticky=tk.W, pady=3)

        # Nhãn gợi ý "(Free)" 
        self.model_hint_lbl = tk.Label(
            self.details_frame, text="", fg="#2E7D32", font=("Arial", 8, "italic")
        )
        self.model_hint_lbl.grid(row=1, column=2, sticky=tk.W, padx=5)
        self.model_var.trace_add("write", self._on_model_typed)

        # ── API Key ────────────────────────────────────────────────
        tk.Label(self.details_frame, text="API Key:", font=("Arial", 9, "bold")).grid(
            row=2, column=0, sticky=tk.W, pady=3)
        self.apikey_var = tk.StringVar()
        self.apikey_var.trace_add('write', self._on_field_changed)
        
        key_frame = tk.Frame(self.details_frame)
        key_frame.grid(row=2, column=1, sticky=tk.W, pady=3)
        
        tk.Entry(key_frame, textvariable=self.apikey_var, width=40, show="*").pack(side=tk.LEFT, padx=5)
        tk.Button(key_frame, text="Test Key ✅", command=self.test_api_key).pack(side=tk.LEFT, padx=5)

        # Set default provider
        self.provider_combo.current(0)
        self._on_provider_selected()

    def _on_provider_selected(self, event=None):
        """Cập nhật model list và URL lấy key khi provider thay đổi."""
        label = self.provider_var.get()
        provider_id = None
        for pid, pdata in self.PROVIDER_MODELS.items():
            if pdata["label"] == label:
                provider_id = pid
                break
        if not provider_id:
            return
        self._current_provider_id = provider_id
        models = self.PROVIDER_MODELS[provider_id]["models"]
        self.model_combo["values"] = models
        if models:
            self.model_combo.current(0)
        # Cập nhật URL label
        url = self.PROVIDER_MODELS[provider_id].get("url", "")
        self.key_url_lbl.config(text=url)
        self._update_model_hint()
        if self.agent_listbox.curselection():
            self.save_btn.config(state=tk.NORMAL)

    def _on_model_typed(self, *args):
        """Khi người dùng gõ model thủ công → auto-detect provider + bật Save."""
        val = self.model_var.get()
        # Tự detect provider từ tên model
        provider_id = self._detect_provider(val)
        if hasattr(self, 'PROVIDER_MODELS') and provider_id in self.PROVIDER_MODELS:
            label = self.PROVIDER_MODELS[provider_id]["label"]
            if self.provider_var.get() != label:
                self.provider_var.set(label)
                self._current_provider_id = provider_id
        self._update_model_hint()
        if self.agent_listbox.curselection():
            self.save_btn.config(state=tk.NORMAL)

    def _update_model_hint(self):
        """Hiển thị nhãn (Free) nếu model miễn phí."""
        val = self.model_var.get()
        if "(Free)" in val or any(p in val for p in ["groq/", "openrouter/"]):
            self.model_hint_lbl.config(text="🆓 Miễn phí", fg="#2E7D32")
        else:
            self.model_hint_lbl.config(text="")




    def open_get_key_url(self):
        """Mở trang lấy API key của provider hiện đang chọn."""
        provider_id = getattr(self, '_current_provider_id', 'google')
        url = self.PROVIDER_MODELS.get(provider_id, {}).get(
            "url", "https://aistudio.google.com/app/apikey"
        )
        webbrowser.open(url)

    def test_api_key(self):
        key = self.apikey_var.get().strip()
        if not key:
            messagebox.showerror("Lỗi", "Hãy nhập API Key trước.")
            return

        provider_id = getattr(self, '_current_provider_id', 'google')

        # ── Google / Gemini ───────────────────────────────────────
        if provider_id == "google":
            try:
                import google.generativeai as genai
                genai.configure(api_key=key)
                list(genai.list_models(page_size=1))
                messagebox.showinfo("✅ Thành công", "API Key hợp lệ!\nĐã kết nối Google Gemini.")
            except ImportError:
                messagebox.showerror("Lỗi", "Thiếu thư viện google-generativeai.\nChạy: pip install google-generativeai")
            except Exception as e:
                messagebox.showerror("❌ Lỗi API Key", f"Kết nối thất bại!\n\n{e}")

        # ── Groq ──────────────────────────────────────────────────
        elif provider_id == "groq":
            try:
                import urllib.request, urllib.error, json as _json
                req = urllib.request.Request(
                    "https://api.groq.com/openai/v1/models",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "User-Agent": "Mozilla/5.0",
                    }
                )
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = _json.loads(r.read())
                count = len(data.get("data", []))
                messagebox.showinfo("✅ Thành công", f"Groq API Key hợp lệ!\n{count} models khả dụng.")
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    messagebox.showerror("❌ Key Sai", "Key không hợp lệ (401 Unauthorized).\nKiểm tra lại key tại console.groq.com/keys")
                else:
                    messagebox.showerror("❌ Lỗi Groq Key", f"HTTP {e.code}: {e.reason}")
            except Exception as e:
                messagebox.showerror("❌ Lỗi Groq Key", f"Kết nối thất bại!\n\n{e}")

        # ── OpenRouter ────────────────────────────────────────────
        elif provider_id == "openrouter":
            try:
                import urllib.request, urllib.error, json as _json
                req = urllib.request.Request(
                    "https://openrouter.ai/api/v1/auth/key",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com",
                        "User-Agent": "Mozilla/5.0",
                    }
                )
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = _json.loads(r.read())
                label = data.get("data", {}).get("label", "unknown")
                messagebox.showinfo("✅ Thành công", f"OpenRouter API Key hợp lệ!\nAccount: {label}")
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    messagebox.showerror("❌ Key Sai", "Key không hợp lệ (401 Unauthorized).\nKiểm tra lại key tại openrouter.ai/keys")
                else:
                    messagebox.showerror("❌ Lỗi OpenRouter Key", f"HTTP {e.code}: {e.reason}")
            except Exception as e:
                messagebox.showerror("❌ Lỗi OpenRouter Key", f"Kết nối thất bại!\n\n{e}")


        # ── Các provider khác: kiểm tra format ───────────────────
        else:
            prefix_map = {
                "openai": "sk-",
                "anthropic": "sk-ant-",
                "deepseek": "sk-",
                "mistral": "",
                "xai": "xai-",
                "huggingface": "hf_",
            }
            expected = prefix_map.get(provider_id, "")
            if expected and not key.startswith(expected):
                messagebox.showwarning(
                    "⚠ Format Key Sai",
                    f"Key {provider_id.title()} thường bắt đầu bằng '{expected}'\n"
                    f"Key bạn nhập: {key[:8]}...\n\nVẫn lưu được, nhưng hãy kiểm tra lại."
                )
            else:
                messagebox.showinfo(
                    "✅ Format OK",
                    f"Format key {provider_id.title()} có vẻ đúng.\n"
                    f"(Không thể test trực tiếp — cần gọi API thực tế)"
                )


    def setup_bridge_tab(self):
        # Split into PanedWindow
        paned = tk.PanedWindow(self.bridge_tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # LEFT: Bot List
        left_frame = tk.Frame(paned, width=200)
        paned.add(left_frame)
        
        tk.Label(left_frame, text="Active Bridges (Telegram Bots):").pack(anchor=tk.W, pady=(0,5))
        
        self.bot_listbox = tk.Listbox(left_frame)
        self.bot_listbox.pack(fill=tk.BOTH, expand=True)
        self.bot_listbox.bind('<<ListboxSelect>>', self.on_bot_select)
        
        btn_frame = tk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        tk.Button(btn_frame, text="+ Add Bot", command=self.add_bot_dialog).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(btn_frame, text="- Remove", command=self.remove_bot).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # RIGHT: Controls & Logs
        right_frame = tk.Frame(paned)
        paned.add(right_frame)
        
        # Bot Config Frame
        config_frame = tk.LabelFrame(right_frame, text="Bot Configuration", padx=10, pady=10)
        config_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(config_frame, text="Bot Name:").grid(row=0, column=0, sticky=tk.W)
        self.bot_name_var = tk.StringVar()
        tk.Entry(config_frame, textvariable=self.bot_name_var, state='readonly').grid(row=0, column=1, sticky=tk.W, padx=5)
        
        tk.Label(config_frame, text="Bot Token:").grid(row=1, column=0, sticky=tk.W)
        self.bot_token_var = tk.StringVar()
        tk.Entry(config_frame, textvariable=self.bot_token_var, width=50).grid(row=1, column=1, sticky=tk.W, padx=5)
        
        tk.Label(config_frame, text="Target Agent:").grid(row=2, column=0, sticky=tk.W)
        self.target_agent_var = tk.StringVar()
        self.target_agent_combo = ttk.Combobox(config_frame, textvariable=self.target_agent_var, state="readonly")
        self.target_agent_combo.grid(row=2, column=1, sticky=tk.W, padx=5)
        tk.Label(config_frame, text="(Select 'Auto-Router' for keyword routing)").grid(row=2, column=2, sticky=tk.W, padx=5)
        
        tk.Button(config_frame, text="Save Bot Config", command=self.save_bot_config).grid(row=3, column=1, sticky=tk.E, pady=5)

        # Control Frame
        ctrl_frame = tk.LabelFrame(right_frame, text="Control", padx=10, pady=10)
        ctrl_frame.pack(fill=tk.X, padx=10)
        
        self.bot_status_lbl = tk.Label(ctrl_frame, text="Status: STOPPED", fg="red", font=("Arial", 12, "bold"))
        self.bot_status_lbl.pack(side=tk.LEFT, padx=10)
        
        self.bot_start_btn = tk.Button(ctrl_frame, text="Start This Bridge", command=self.start_selected_bridge, bg="#ddffdd")
        self.bot_start_btn.pack(side=tk.LEFT, padx=5)
        
        self.bot_stop_btn = tk.Button(ctrl_frame, text="Stop This Bridge", command=self.stop_selected_bridge, state=tk.DISABLED, bg="#ffdddd")
        self.bot_stop_btn.pack(side=tk.LEFT, padx=5)
        
        # Log Area
        log_frame = tk.LabelFrame(right_frame, text="Live Logs (Selected Bot)", padx=5, pady=5)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, state='disabled', height=15)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def setup_chat_tab(self):
        """Tab chat để gửi/nhận tin nhắn với agent."""
        # Top bar: chọn agent
        top_bar = tk.Frame(self.chat_tab, pady=4)
        top_bar.pack(fill=tk.X, padx=10)

        tk.Label(top_bar, text="Agent:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        self.chat_agent_var = tk.StringVar(value="Auto-Router")
        self.chat_agent_combo = ttk.Combobox(
            top_bar, textvariable=self.chat_agent_var,
            values=["Auto-Router"], state="readonly", width=30
        )
        self.chat_agent_combo.pack(side=tk.LEFT, padx=8)

        tk.Button(top_bar, text="🗑 Xóa lịch sử",
                  command=self.clear_chat).pack(side=tk.RIGHT)
        tk.Button(top_bar, text="🆓 API Key Free",
                  command=self.show_free_api_keys,
                  bg="#4CAF50", fg="white",
                  font=("Arial", 9, "bold"),
                  relief=tk.FLAT, padx=8).pack(side=tk.RIGHT, padx=6)

        # Khung hiển thị tin nhắn
        msg_frame = tk.Frame(self.chat_tab)
        msg_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))

        self.chat_display = tk.Text(
            msg_frame,
            state='disabled',
            wrap=tk.WORD,
            font=("Arial", 10),
            background="#f0f0f0",
            relief=tk.FLAT,
            padx=8, pady=8
        )
        self.chat_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(msg_frame, command=self.chat_display.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_display.config(yscrollcommand=scrollbar.set)

        # Định nghĩa tag màu sắc
        self.chat_display.tag_config(
            "user",
            background="#DCF8C6",   # xanh lá nhạt (như WhatsApp user)
            foreground="#000000",
            justify=tk.RIGHT,
            lmargin1=80, lmargin2=80,
            rmargin=10,
            spacing1=4, spacing3=4
        )
        self.chat_display.tag_config(
            "bot",
            background="#FFFFFF",    # trắng (tin nhắn bot)
            foreground="#000000",
            justify=tk.LEFT,
            lmargin1=10, lmargin2=10,
            rmargin=80,
            spacing1=4, spacing3=4
        )
        self.chat_display.tag_config(
            "system",
            foreground="#888888",
            justify=tk.CENTER,
            spacing1=2, spacing3=2
        )
        self.chat_display.tag_config(
            "sender_user",
            foreground="#075E54",
            font=("Arial", 9, "bold")
        )
        self.chat_display.tag_config(
            "sender_bot",
            foreground="#1565C0",
            font=("Arial", 9, "bold")
        )

        # Khu vực nhập tin nhắn
        input_frame = tk.Frame(self.chat_tab, pady=5)
        input_frame.pack(fill=tk.X, padx=10, pady=(0, 8))

        self.chat_input = tk.Text(input_frame, height=3, font=("Arial", 10),
                                  wrap=tk.WORD)
        self.chat_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.chat_input.bind("<Return>", self.on_chat_enter)
        self.chat_input.bind("<Shift-Return>", lambda e: None)  # Shift+Enter = xuống dòng

        send_btn = tk.Button(
            input_frame, text="Gửi ▶",
            command=self.send_chat_message,
            bg="#128C7E", fg="white",
            font=("Arial", 10, "bold"),
            relief=tk.FLAT, padx=12
        )
        send_btn.pack(side=tk.RIGHT)

        # Hint
        tk.Label(self.chat_tab,
                 text="Enter = Gửi  |  Shift+Enter = Xuống dòng",
                 font=("Arial", 8), fg="gray").pack()

        # Queue cho phản hồi chat
        self.chat_queue = queue.Queue()
        self._check_chat_queue()

    def _append_chat(self, sender, message, tag):
        """Thêm một tin nhắn vào khung hiển thị."""
        self.chat_display.config(state='normal')
        timestamp = datetime.now().strftime("%H:%M")
        sender_tag = "sender_user" if tag == "user" else "sender_bot"

        self.chat_display.insert(tk.END, f"{sender} ({timestamp})\n", sender_tag)
        self.chat_display.insert(tk.END, f"{message.strip()}\n\n", tag)
        self.chat_display.see(tk.END)
        self.chat_display.config(state='disabled')

    def _append_system_msg(self, message):
        """Thêm tin nhắn hệ thống (màu xám, căn giữa)."""
        self.chat_display.config(state='normal')
        self.chat_display.insert(tk.END, f"── {message} ──\n", "system")
        self.chat_display.see(tk.END)
        self.chat_display.config(state='disabled')

    def clear_chat(self):
        self.chat_display.config(state='normal')
        self.chat_display.delete(1.0, tk.END)
        self.chat_display.config(state='disabled')
        self._append_system_msg("Lịch sử đã được xóa")

    def on_chat_enter(self, event):
        """Nhấn Enter gửi tin nhắn (Shift+Enter = xuống dòng)."""
        if not (event.state & 0x1):  # Không giữ Shift
            self.send_chat_message()
            return "break"  # Ngăn xuống dòng

    def send_chat_message(self):
        """Gửi tin nhắn từ ô input tới agent."""
        message = self.chat_input.get("1.0", tk.END).strip()
        if not message:
            return

        # Hiện tin nhắn người dùng
        self._append_chat("Bạn", message, "user")
        self.chat_input.delete("1.0", tk.END)

        agent_name = self.chat_agent_var.get()
        self._append_system_msg(f"Đang gửi tới {agent_name}...")

        # Gửi trong thread riêng để không đóng băng UI
        threading.Thread(
            target=self._call_agent_thread,
            args=(message, agent_name),
            daemon=True
        ).start()

    def _call_agent_thread(self, message, agent_name):
        """Gọi agent trực tiếp qua Gemini API (đọc key từ NullClaw config)."""
        try:
            import google.generativeai as genai

            # --- 1. Đọc config ---
            def _load_json(p):
                try:
                    with open(p, 'r', encoding='utf-8-sig') as f:
                        return json.load(f)
                except Exception:
                    return {}

            oc_cfg   = _load_json(OPENCLAW_CONFIG_PATH)
            auth_cfg = _load_json(AUTH_PROFILES_PATH)

            # --- 2. Xác định agent thực (Auto-Router → defaults) ---
            actual_agent = "defaults" if agent_name == "Auto-Router" else agent_name
            agent_conf = oc_cfg.get("agents", {}).get(actual_agent, {})
            if not agent_conf:
                agent_conf = oc_cfg.get("agents", {}).get("defaults", {})

            # --- 3. Lấy model và dọn dẹp tên model ---
            model_id = agent_conf.get("model", {}).get(
                "primary", "gemini-2.0-flash-thinking-exp-1219"
            )
            # Remove (Free) if it somehow got saved
            clean_model = model_id.replace(" (Free)", "").strip()
            
            # --- 4. Xác định provider từ auth profile ─────────
            # Đầu tiên detect từ model name chưa cắt prefix
            provider = self._detect_provider(clean_model)
            
            # Khử tiền tố provider cho API gọi trực tiếp (Groq, OpenAI, Anthropic, DeepSeek, Mistral, xAI không cần tiền tố)
            if provider in ["google", "groq", "openai", "anthropic", "deepseek", "mistral", "xai", "ollama"]:
                if "/" in clean_model and clean_model.startswith(provider + "/"):
                    clean_model = clean_model.split("/", 1)[1]
            
            # Tìm profile theo thứ tự ưu tiên nhất: <provider>:<agent_name>
            api_key = None
            profiles = auth_cfg.get("profiles", {})
            
            # 1. Tìm chính xác cho agent và provider này
            specific_keys = [
                f"{provider}:{actual_agent}",
                f"{provider}:{agent_name}",
                f"{provider}:defaults"
            ]
            
            for candidate in specific_keys:
                if candidate in profiles:
                    api_key = profiles[candidate].get("key") or profiles[candidate].get("apiKey")
                    if api_key: break
            
            # 2. Nếu không tìm thấy, quét tất cả profile để xem có cái nào map với provider không
            if not api_key:
                for k, v in profiles.items():
                    if isinstance(v, dict):
                        # Khóa có thể lưu kiểu `groq:agentName` hoặc `type`: `api_key` `provider`: `groq`
                        p_name = v.get("provider")
                        if p_name == provider or (":" in k and k.split(":")[0] == provider):
                            api_key = v.get("key") or v.get("apiKey")
                            if api_key:
                                break
                                
            # 3. Fallback cuối: quét đại một API key bất kỳ (rủi ro sai model cao)
            if not api_key and provider == "google":
                for k, v in profiles.items():
                    if isinstance(v, dict):
                        candidate_key = v.get("key") or v.get("apiKey")
                        if candidate_key:
                            api_key = candidate_key
                            break
                            


            if provider == "ollama":
                # Ollama không cần api_key thực
                pass
            elif not api_key:
                self.chat_queue.put(("error", agent_name,
                    "❌ Chưa cấu hình API Key!\n"
                    "Vào tab Agents → chọn agent → nhập API Key → Save Changes."
                ))
                return

            # --- 5. Gọi API dựa trên Provider ---
            try:
                if provider == "google":
                    import google.generativeai as genai
                    genai.configure(api_key=api_key)
                    model_obj = genai.GenerativeModel(
                        model_name=clean_model,
                        generation_config={"temperature": 0.7, "top_p": 0.95, "max_output_tokens": 8192}
                    )
                    chat_session = model_obj.start_chat(history=[])
                    response = chat_session.send_message(message)
                    self.chat_queue.put(("bot", agent_name, response.text))
                    
                elif provider in ["openai", "groq", "openrouter", "deepseek", "mistral", "xai"]:
                    import urllib.request
                    import urllib.error
                    import json as _json

                    endpoints = {
                        "openai": "https://api.openai.com/v1/chat/completions",
                        "groq": "https://api.groq.com/openai/v1/chat/completions",
                        "openrouter": "https://openrouter.ai/api/v1/chat/completions",
                        "deepseek": "https://api.deepseek.com/chat/completions",
                        "mistral": "https://api.mistral.ai/v1/chat/completions",
                        "xai": "https://api.x.ai/v1/chat/completions"
                    }
                    url = endpoints[provider]
                    
                    data = {
                        "model": clean_model,
                        "messages": [{"role": "user", "content": message}],
                        "temperature": 0.7
                    }
                    
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "User-Agent": "OpenClawManager/1.0"
                    }
                    if provider == "openrouter":
                        headers["HTTP-Referer"] = "https://github.com/hoang"

                    req = urllib.request.Request(url, data=_json.dumps(data).encode('utf-8'), headers=headers)
                    with urllib.request.urlopen(req, timeout=30) as r:
                        resp_data = _json.loads(r.read())
                        reply = resp_data["choices"][0]["message"]["content"]
                        self.chat_queue.put(("bot", agent_name, reply))

                elif provider == "anthropic":
                    import urllib.request
                    import urllib.error
                    import json as _json
                    
                    url = "https://api.anthropic.com/v1/messages"
                    data = {
                        "model": clean_model,
                        "max_tokens": 4096,
                        "messages": [{"role": "user", "content": message}],
                        "temperature": 0.7
                    }
                    headers = {
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                        "User-Agent": "OpenClawManager/1.0"
                    }
                    req = urllib.request.Request(url, data=_json.dumps(data).encode('utf-8'), headers=headers)
                    with urllib.request.urlopen(req, timeout=30) as r:
                        resp_data = _json.loads(r.read())
                        reply = resp_data["content"][0]["text"]
                        self.chat_queue.put(("bot", agent_name, reply))
                        
                elif provider == "ollama":
                    import urllib.request
                    import urllib.error
                    import json as _json
                    
                    url = "http://127.0.0.1:11434/api/chat"
                    data = {
                        "model": clean_model,
                        "messages": [{"role": "user", "content": message}],
                        "stream": False
                    }
                    req = urllib.request.Request(url, data=_json.dumps(data).encode('utf-8'), headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=120) as r:
                        resp_data = _json.loads(r.read())
                        reply = resp_data["message"]["content"]
                        self.chat_queue.put(("bot", agent_name, reply))
                        
                else:
                    self.chat_queue.put(("error", agent_name, f"❌ Provider '{provider}' chưa được hỗ trợ chat trực tiếp trong GUI."))
                
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "quota" in err_str.lower() or "RESOURCE_EXHAUSTED" in err_str:
                    self.chat_queue.put(("error", agent_name, f"⚠ Hết quota (Rate Limit) cho provider {provider.title()}!"))
                elif "401" in err_str or "API_KEY_INVALID" in err_str or "Unauthorized" in err_str:
                    self.chat_queue.put(("error", agent_name, f"❌ API Key không hợp lệ cho {provider.title()}!\nKiểm tra lại khóa."))
                elif "404" in err_str:
                    self.chat_queue.put(("error", agent_name, f"❌ Model '{clean_model}' không tồn tại hoặc không hỗ trợ bởi {provider.title()}."))
                else:
                    self.chat_queue.put(("error", agent_name, f"❌ Lỗi kết nối {provider.title()}: {e}"))
        except ImportError:
            self.chat_queue.put(("error", agent_name,
                "❌ Thiếu thư viện google-generativeai.\n"
                "Chạy: pip install google-generativeai"
            ))
        except Exception as e:
            self.chat_queue.put(("error", agent_name, f"❌ Lỗi: {e}"))

    def show_free_api_keys(self):
        """Hiển thị cửa sổ popup danh sách API key miễn phí."""
        win = tk.Toplevel(self.root)
        win.title("🆓 Danh sách API Key Miễn Phí")
        win.geometry("680x580")
        win.resizable(True, True)
        win.grab_set()  # Modal

        # Header
        header = tk.Frame(win, bg="#1B5E20", pady=12)
        header.pack(fill=tk.X)
        tk.Label(header,
                 text="🆓  API Key Miễn Phí cho AI Agents",
                 font=("Arial", 14, "bold"),
                 bg="#1B5E20", fg="white").pack()
        tk.Label(header,
                 text="Nhấn vào tên nhà cung cấp để mở trang lấy key",
                 font=("Arial", 9),
                 bg="#1B5E20", fg="#A5D6A7").pack()

        # Scrollable content
        frame_outer = tk.Frame(win)
        frame_outer.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        canvas = tk.Canvas(frame_outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame_outer, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mouse wheel scroll
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        win.protocol("WM_DELETE_WINDOW", lambda: [canvas.unbind_all("<MouseWheel>"), win.destroy()])

        # ─── Danh sách API key free ───
        FREE_APIS = [
            {
                "provider": "🟢 Google AI Studio",
                "url": "https://aistudio.google.com/app/apikey",
                "models": [
                    "gemini-2.0-flash-thinking-exp-1219",
                    "gemini-2.0-pro-exp-02-05",
                    "gemini-2.0-flash-exp",
                    "gemini-2.0-flash-lite-preview-02-05",
                    "gemini-1.5-flash (miễn phí 15 req/phút)",
                ],
                "limit": "15–60 req/phút • 1,500 req/ngày (Flash)",
                "note": "Miễn phí hoàn toàn, không cần thẻ tín dụng",
                "color": "#E8F5E9",
                "badge_color": "#2E7D32",
            },
            {
                "provider": "⚡ Groq (LLaMA / Mixtral)",
                "url": "https://console.groq.com/keys",
                "models": [
                    "llama-3.3-70b-versatile",
                    "llama-3.1-8b-instant",
                    "mixtral-8x7b-32768",
                    "gemma2-9b-it",
                ],
                "limit": "30 req/phút • 14,400 req/ngày",
                "note": "Tốc độ cao, miễn phí, LLaMA 3.3 mạnh nhất hiện tại",
                "color": "#FFF3E0",
                "badge_color": "#E65100",
            },
            {
                "provider": "🔀 OpenRouter (nhiều mô hình)",
                "url": "https://openrouter.ai/keys",
                "models": [
                    "google/gemini-2.0-flash-thinking-exp-1219 (FREE)",
                    "meta-llama/llama-3.3-70b-instruct (FREE)",
                    "deepseek/deepseek-r1 (FREE)",
                    "mistralai/mistral-7b-instruct (FREE)",
                    "qwen/qwen-2.5-72b-instruct (FREE)",
                ],
                "limit": "Tuỳ model • Một số model hoàn toàn miễn phí",
                "note": "Truy cập hàng trăm model qua 1 API key duy nhất",
                "color": "#EDE7F6",
                "badge_color": "#4527A0",
            },
            {
                "provider": "🧠 DeepSeek",
                "url": "https://platform.deepseek.com/api_keys",
                "models": [
                    "deepseek-chat (V3)",
                    "deepseek-reasoner (R1)",
                ],
                "limit": "$5 credit miễn phí khi đăng ký",
                "note": "Mô hình reasoning mạnh, giá rẻ nhất thị trường",
                "color": "#E3F2FD",
                "badge_color": "#1565C0",
            },
            {
                "provider": "🤗 Hugging Face Inference API",
                "url": "https://huggingface.co/settings/tokens",
                "models": [
                    "mistralai/Mistral-7B-Instruct-v0.3",
                    "google/gemma-2-9b-it",
                    "meta-llama/Meta-Llama-3-8B-Instruct",
                ],
                "limit": "Miễn phí (giới hạn tốc độ)",
                "note": "Hàng ngàn model mã nguồn mở, miễn phí cơ bản",
                "color": "#FFF8E1",
                "badge_color": "#F57F17",
            },
            {
                "provider": "🌊 Cohere",
                "url": "https://dashboard.cohere.com/api-keys",
                "models": [
                    "command-r-plus",
                    "command-r",
                    "command-light",
                ],
                "limit": "5 req/phút • 1,000 req/tháng (trial)",
                "note": "Phù hợp RAG và tìm kiếm ngữ nghĩa",
                "color": "#FCE4EC",
                "badge_color": "#880E4F",
            },
            {
                "provider": "🆓 Mistral AI (La Plateforme)",
                "url": "https://console.mistral.ai/api-keys/",
                "models": [
                    "mistral-small-latest",
                    "open-mistral-7b",
                    "open-mixtral-8x7b",
                ],
                "limit": "€5 credit miễn phí khi đăng ký",
                "note": "Model châu Âu, riêng tư, không train data",
                "color": "#E0F7FA",
                "badge_color": "#006064",
            },
        ]

        for api in FREE_APIS:
            card = tk.Frame(scroll_frame, bg=api["color"],
                            relief=tk.RIDGE, bd=1)
            card.pack(fill=tk.X, padx=10, pady=5, ipady=6)

            # Header dòng: tên provider (clickable) + badge giới hạn
            row1 = tk.Frame(card, bg=api["color"])
            row1.pack(fill=tk.X, padx=10, pady=(6, 2))

            link = tk.Label(row1, text=api["provider"],
                            font=("Arial", 11, "bold underline"),
                            bg=api["color"], fg=api["badge_color"],
                            cursor="hand2")
            link.pack(side=tk.LEFT)
            link.bind("<Button-1>", lambda e, u=api["url"]: webbrowser.open(u))

            # Badge giới hạn
            badge = tk.Label(row1,
                             text=f"  {api['limit']}  ",
                             font=("Arial", 8),
                             bg=api["badge_color"], fg="white",
                             padx=4, pady=2)
            badge.pack(side=tk.RIGHT)

            # Note
            tk.Label(card, text=f"  ℹ {api['note']}",
                     font=("Arial", 9, "italic"),
                     bg=api["color"], fg="#555555",
                     anchor=tk.W).pack(fill=tk.X, padx=10)

            # Danh sách models
            sep = tk.Label(card, text="  Models hỗ trợ:",
                           font=("Arial", 9, "bold"),
                           bg=api["color"], fg="#333333",
                           anchor=tk.W)
            sep.pack(fill=tk.X, padx=10, pady=(4, 0))

            for model in api["models"]:
                tk.Label(card, text=f"      • {model}",
                         font=("Arial", 9),
                         bg=api["color"], fg="#333333",
                         anchor=tk.W).pack(fill=tk.X, padx=10)

            # Nút copy URL
            btn_row = tk.Frame(card, bg=api["color"])
            btn_row.pack(fill=tk.X, padx=10, pady=(4, 4))

            def _open(u=api["url"]):
                webbrowser.open(u)

            tk.Button(btn_row,
                      text="🔗 Mở trang lấy API Key",
                      command=_open,
                      bg=api["badge_color"], fg="white",
                      font=("Arial", 9), relief=tk.FLAT,
                      padx=10, pady=3
                      ).pack(side=tk.RIGHT)

        # Footer
        footer = tk.Frame(win, bg="#ECEFF1", pady=6)
        footer.pack(fill=tk.X)
        tk.Label(footer,
                 text="💡 Tip: Sau khi lấy key, vào tab Agents → chọn agent → dán key vào ô API Key → Save",
                 font=("Arial", 9), bg="#ECEFF1", fg="#37474F").pack()
        tk.Button(footer, text="Đóng", command=win.destroy,
                  font=("Arial", 9), padx=20).pack(pady=4)

    def _check_chat_queue(self):
        """Kiểm tra queue chat và hiển thị phản hồi từ agent."""
        while not self.chat_queue.empty():
            try:
                item = self.chat_queue.get_nowait()
                msg_type, sender, content = item
                if msg_type == "bot":
                    self._append_chat(f"🤖 {sender}", content, "bot")
                elif msg_type == "error":
                    self._append_chat(f"⚠ {sender}", content, "bot")
            except queue.Empty:
                break
        self.root.after(200, self._check_chat_queue)

    def on_select(self, event):
        selection = self.agent_listbox.curselection()
        if not selection: return

        agent_name = self.agent_listbox.get(selection[0])
        agent_data = self.agents.get(agent_name, {})

        raw_model = agent_data.get('model', {}).get('primary', '')

        # --- Set Provider dropdown (dùng emoji label) ---
        provider_id = self._detect_provider(raw_model)
        self._current_provider_id = provider_id
        if hasattr(self, 'PROVIDER_MODELS') and provider_id in self.PROVIDER_MODELS:
            label = self.PROVIDER_MODELS[provider_id]["label"]
            self.provider_var.set(label)
            # Cập nhật danh sách model theo provider
            models = self.PROVIDER_MODELS[provider_id]["models"]
            self.model_combo["values"] = models
        else:
            self.provider_var.set(provider_id)

        # --- Set Model (thêm "(Free)" nếu có trong danh sách) ---
        matched = None
        if hasattr(self, 'PROVIDER_MODELS'):
            for m in self.PROVIDER_MODELS.get(provider_id, {}).get('models', []):
                if m.replace(' (Free)', '') == raw_model:
                    matched = m  # dùng tên đầy đủ kể cả "(Free)"
                    break
        self.model_var.set(matched if matched else raw_model)
        self._update_model_hint()

        # --- Load API Key ---
        api_key = ""
        profiles = self.auth_data.get('profiles', {})
        
        # 1. Search for exact provider:agent
        candidate_keys = [f"{provider_id}:{agent_name}", f"{provider_id}:defaults"]
        for candidate in candidate_keys:
            if candidate in profiles:
                api_key = profiles[candidate].get('key', '') or profiles[candidate].get('apiKey', '')
                if api_key: break
                
        # 2. Search anywhere in the profiles for a key that maps to this agent_name
        if not api_key:
            for k, v in profiles.items():
                if isinstance(v, dict) and ":" in k:
                    # e.g., groq:ap1 -> parts[1] is 'ap1'
                    parts = k.split(":", 1)
                    if len(parts) > 1 and parts[1] == agent_name:
                        api_key = v.get("key", "") or v.get("apiKey", "")
                        if api_key: break
                        
        self.apikey_var.set(api_key)

        self.save_btn.config(state=tk.DISABLED)
    
    def _detect_provider(self, model):
        """Auto-detect provider from model name (prefix-first matching)."""
        m = model.lower().replace(" (free)", "").strip()
        # Kiểm tra prefix chính xác trước
        if m.startswith("google/") or "gemini" in m:
            return "google"
        elif m.startswith("groq/") or "groq" in m or "llama" in m or "mixtral" in m:
            return "groq"
        elif m.startswith("openrouter/"):
            return "openrouter"
        elif m.startswith("openai/") or "gpt" in m:
            return "openai"
        elif m.startswith("anthropic/") or "claude" in m:
            return "anthropic"
        elif m.startswith("deepseek/") or "deepseek" in m:
            return "deepseek"
        elif m.startswith("mistral/") or "mistral" in m or "codestral" in m:
            return "mistral"
        elif m.startswith("xai/") or "grok" in m:
            return "xai"
        elif m.startswith("huggingface/"):
            return "huggingface"
        elif m.startswith("ollama/"):
            return "ollama"
        return "google"  # default



    def _auto_detect_provider(self, *args):
        """Called when model changes - auto set provider dropdown."""
        model = self.model_var.get().replace(" (Free)", "").strip()
        provider = self._detect_provider(model)
        self.provider_var.set(provider)

    def enable_save(self):
        self.save_btn.config(state=tk.NORMAL)

    def _on_field_changed(self, *args):
        """Bật nút Save khi người dùng chỉnh sửa bất kỳ trường nào (chỉ khi đã chọn agent)."""
        if self.agent_listbox.curselection():
            self.save_btn.config(state=tk.NORMAL)

    def add_agent_dialog(self):
        """Dialog thêm agent mới với provider/model selector và key format hint."""
        # Thông tin format key theo provider
        KEY_INFO = {
            "google":      {"prefix": "AIza...",   "example": "AIzaSy..."},
            "groq":        {"prefix": "gsk_...",    "example": "gsk_abc123..."},
            "openrouter":  {"prefix": "sk-or-...",  "example": "sk-or-v1-abc..."},
            "openai":      {"prefix": "sk-...",     "example": "sk-proj-abc..."},
            "anthropic":   {"prefix": "sk-ant-...", "example": "sk-ant-api03-abc..."},
            "deepseek":    {"prefix": "sk-...",     "example": "sk-abc123..."},
            "mistral":     {"prefix": "...",        "example": "32ký tự hex"},
            "xai":         {"prefix": "xai-...",    "example": "xai-abc123..."},
            "huggingface": {"prefix": "hf_...",     "example": "hf_abc123..."},
            "ollama":      {"prefix": "(không cần)", "example": "chạy local, không cần key"},
        }

        win = tk.Toplevel(self.root)
        win.title("➕ Thêm Agent Mới")
        win.geometry("560x400")
        win.resizable(False, False)
        win.grab_set()

        pad = {"padx": 12, "pady": 6}

        # ── Tên agent ─────────────────────────────────────────────
        tk.Label(win, text="Tên Agent:", font=("Arial", 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, **pad)
        name_var = tk.StringVar()
        tk.Entry(win, textvariable=name_var, width=38, font=("Arial", 10)).grid(
            row=0, column=1, columnspan=2, sticky=tk.W, **pad)

        # ── Provider ──────────────────────────────────────────────
        tk.Label(win, text="Provider:", font=("Arial", 10, "bold")).grid(
            row=1, column=0, sticky=tk.W, **pad)
        dlg_provider_var = tk.StringVar()
        provider_labels = [v["label"] for v in self.PROVIDER_MODELS.values()]
        dlg_provider_combo = ttk.Combobox(
            win, textvariable=dlg_provider_var,
            values=provider_labels, state="readonly", width=36
        )
        dlg_provider_combo.grid(row=1, column=1, columnspan=2, sticky=tk.W, **pad)
        dlg_provider_combo.current(0)

        # ── Model ─────────────────────────────────────────────────
        tk.Label(win, text="Model ID:", font=("Arial", 10, "bold")).grid(
            row=2, column=0, sticky=tk.W, **pad)
        dlg_model_var = tk.StringVar()
        dlg_model_combo = ttk.Combobox(win, textvariable=dlg_model_var, width=36)
        dlg_model_combo.grid(row=2, column=1, columnspan=2, sticky=tk.W, **pad)

        dlg_free_lbl = tk.Label(win, text="", fg="#2E7D32", font=("Arial", 8, "italic"))
        dlg_free_lbl.grid(row=2, column=3, sticky=tk.W, padx=4)

        # ── API Key ───────────────────────────────────────────────
        tk.Label(win, text="API Key:", font=("Arial", 10, "bold")).grid(
            row=3, column=0, sticky=tk.W, **pad)
        dlg_key_var = tk.StringVar()
        dlg_key_entry = tk.Entry(win, textvariable=dlg_key_var, width=36,
                                 show="*", font=("Arial", 10))
        dlg_key_entry.grid(row=3, column=1, sticky=tk.W, **pad)

        # Nút lấy key
        def _open_key_url():
            pid = _get_pid()
            url = self.PROVIDER_MODELS.get(pid, {}).get("url", "")
            if url:
                webbrowser.open(url)

        tk.Button(win, text="🔑 Lấy Key", command=_open_key_url,
                  bg="#1565C0", fg="white", relief=tk.FLAT, padx=6).grid(
            row=3, column=2, sticky=tk.W, padx=4)

        # ── Hint: format key + link ───────────────────────────────
        hint_frame = tk.Frame(win, bg="#F3F4F6", relief=tk.GROOVE, bd=1)
        hint_frame.grid(row=4, column=0, columnspan=4, sticky=tk.EW,
                       padx=12, pady=(0, 8))

        hint_icon  = tk.Label(hint_frame, text="ℹ️", bg="#F3F4F6", font=("Arial", 11))
        hint_icon.pack(side=tk.LEFT, padx=(8, 4), pady=6)

        hint_text  = tk.Label(hint_frame, text="", bg="#F3F4F6",
                              font=("Arial", 9), justify=tk.LEFT, anchor=tk.W)
        hint_text.pack(side=tk.LEFT, pady=6, fill=tk.X, expand=True)

        hint_url   = tk.Label(hint_frame, text="", fg="#1565C0",
                              bg="#F3F4F6", cursor="hand2",
                              font=("Arial", 8, "underline"))
        hint_url.pack(side=tk.RIGHT, padx=8, pady=6)
        hint_url.bind("<Button-1>", lambda e: _open_key_url())

        def _get_pid():
            lbl = dlg_provider_var.get()
            for pid, pdata in self.PROVIDER_MODELS.items():
                if pdata["label"] == lbl:
                    return pid
            return "google"

        def _update_hint(*args):
            pid = _get_pid()
            info = KEY_INFO.get(pid, {})
            models = self.PROVIDER_MODELS.get(pid, {}).get("models", [])
            url    = self.PROVIDER_MODELS.get(pid, {}).get("url", "")

            # Cập nhật model list
            dlg_model_combo["values"] = models
            if models:
                dlg_model_combo.current(0)

            # Cập nhật hint
            prefix_ex = info.get("prefix", "")
            example   = info.get("example", "")
            if pid == "ollama":
                hint_text.config(text="Ollama chạy local — không cần API key.\nĐể trống ô API Key.")
                dlg_key_entry.config(state=tk.DISABLED, bg="#EEEEEE")
            else:
                dlg_key_entry.config(state=tk.NORMAL, bg="white")
                hint_text.config(
                    text=f"Format key: {prefix_ex}   Ví dụ: {example}"
                )
            hint_url.config(text=url)

            # Nhãn Free
            model_val = dlg_model_var.get()
            if "(Free)" in model_val or pid in ("groq", "huggingface", "ollama"):
                dlg_free_lbl.config(text="🆓 Miễn phí")
            else:
                dlg_free_lbl.config(text="")

        dlg_provider_combo.bind("<<ComboboxSelected>>", _update_hint)
        dlg_model_var.trace_add("write", _update_hint)
        _update_hint()  # Init

        # ── Nút Save / Cancel ─────────────────────────────────────
        btn_row = tk.Frame(win)
        btn_row.grid(row=5, column=0, columnspan=4, pady=12)

        def _save():
            name    = name_var.get().strip()
            pid     = _get_pid()
            model   = dlg_model_var.get().replace(" (Free)", "").strip()
            api_key = dlg_key_var.get().strip()

            if not name:
                messagebox.showerror("Lỗi", "Tên agent không được trống!", parent=win)
                return
            if name in self.agents:
                messagebox.showerror("Lỗi", f"Agent '{name}' đã tồn tại!", parent=win)
                return
            if not model:
                messagebox.showerror("Lỗi", "Hãy chọn Model!", parent=win)
                return

            # Lưu vào self.agents
            self.agents[name] = {"model": {"primary": model}}

            # Lưu API key vào auth_data
            if api_key and pid != "ollama":
                profile_key = f"{pid}:{name}"
                if "profiles" not in self.auth_data:
                    self.auth_data["profiles"] = {}
                self.auth_data["profiles"][profile_key] = {
                    "type": "api_key",
                    "provider": pid,
                    "key": api_key,
                    "apiKey": api_key,
                }
                
                # Also set in openclaw_data for the engine
                if 'auth' not in self.openclaw_data:
                    self.openclaw_data['auth'] = {'profiles': {}}
                if 'profiles' not in self.openclaw_data['auth']:
                    self.openclaw_data['auth']['profiles'] = {}
                self.openclaw_data['auth']['profiles'][profile_key] = {
                    "provider": pid,
                    "mode": "api_key"
                }

            # Đồng bộ vào openclaw_data để refresh_list hiển thị đúng
            self.openclaw_data['agents'] = self.agents
            self.refresh_list()
            
            # Automatically select the newly added agent so users can see its API key and details
            try:
                items = self.agent_listbox.get(0, tk.END)
                if name in items:
                    idx = items.index(name)
                    self.agent_listbox.selection_clear(0, tk.END)
                    self.agent_listbox.selection_set(idx)
                    self.on_select(None)
            except Exception:
                pass

            self.save_btn.config(state=tk.NORMAL)
            win.destroy()
            messagebox.showinfo("✅ Thành công",
                f"Agent '{name}' đã được thêm!\n"
                f"Provider: {pid}  |  Model: {model}\n\n"
                "Nhấn 💾 Save Changes để lưu vĩnh viễn.")

        tk.Button(btn_row, text="✅ Thêm Agent", command=_save,
                  bg="#2E7D32", fg="white", font=("Arial", 10, "bold"),
                  padx=20, pady=6, relief=tk.FLAT).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_row, text="Hủy", command=win.destroy,
                  font=("Arial", 10), padx=20, pady=6).pack(side=tk.LEFT, padx=10)



    def load_data(self):
        try:
            if os.path.exists(OPENCLAW_CONFIG_PATH):
                with open(OPENCLAW_CONFIG_PATH, 'r', encoding='utf-8-sig') as f:
                    self.openclaw_data = json.load(f)
            else:
                self.openclaw_data = {"agents": {"defaults": {}}}
            
            # Load Telegram Bots
            telegram_conf = self.openclaw_data.get('channels', {}).get('telegram', {})
            self.bot_configs = telegram_conf.get('bots', {})
            
            # Migration: If old single token exists, migrate to a "Default Bot"
            old_token = telegram_conf.get('botToken')
            if old_token and not self.bot_configs:
                self.bot_configs['Default Bot'] = {"token": old_token, "agent": "Auto-Router"}
                # Cleanup old key eventually? For now keep for backward compat but UI uses bots dict
            
            # Refresh Bot List
            self.refresh_bot_list()

            if os.path.exists(AUTH_PROFILES_PATH):
                with open(AUTH_PROFILES_PATH, 'r', encoding='utf-8-sig') as f:
                    self.auth_data = json.load(f)
            else:
                self.auth_data = {"version": 1, "profiles": {}}
            
            # --- Update Model Combo Values ---
            # Extract models directly from PROVIDER_MODELS to ensure consistency
            display_models = []
            other_models = set()
            
            for provider_id, pdata in self.PROVIDER_MODELS.items():
                for model in pdata.get("models", []):
                    if "(Free)" in model:
                        display_models.append(model)
                    else:
                        other_models.add(model)
            
            # Add from existing NullClaw config if available (user's custom models)
            defaults = self.openclaw_data.get('agents', {}).get('defaults', {})
            if 'models' in defaults:
                for m in defaults['models'].keys():
                    if m not in display_models and f"{m} (Free)" not in display_models:
                        other_models.add(m)

            # Combine: Free first, then sorted others
            final_list = display_models + sorted(list(other_models))

            self.model_combo['values'] = final_list
            if not self.model_var.get() and final_list:
                self.model_combo.current(0)  # Select first by default if empty
            
            self.refresh_list()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load config: {e}")

    def refresh_list(self):
        self.agent_listbox.delete(0, tk.END)
        self.agents = self.openclaw_data.get('agents', {})
        agent_names = []
        for name in self.agents:
            if name == 'defaults': continue
            self.agent_listbox.insert(tk.END, name)
            agent_names.append(name)
        
        all_agents = ["Auto-Router"] + sorted(agent_names)

        # Update Bridge Tab Agent Combo
        if hasattr(self, 'target_agent_combo'):
            self.target_agent_combo['values'] = all_agents

        # Update Chat Tab Agent Combo
        if hasattr(self, 'chat_agent_combo'):
            self.chat_agent_combo['values'] = all_agents

    def refresh_bot_list(self):
         self.bot_listbox.delete(0, tk.END)
         for name in self.bot_configs:
             self.bot_listbox.insert(tk.END, name)




    def save_data(self):
        selection = self.agent_listbox.curselection()
        if selection:
            name = self.agent_listbox.get(selection[0])
            if name in self.agents:
                if 'model' not in self.agents[name]: self.agents[name]['model'] = {}
                
                # Clean model name (remove " (Free)" suffix if present)
                raw_model = self.model_var.get()
                clean_model = raw_model.replace(" (Free)", "").strip()
                self.agents[name]['model']['primary'] = clean_model
                
                provider = getattr(self, '_current_provider_id', 'google')
                profile_key = f"{provider}:{name}"
                
                if 'auth' not in self.openclaw_data: self.openclaw_data['auth'] = {'profiles': {}}
                
                self.openclaw_data['auth']['profiles'][profile_key] = {
                    "provider": provider,
                    "mode": "api_key"
                }
                
                # Update / Create Auth Profile with API Key
                input_key = self.apikey_var.get().strip()
                
                if profile_key not in self.auth_data['profiles']:
                    self.auth_data['profiles'][profile_key] = {
                        "type": "api_key",
                        "provider": provider,
                        "key": input_key if input_key else "PLACEHOLDER",
                        "apiKey": input_key if input_key else "PLACEHOLDER"
                    }
                else:
                    # Update existing
                    if input_key: # Only update if user typed something to avoid overwriting with empty if logic fails? 
                        # Actually if user clears it we should probably clear it.
                        self.auth_data['profiles'][profile_key]['key'] = input_key
                        self.auth_data['profiles'][profile_key]['apiKey'] = input_key


        # (Telegram token is saved separately via Bridge tab > Save Bot Config)

        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            if os.path.exists(OPENCLAW_CONFIG_PATH):
                shutil.copy(OPENCLAW_CONFIG_PATH, os.path.join(BACKUP_DIR, f"openclaw_{timestamp}.json"))
            if os.path.exists(AUTH_PROFILES_PATH):
                shutil.copy(AUTH_PROFILES_PATH, os.path.join(BACKUP_DIR, f"auth-profiles_{timestamp}.json"))
        except Exception as e:
            messagebox.showerror("Backup Error", f"Could not create backup: {e}")
            return
        
        try:
            with open(OPENCLAW_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.openclaw_data, f, indent=2)
            
            with open(AUTH_PROFILES_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.auth_data, f, indent=2)

            messagebox.showinfo("Success", f"Configuration saved!\nBackups created in {BACKUP_DIR}")
            self.save_btn.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save config: {e}")

    # --- Bot Management ---
    def add_bot_dialog(self):
        name = simpledialog.askstring("New Bot", "Enter unique Bot Name (ID):")
        if not name: return
        if name in self.bot_configs:
            messagebox.showwarning("Exists", "Bot name already exists.")
            return
        
        self.bot_configs[name] = {"token": "", "agent": "Auto-Router"}
        self.refresh_bot_list()
        self.save_bot_config_data() # Save to disk immediately or just memory? Memory first.

    def remove_bot(self):
        selection = self.bot_listbox.curselection()
        if not selection: return
        name = self.bot_listbox.get(selection[0])
        
        if name in self.bridge_processes and self.bridge_processes[name]:
             messagebox.showwarning("Running", "Stop the bridge before removing.")
             return

        if messagebox.askyesno("Confirm", f"Remove bot '{name}'?"):
            del self.bot_configs[name]
            self.refresh_bot_list()
            self.save_bot_config_data()
            
            # Clear right pane if it was selected
            self.bot_name_var.set("")
            self.bot_token_var.set("")
            self.target_agent_var.set("")

    def on_bot_select(self, event):
        selection = self.bot_listbox.curselection()
        if not selection: return
        name = self.bot_listbox.get(selection[0])
        
        conf = self.bot_configs.get(name, {})
        self.bot_name_var.set(name)
        self.bot_token_var.set(conf.get('token', ''))
        self.target_agent_var.set(conf.get('agent', 'Auto-Router'))
        
        self.update_bot_control_ui(name)

    def save_bot_config(self):
        name = self.bot_name_var.get()
        if not name or name not in self.bot_configs: return
        
        self.bot_configs[name]['token'] = self.bot_token_var.get().strip()
        self.bot_configs[name]['agent'] = self.target_agent_var.get()
        
        self.save_bot_config_data()
        messagebox.showinfo("Saved", f"Configuration for '{name}' updated.")

    def save_bot_config_data(self):
        # Save to openclaw.json
        if 'channels' not in self.openclaw_data: self.openclaw_data['channels'] = {}
        if 'telegram' not in self.openclaw_data['channels']: self.openclaw_data['channels']['telegram'] = {}
        
        self.openclaw_data['channels']['telegram']['bots'] = self.bot_configs
        # Remove old single token to avoid confusion? 
        # self.openclaw_data['channels']['telegram'].pop('botToken', None) 
        
        try:
            with open(OPENCLAW_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.openclaw_data, f, indent=2)
        except Exception as e:
            messagebox.showerror("Error", f"Could not save config: {e}")

    # --- Bridge Process Logic ---
    def start_selected_bridge(self):
        name = self.bot_name_var.get()
        if not name: return
        
        if name in self.bridge_processes and self.bridge_processes[name]:
            return # Already running

        token = self.bot_token_var.get().strip()
        if not token:
            messagebox.showerror("Error", "Bot Token is required.")
            return
            
        agent = self.target_agent_var.get()
        
        # Check execution mode (Frozen/Compiled or Script)
        is_frozen = getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS') or "__compiled__" in globals()
        
        if is_frozen:
            # Running as standalone exe
            # Assume bridge_server.exe is in the same directory
            bridge_exe = os.path.join(os.path.dirname(sys.executable), "bridge_server.exe")
            if not os.path.exists(bridge_exe):
                 # Fallback for one-dir mode where it might be in internal path? 
                 # Nuitka standalone puts things in .dist usually.
                 # Let's assume user builds them side-by-side.
                 messagebox.showerror("Error", f"Bridge executable not found at: {bridge_exe}")
                 return
            
            cmd = [bridge_exe, '--token', token]
        else:
            # Running as script
            python_exe = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable
            cmd = [python_exe, BRIDGE_SCRIPT, '--token', token]
            
        if agent and agent != "Auto-Router":
            cmd.extend(['--agent', agent])
        
        self.log_message(f"[{name}] Requesting start...", name)
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            # Start Process
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=os.path.dirname(bridge_exe) if is_frozen else CURRENT_DIR, # Set CWD to exe dir
                startupinfo=startupinfo
            )
            
            self.bridge_processes[name] = proc
            self.update_bot_control_ui(name)
            
            threading.Thread(target=self.reader_thread, args=(proc.stdout, name), daemon=True).start()
            threading.Thread(target=self.reader_thread, args=(proc.stderr, name), daemon=True).start()
            
            self.log_message(f"[{name}] Started.", name)
            
        except Exception as e:
            self.log_message(f"[{name}] Error starting: {e}", name)

    def stop_selected_bridge(self):
        name = self.bot_name_var.get()
        if not name: return
        
        proc = self.bridge_processes.get(name)
        if not proc: return
        
        self.log_message(f"[{name}] Requesting stop...", name)
        try:
            proc.terminate()
            self.bridge_processes[name] = None
            self.update_bot_control_ui(name)
            self.log_message(f"[{name}] Terminated.", name)
        except Exception as e:
            self.log_message(f"[{name}] Error stopping: {e}", name)

    def update_bot_control_ui(self, name):
        # Only update if the selected bot matches 'name'
        if self.bot_name_var.get() != name: return
        
        is_running = False
        if name in self.bridge_processes and self.bridge_processes[name]:
            if self.bridge_processes[name].poll() is None:
                is_running = True
            else:
                self.bridge_processes[name] = None # Clean up if dead
        
        if is_running:
            self.bot_status_lbl.config(text="Status: RUNNING", fg="green")
            self.bot_start_btn.config(state=tk.DISABLED)
            self.bot_stop_btn.config(state=tk.NORMAL)
        else:
            self.bot_status_lbl.config(text="Status: STOPPED", fg="red")
            self.bot_start_btn.config(state=tk.NORMAL)
            self.bot_stop_btn.config(state=tk.DISABLED)

    def reader_thread(self, pipe, bot_name):
        try:
            with pipe:
                for line in iter(pipe.readline, ''):
                    self.log_queue.put((bot_name, line))
        except Exception:
            pass
        finally:
             pass # Polling handles cleanup

    def check_log_queue(self):
        while not self.log_queue.empty():
            try:
                item = self.log_queue.get_nowait()
                if isinstance(item, tuple):
                    bot_name, msg = item
                    # Append Log
                    self.log_append(f"[{bot_name}] {msg}")
                    
                    # Check status update if this bot is selected
                    if self.bot_name_var.get() == bot_name:
                         # We can't easily poll process here efficiently without map lookup
                         # Let's just rely on periodic UI update or user interaction?
                         # Or just auto-check current selected bot status
                         pass
                else:
                    # Legacy or system message
                    self.log_append(str(item))
            except queue.Empty:
                break
        
        # Periodic check for the currently selected bot's status (to detect unexpected crashes)
        selected = self.bot_name_var.get()
        if selected:
            self.update_bot_control_ui(selected)
             
        self.root.after(100, self.check_log_queue)

    def log_append(self, msg):
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, msg)
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def log_message(self, msg, bot_name="System"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put((bot_name, f"[{timestamp}] {msg}\n"))

    def cleanup(self):
        """Stops all running bridges."""
        for name, proc in self.bridge_processes.items():
            if proc:
                try:
                    proc.terminate()
                except:
                    pass
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = AgentConfigApp(root)
    root.protocol("WM_DELETE_WINDOW", app.cleanup)
    root.mainloop()
