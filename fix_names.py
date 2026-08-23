import json
import os
import re

with open("characters.json", "r") as f:
    chars = json.load(f)

for c in chars:
    name = c.get("name", "")
    # Remove weird characters like | ¦ ~ [ ]
    name = re.sub(r'[\|¦~\[\]]', ' ', name)
    # Remove strings like "Isekai as the Villain", "The Control Devil", "7 Days, 7 Personalities"
    # Actually just split by common separators and take the first part
    if '-' in name:
        name = name.split('-')[0]
    if '_' in name:
        name = name.replace('_', ' ')
    if '|' in name:
        name = name.split('|')[0]
    # Remove extra spaces
    name = re.sub(r'\s+', ' ', name).strip()
    
    # Specific cleanups
    name = name.replace("Your Hot Commander", "")
    name = name.replace("Your Husband’s Affair", "")
    name = name.replace("Unhopeful Destiny", "")
    name = name.replace("7 Days 7 Personalities", "")
    name = name.replace("Isekai as the Villain", "")
    name = name.replace("The Control Devil", "")
    name = name.replace("Obsession", "")
    name = name.replace("Your Little Sister", "Little Sister")
    
    # Clean again
    name = re.sub(r'[\(\)\?]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    
    # If it ends up empty, fallback
    if not name:
        name = c.get("id", "Unknown")
        
    c["name"] = name
    print(f"Cleaned {c['id']} -> {name}")

with open("characters.json", "w") as f:
    json.dump(chars, f, indent=2)

