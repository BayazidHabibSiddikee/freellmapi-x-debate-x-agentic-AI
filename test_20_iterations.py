import requests
import time

URL = "http://localhost:5050/api/chat"
EXPORT_URL = "http://localhost:5050/api/export"

characters = ["Ghost - The bug", "Evok", "Marin", "Hector| Isekai as the Villain"]

history = []

def test_turn(user_msg=None):
    global history
    if user_msg:
        history.append({"speaker": "Sword", "text": user_msg})
    
    payload = {
        "topic": "The ethics of AI in creative arts",
        "characters": characters,
        "history": history,
        "user_name": "Sword",
        "mode": "random"
    }

    try:
        resp = requests.post(URL, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        print(f"[{data['speaker']}]: {data['text']}\n")
        history.append({"speaker": data["speaker"], "text": data["text"]})
    except Exception as e:
        print(f"Failed: {e}")

print("Starting 20 Iterations Test as User 'Sword'...")

user_prompts = [
    "Hey everyone, are you all here?",
    "So what do you guys think about AI replacing artists?",
    "Wait, let's back up. Is AI art even real art?",
    "Marin, what do you think?",
    "Hector, you always have a villainous take. Give it to us."
]

for i in range(20):
    print(f"--- Iteration {i+1} ---")
    if i < len(user_prompts):
        msg = user_prompts[i]
        print(f"[User (Sword)]: {msg}")
        test_turn(msg)
    else:
        test_turn()
    time.sleep(2)

print("Exporting chat to verify...")
export_payload = {
    "topic": "The ethics of AI in creative arts",
    "characters": characters,
    "history": history
}
try:
    resp = requests.post(EXPORT_URL, json=export_payload)
    print("Export Response:", resp.json())
except Exception as e:
    print(f"Export failed: {e}")
