import re

with open('templates/personal.html', 'r') as f:
    text = f.read()

# Fix minimum characters check
text = text.replace('characters.length < 2', 'characters.length < 1')
text = text.replace('Please select at least 2 characters', 'Please select 1 character')

# Fix toggleAutoPlay artifacts
text = re.sub(r'document\.getElementById\(\'autoPlayToggle\'\)\.checked = false;\s*toggleAutoPlay\(\);', '', text)

# Fix syntax error block in generateTurn
text = re.sub(r'if \(burstQueue > 0\).*?} else , 2000\);\s*}', '', text, flags=re.DOTALL)

# Fix sendUserMessage burstQueue
text = re.sub(r'const mode = \'round_robin\';\s*if \(mode === \'random\'\) \{.*?\} else \{\s*generateTurn\(\);\s*\}', 'generateTurn();', text, flags=re.DOTALL)

with open('templates/personal.html', 'w') as f:
    f.write(text)
