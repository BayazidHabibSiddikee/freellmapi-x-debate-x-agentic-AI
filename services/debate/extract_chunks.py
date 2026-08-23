import struct
import json
import base64
import os
from PIL import Image

def extract_png_text(filepath):
    """Extract text chunk from PNG file."""
    with open(filepath, 'rb') as f:
        # Check PNG signature
        if f.read(8) != b'\x89PNG\r\n\x1a\n':
            return None

        while True:
            length_bytes = f.read(4)
            if len(length_bytes) != 4:
                break
            length = struct.unpack('>I', length_bytes)[0]
            chunk_type = f.read(4)
            chunk_data = f.read(length)
            f.read(4)  # CRC

            if chunk_type in (b'tEXt', b'iTXt'):
                try:
                    if chunk_type == b'tEXt':
                        parts = chunk_data.split(b'\x00', 1)
                        if len(parts) == 2:
                            keyword, text = parts
                            return (keyword.decode('latin-1'), text.decode('latin-1'))
                    elif chunk_type == b'iTXt':
                        # iTXt format: keyword\n\0compression\0language\0translation\0text
                        parts = chunk_data.split(b'\x00', 4)
                        if len(parts) >= 5:
                            keyword = parts[0].decode('latin-1')
                            text = parts[4].decode('utf-8')
                            return (keyword, text)
                except Exception:
                    pass
    return None

def create_placeholder_image(path, name):
    """Create a placeholder PNG for characters without images."""
    img = Image.new('RGB', (200, 200), color='#1f2937')
    # You can add text or other elements here
    img.save(path)
    return path

def sync_characters():
    cards = []
    if os.path.exists("characters.json"):
        try:
            with open("characters.json", "r") as f:
                cards = json.load(f)
        except Exception:
            pass
            
    existing_ids = {c["id"] for c in cards}
    
    images_dir = "images"
    os.makedirs(images_dir, exist_ok=True)

    # Process all PNG files
    for file in sorted(os.listdir(images_dir)):
        if file.lower().endswith(".png"):
            path = os.path.join(images_dir, file)
            res = extract_png_text(path)
            character_added = False

            if res:
                keyword, data = res
                if keyword == 'chara':
                    try:
                        decoded = base64.b64decode(data).decode('utf-8')
                        chara_json = json.loads(decoded)
                        name = chara_json.get('name', file.replace('.png', ''))
                        sys_prompt = chara_json.get('system_prompt', 
                           chara_json.get('description', 
                           chara_json.get('personality', 
                           f"Character from {file}")))

                        char_id = name.replace(' ', '_').replace('.', '_')
                        if char_id not in existing_ids:
                            cards.append({
                                "id": char_id,
                                "name": name,
                                "image": path,
                                "system_prompt": sys_prompt
                            })
                            existing_ids.add(char_id)
                            print(f"✅ Extracted: {name}")
                        else:
                            print(f"⏩ Skipped (already exists): {name}")
                        character_added = True
                    except Exception as e:
                        print(f"⚠️ Error parsing chara in {file}: {e}")

            if not character_added:
                # Add as fallback character
                name = file.replace('.png', '').replace('_', ' ')
                char_id = file.replace('.png', '').replace(' ', '_')
                if char_id not in existing_ids:
                    cards.append({
                        "id": char_id,
                        "name": name,
                        "image": path,
                        "system_prompt": f"Character from {file}. Persona metadata not found."
                    })
                    existing_ids.add(char_id)
                    print(f"ℹ️ Added fallback: {name}")

    # Ensure Marin exists (create placeholder if needed)
    marin_path = os.path.join(images_dir, "default_marin.png")
    if not any(c['name'] == 'Marin' for c in cards):
        if not os.path.exists(marin_path):
            create_placeholder_image(marin_path, "Marin")
            print(f"ℹ️ Created placeholder: {marin_path}")
        cards.append({
            "id": "Marin",
            "name": "Marin",
            "image": marin_path,
            "system_prompt": "You are Marin, an AI designed with dry humor and technical prowess."
        })
        print(f"✅ Added: Marin")

    # Save characters.json
    with open("characters.json", "w") as f:
        json.dump(cards, f, indent=2)
    print(f"\n🎉 Total characters: {len(cards)}")
    print(f"📄 Saved to: characters.json")
    return cards

if __name__ == '__main__':
    sync_characters()
