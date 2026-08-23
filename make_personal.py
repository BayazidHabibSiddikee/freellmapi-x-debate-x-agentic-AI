import re

with open('templates/personal.html', 'r') as f:
    content = f.read()

# Change Title
content = content.replace("<title>AI Character Debate Simulator</title>", "<title>Personal AI Chat</title>")
content = content.replace("<h1>Sword Debate</h1>", "<h1>Personal Chat</h1>")
content = content.replace("Debate Topic", "Chat Topic")

# Remove Chat Mode section
content = re.sub(r'<div class="control-group">\s*<label><i class="ri-settings-2-line"></i> Chat Mode</label>.*?</div>', '', content, flags=re.DOTALL)

# Change checkboxes to radios for character selection
content = content.replace('type="checkbox"', 'type="radio" name="selected_character"')

# Remove Auto-Play Toggle
content = re.sub(r'<div class="toggle-container">\s*<div class="toggle-label">\s*<i class="ri-robot-line".*?</div>', '', content, flags=re.DOTALL)

# Change (Select >=2) to (Select 1)
content = content.replace("Participants (Select ≥2)", "Partner (Select 1)")

# Remove next char / auto play logic from js
# e.g., if (isAutoPlaying) ...
content = re.sub(r'if \(isAutoPlaying\).*?}', '', content, flags=re.DOTALL)
content = re.sub(r'function toggleAutoPlay\(\) \{.*?\}', '', content, flags=re.DOTALL)
content = re.sub(r'let isAutoPlaying = false;', '', content)
content = re.sub(r'let autoPlayInterval = null;', '', content)
content = re.sub(r'let burstQueue = 0;', '', content)

# Change mode variable to fixed value
content = content.replace("const mode = document.getElementById('chatMode').value;", "const mode = 'round_robin';")
content = content.replace("localStorage.setItem('debateMode', document.getElementById('chatMode').value);", "")
content = content.replace("const savedMode = localStorage.getItem('debateMode');", "")
content = content.replace("if (savedMode) document.getElementById('chatMode').value = savedMode;", "")

with open('templates/personal.html', 'w') as f:
    f.write(content)
