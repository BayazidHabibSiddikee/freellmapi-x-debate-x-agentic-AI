import json

with open("characters.json", "r") as f:
    chars = json.load(f)

for c in chars:
    name = c.get("name", "")
    if "Maya" in name:
        name = "Maya"
    if "Sebastian" in name:
        name = "Sebastian"
    c["name"] = name
    print(name)

with open("characters.json", "w") as f:
    json.dump(chars, f, indent=2)

