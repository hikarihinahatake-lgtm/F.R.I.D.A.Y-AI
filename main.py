
import os
import json
import threading
import webbrowser
import subprocess
from pathlib import Path
from datetime import datetime

import customtkinter as ctk
import psutil
from groq import Groq

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

try:
    import speech_recognition as sr
except ImportError:
    sr = None


APP_NAME = "F.R.I.D.A.Y."
MODEL = "openai/gpt-oss-120b"

APP_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "FridayAI"
CONFIG_FILE = APP_DIR / "config.json"

SYSTEM_PROMPT = """
You are F.R.I.D.A.Y., a sophisticated, calm, intelligent personal AI
assistant. You are warm, articulate, observant, and lightly witty.
You address the user naturally. Be helpful and concise.
You are running on the user's Windows computer.
Never claim to have performed an action unless the application confirms it.
"""


def load_config():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(data):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8"
    )


class FridayApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("F.R.I.D.A.Y. | Personal AI")
        self.geometry("1100x720")
        self.minsize(850, 600)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.config_data = load_config()
        self.api_key = self.config_data.get("api_key", "")
        self.history = []
        self.busy = False


      self.tts_engine = None

        if pyttsx3:
            try:
                self.tts_engine = pyttsx3.init()

                voices = self.tts_engine.getProperty("voices")

                female_voice = None

                for voice in voices:
                    voice_name = voice.name.lower()

                    if any(name in voice_name for name in ["zira", "female", "aria", "jenny", "hazel"]):
                        female_voice = voice.id
                        break

                if female_voice:
                    self.tts_engine.setProperty("voice", female_voice)

                self.tts_engine.setProperty("rate", 175)
                self.tts_engine.setProperty("volume", 0.9)

            except Exception:
                self.tts_engine = None

        self.build_interface()
        self.refresh_system_stats()
        self.write_message(
            "F.R.I.D.A.Y.",
            "Good evening. Systems are online. "
            "How may I assist you?"
        )

        if not self.api_key:
            self.after(700, self.ask_for_api_key)

    def build_interface(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(
            self, width=225, corner_radius=0
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        ctk.CTkLabel(
            self.sidebar,
            text="F.R.I.D.A.Y.",
            font=("Segoe UI", 27, "bold"),
            text_color="#70CFFF"
        ).pack(pady=(35, 5))

        ctk.CTkLabel(
            self.sidebar,
            text="PERSONAL AI SYSTEM",
            font=("Segoe UI", 10),
            text_color="#8195A8"
        ).pack(pady=(0, 35))

        self.status_label = ctk.CTkLabel(
            self.sidebar,
            text="● SYSTEM ONLINE",
            text_color="#58D6A0",
            font=("Segoe UI", 12, "bold")
        )
        self.status_label.pack(pady=10)

        ctk.CTkLabel(
            self.sidebar,
            text="SYSTEM MONITOR",
            font=("Segoe UI", 11, "bold"),
            text_color="#8195A8"
        ).pack(pady=(35, 12))

        self.cpu_label = self.stat_label("CPU: --%")
        self.ram_label = self.stat_label("MEMORY: --%")
        self.battery_label = self.stat_label("BATTERY: --")

        ctk.CTkLabel(
            self.sidebar,
            text="QUICK ACCESS",
            font=("Segoe UI", 11, "bold"),
            text_color="#8195A8"
        ).pack(pady=(35, 12))

        self.side_button("Open Google", lambda: self.open_site(
            "https://www.google.com"
        ))
        self.side_button("Open YouTube", lambda: self.open_site(
            "https://www.youtube.com"
        ))
        self.side_button("Open Gmail", lambda: self.open_site(
            "https://mail.google.com"
        ))
        self.side_button("API Settings", self.ask_for_api_key)

        # Main panel
        self.main = ctk.CTkFrame(self, corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self.main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=25, pady=20)

        ctk.CTkLabel(
            header,
            text="Personal Assistant",
            font=("Segoe UI", 23, "bold")
        ).pack(side="left")

        self.clock_label = ctk.CTkLabel(
            header,
            text="",
            text_color="#8EA6BB"
        )
        self.clock_label.pack(side="right")
        self.update_clock()

        # Conversation area
        self.chat = ctk.CTkTextbox(
            self.main,
            corner_radius=12,
            font=("Segoe UI", 14),
            wrap="word"
        )
        self.chat.grid(
            row=1, column=0, sticky="nsew",
            padx=25, pady=(0, 15)
        )
        self.chat.configure(state="disabled")

        # Input area
        bottom = ctk.CTkFrame(self.main, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="ew", padx=25, pady=20)
        bottom.grid_columnconfigure(0, weight=1)

        self.message_input = ctk.CTkEntry(
            bottom,
            height=48,
            placeholder_text="Ask F.R.I.D.A.Y. anything..."
        )
        self.message_input.grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        self.message_input.bind("<Return>", self.send_message)

        self.send_button = ctk.CTkButton(
            bottom,
            text="SEND",
            width=90,
            height=48,
            command=self.send_message
        )
        self.send_button.grid(row=0, column=1, padx=4)

        self.mic_button = ctk.CTkButton(
            bottom,
            text="🎙 SPEAK",
            width=110,
            height=48,
            fg_color="#263E59",
            hover_color="#365A7A",
            command=self.listen_once
        )
        self.mic_button.grid(row=0, column=2, padx=(4, 0))

        self.footer = ctk.CTkLabel(
            self.main,
            text="F.R.I.D.A.Y. is ready • AI responses require an internet connection",
            text_color="#71869A",
            font=("Segoe UI", 10)
        )
        self.footer.grid(row=3, column=0, pady=(0, 12))

    def stat_label(self, text):
        label = ctk.CTkLabel(
            self.sidebar,
            text=text,
            font=("Segoe UI", 12),
            text_color="#D0DCE7"
        )
        label.pack(anchor="w", padx=25, pady=5)
        return label

    def side_button(self, text, command):
        ctk.CTkButton(
            self.sidebar,
            text=text,
            height=35,
            anchor="w",
            fg_color="transparent",
            hover_color="#263E59",
            command=command
        ).pack(fill="x", padx=15, pady=3)

    def write_message(self, speaker, message):
        self.chat.configure(state="normal")
        self.chat.insert("end", f"\n{speaker}\n", "speaker")
        self.chat.insert("end", f"{message}\n\n")
        self.chat.see("end")
        self.chat.configure(state="disabled")

    def send_message(self, event=None):
        if self.busy:
            return

        message = self.message_input.get().strip()
        if not message:
            return

        self.message_input.delete(0, "end")
        self.write_message("YOU", message)

        if self.handle_local_command(message):
            return

        if not self.api_key:
            self.write_message(
                "F.R.I.D.A.Y.",
                "Please add your Groq API key in API Settings first."
            )
            return

        self.busy = True
        self.status_label.configure(
            text="● THINKING",
            text_color="#F2C66D"
        )

        threading.Thread(
            target=self.ask_groq,
            args=(message,),
            daemon=True
        ).start()

    def ask_groq(self, message):
        try:
            client = Groq(api_key=self.api_key)

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]
            messages.extend(self.history[-12:])
            messages.append({"role": "user", "content": message})

            result = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=900
            )

            answer = result.choices[0].message.content.strip()

            self.history.append(
                {"role": "user", "content": message}
            )
            self.history.append(
                {"role": "assistant", "content": answer}
            )

            self.after(0, lambda: self.finish_response(answer))

        except Exception as error:
            error_text = str(error)
            self.after(
                0,
                lambda: self.finish_response(
                    "I couldn't reach the AI service. "
                    f"Please check your connection and API key.\n\n"
                    f"Details: {error_text[:350]}"
                )
            )

    def finish_response(self, answer):
        self.write_message("F.R.I.D.A.Y.", answer)
        self.busy = False
        self.status_label.configure(
            text="● SYSTEM ONLINE",
            text_color="#58D6A0"
        )
        threading.Thread(
            target=self.speak,
            args=(answer,),
            daemon=True
        ).start()

    def speak(self, text):
        if not self.tts_engine:
            return
        try:
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
        except Exception:
            pass

    def listen_once(self):
        if not sr:
            self.write_message(
                "F.R.I.D.A.Y.",
                "Voice input isn't available. Please check the installation."
            )
            return

        self.mic_button.configure(
            text="LISTENING...",
            state="disabled"
        )
        threading.Thread(
            target=self.capture_voice,
            daemon=True
        ).start()

    def capture_voice(self):
        try:
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                self.after(
                    0,
                    lambda: self.footer.configure(
                        text="Listening... Please speak."
                    )
                )
                recognizer.adjust_for_ambient_noise(
                    source, duration=0.5
                )
                audio = recognizer.listen(
                    source, timeout=5, phrase_time_limit=12
                )

            words = recognizer.recognize_google(audio)
            self.after(
                0,
                lambda: self.message_input.insert(0, words)
            )
            self.after(
                0,
                lambda: self.footer.configure(
                    text="Voice captured. Press SEND when ready."
                )
            )

        except Exception as error:
            self.after(
                0,
                lambda: self.footer.configure(
                    text=f"Microphone unavailable: {str(error)[:100]}"
                )
            )
        finally:
            self.after(
                0,
                lambda: self.mic_button.configure(
                    text="🎙 SPEAK",
                    state="normal"
                )
            )

    def ask_for_api_key(self):
        dialog = ctk.CTkInputDialog(
            text="Enter your Groq API key:",
            title="F.R.I.D.A.Y. | API Setup"
        )
        key = dialog.get_input()

        if key and key.strip():
            self.api_key = key.strip()
            self.config_data["api_key"] = self.api_key
            save_config(self.config_data)
            self.write_message(
                "F.R.I.D.A.Y.",
                "API key saved locally. AI connection is ready."
            )

    def handle_local_command(self, message):
        command = message.lower().strip()

        if command in ("open google", "open google chrome"):
            self.open_site("https://www.google.com")
            return True

        if command in ("open youtube", "open youtube.com"):
            self.open_site("https://www.youtube.com")
            return True

        if command in ("open gmail", "open email"):
            self.open_site("https://mail.google.com")
            return True

        if command in ("what time is it", "time"):
            self.write_message(
                "F.R.I.D.A.Y.",
                datetime.now().strftime("It is %I:%M %p.")
            )
            return True

        if command in ("what is today's date", "what's the date", "date"):
            self.write_message(
                "F.R.I.D.A.Y.",
                datetime.now().strftime("Today is %A, %B %d, %Y.")
            )
            return True

        return False

    def open_site(self, url):
        webbrowser.open(url)
        self.write_message(
            "F.R.I.D.A.Y.",
            f"Opening {url}"
        )

    def refresh_system_stats(self):
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            battery = psutil.sensors_battery()

            self.cpu_label.configure(text=f"CPU: {cpu:.0f}%")
            self.ram_label.configure(text=f"MEMORY: {ram:.0f}%")

            if battery:
                self.battery_label.configure(
                    text=f"BATTERY: {battery.percent:.0f}%"
                )
            else:
                self.battery_label.configure(
                    text="BATTERY: N/A"
                )
        except Exception:
            pass

        self.after(2000, self.refresh_system_stats)

    def update_clock(self):
        self.clock_label.configure(
            text=datetime.now().strftime("%A • %I:%M:%S %p")
        )
        self.after(1000, self.update_clock)


if __name__ == "__main__":
    app = FridayApp()
    app.mainloop()
