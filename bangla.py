#!/usr/bin/env python3
# tools/bangla.py — Bangla Voice Translator, runs as its own process
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.tts import speak_female

from datetime import datetime


class BanglaVoiceTranslator:
    def speak(self, text: str):
        speak_female(text)

    def listen(self) -> str | None:
        try:
            text = input("Bangla input: ").strip()
            if text:
                print(f"[Bangla] {text}")
                return text
        except EOFError:
            pass
        return None

    def translate(self, bangla_text: str) -> str | None:
        try:
            from deep_translator import GoogleTranslator
            result = GoogleTranslator(source='bn', target='en').translate(bangla_text)
            print(f"[Translated] {result}")
            return result
        except ImportError:
            try:
                from googletrans import Translator
                result = Translator().translate(bangla_text, src='bn', dest='en')
                print(f"[Translated] {result.text}")
                return result.text
            except Exception as e:
                print(f"Translation error: {e}")
                return None
        except Exception as e:
            print(f"Translation error: {e}")
            return None

    def reply(self, text: str) -> str:
        t = text.lower()
        if any(w in t for w in ['hello', 'hi', 'hey']):
            return "Hello! How can I help you?"
        if 'how are you' in t:
            return "I'm doing great! How about you?"
        if 'your name' in t or 'who are you' in t:
            return "I am a Bangla voice translator."
        if 'time' in t:
            return f"The current time is {datetime.now().strftime('%I:%M %p')}"
        if 'date' in t or 'today' in t:
            return f"Today is {datetime.now().strftime('%B %d, %Y')}"
        if any(w in t for w in ['thank']):
            return "You're welcome!"
        if any(w in t for w in ['bye', 'goodbye', 'quit', 'exit']):
            return "Goodbye! Have a great day!"
        return f"I heard: {text}. I'm still learning!"

    def run(self):
        self.speak("Bangla voice translator is ready. Type in Bangla to begin.")
        while True:
            bangla = self.listen()
            if not bangla:
                continue
            english = self.translate(bangla)
            if not english:
                continue
            bye = any(w in english.lower() for w in ['bye', 'goodbye', 'quit', 'exit'])
            self.speak(self.reply(english))
            if bye:
                break
            print("-" * 40)


if __name__ == '__main__':
    BanglaVoiceTranslator().run()