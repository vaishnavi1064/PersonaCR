import os
import re

directories_to_scan = [
    r'd:\agentic_project\frontend\src\components',
    r'd:\agentic_project\frontend\src\pages'
]

# Regex to match fontSize: <number>
# e.g., fontSize: 12  -> fontSize: 13
# We only want to match literal numbers, not strings or vars
font_regex = re.compile(r'(fontSize:\s*)(\d+)')

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Special handling for Sidebar.tsx logo sizing per requirements (+3 instead of +1)
    if 'Sidebar.tsx' in filepath:
        # The logo text is currently 14px. We need to find the specific one.
        # "PersonaCR" is wrapped in a span with "fontSize: 14"
        content = re.sub(
            r"(fontSize:\s*)(14)(,\s*color:\s*'var\(--text-primary\)',\s*letterSpacing:\s*'-0.1px')",
            r"\g<1>17\g<3>",
            content
        )
        # The DiamondIcon svg needs bumping from 20 -> 24
        #   <svg width="20" height="20"
        content = re.sub(
            r'<svg width="20" height="20"',
            r'<svg width="24" height="24"',
            content
        )
        
    def replacer(match):
        prefix = match.group(1)
        value = int(match.group(2))
        # If it's a very large number, it might be something else, but max font is usually < 100
        if value < 100:
            return f"{prefix}{value + 1}"
        return match.group(0)

    new_content = font_regex.sub(replacer, content)

    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {filepath}")

for d in directories_to_scan:
    for root, _, files in os.walk(d):
        for file in files:
            if file.endswith('.tsx') or file.endswith('.ts'):
                process_file(os.path.join(root, file))

print("Done.")
