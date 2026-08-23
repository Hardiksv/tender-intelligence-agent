import os
import re
import emoji

def remove_comments_and_emojis_python(content):
    # Remove emojis
    content = emoji.replace_emoji(content, replace='')
    
    # Remove single line comments (but not inside strings, though this simple regex might catch some edge cases, 
    # it's usually fine for standard code. Better to just remove lines that start with #)
    lines = content.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#'):
            continue
        
        # Remove trailing comments
        # A simple split by ' #' might work, but let's be careful about URLs.
        if ' #' in line:
            line = line.split(' #')[0].rstrip()
            
        cleaned_lines.append(line)
        
    return '\n'.join(cleaned_lines)

def remove_comments_and_emojis_js(content):
    # Remove emojis
    content = emoji.replace_emoji(content, replace='')
    
    # Remove single line comments //
    lines = content.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
            
        # Remove trailing comments
        if ' //' in line and not '://' in line:
            line = line.split(' //')[0].rstrip()
            
        cleaned_lines.append(line)
        
    return '\n'.join(cleaned_lines)


for root, dirs, files in os.walk('backend'):
    if 'venv' in root or '__pycache__' in root or '.git' in root:
        continue
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            cleaned = remove_comments_and_emojis_python(content)
            if cleaned != content:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(cleaned)

for root, dirs, files in os.walk('frontend/src'):
    if 'node_modules' in root or '.git' in root:
        continue
    for file in files:
        if file.endswith(('.js', '.jsx', '.ts', '.tsx')):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            cleaned = remove_comments_and_emojis_js(content)
            
            # also strip {/* */} jsx comments if possible
            cleaned = re.sub(r'\{\/\*.*?\*\/\}\n?', '', cleaned, flags=re.DOTALL)
            
            if cleaned != content:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(cleaned)

print("Cleanup complete.")
