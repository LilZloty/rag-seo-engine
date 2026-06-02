"""
UI Cleanup Script: Remove emojis and rounded corners from frontend files.
Makes the UI more professional with rectangular elements.
Preserves file formatting carefully.
"""
import os
import re

# Frontend app directory
script_dir = os.path.dirname(os.path.abspath(__file__))
frontend_app_dir = os.path.join(script_dir, '..', 'frontend', 'app')

# Files to process
files_to_process = [
    os.path.join(frontend_app_dir, 'page.tsx'),
    os.path.join(frontend_app_dir, 'generate', '[id]', 'page.tsx'),
    os.path.join(frontend_app_dir, 'libraries', 'page.tsx'),
]

# Emoji patterns to remove
emojis_to_remove = [
    '🔄', '✨', '🆕', '📊', '💾', '📚', '📝', '💬', '🤖', '🧠',
    '✅', '⚠', '⚠️', '🔍', '⏳', '📷', '🚗', '⏰', '🔥', '📦',
    '💭', '👤', '💰', '🏷️', '🛒', '📈', '⚡', '🎯', '💡', '🔗',
    '📁', '🗂️', '📋', '🔧', '⚙️', '🎨', '�️', '🏪', '🌐', '📱',
    '✓', '✕', '⇐', '⇒'
]

# Rounded class patterns to remove
rounded_patterns = [
    'rounded-2xl',
    'rounded-xl', 
    'rounded-lg',
    'rounded-full',
    'rounded-md',
    'rounded-sm',
]

def clean_file(filepath):
    if not os.path.exists(filepath):
        print(f"  Skipping (not found): {os.path.basename(filepath)}")
        return 0
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    changes = 0
    
    # Remove emojis
    for emoji in emojis_to_remove:
        if emoji in content:
            count = content.count(emoji)
            content = content.replace(emoji, '')
            changes += count
    
    # Remove standalone "rounded" word as a CSS class
    # Match rounded that's not part of another word
    count = len(re.findall(r'(?<![a-zA-Z-])rounded(?![a-zA-Z-])', content))
    content = re.sub(r'(?<![a-zA-Z-])rounded(?![a-zA-Z-])', '', content)
    changes += count
    
    # Remove rounded-* patterns
    for pattern in rounded_patterns:
        if pattern in content:
            count = content.count(pattern)
            content = content.replace(pattern, '')
            changes += count
    
    # Clean up double spaces in className strings but preserve line structure
    # Only clean within quotes to avoid breaking code
    def clean_classname(match):
        cls = match.group(1)
        # Replace multiple spaces with single space
        cls = re.sub(r' +', ' ', cls)
        # Strip leading/trailing spaces
        cls = cls.strip()
        return f'className="{cls}"'
    
    content = re.sub(r'className="([^"]*)"', clean_classname, content)
    
    # Also handle template literals className={`...`}
    def clean_template_classname(match):
        cls = match.group(1)
        cls = re.sub(r' +', ' ', cls)
        cls = cls.strip()
        return f'className={{`{cls}`}}'
    
    content = re.sub(r'className=\{`([^`]*)`\}', clean_template_classname, content)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  Cleaned: {os.path.basename(filepath)} ({changes} replacements)")
        return changes
    else:
        print(f"  No changes: {os.path.basename(filepath)}")
        return 0

def main():
    print("=" * 50)
    print("UI Cleanup: Removing emojis and rounded corners")
    print("=" * 50)
    
    total_changes = 0
    for filepath in files_to_process:
        total_changes += clean_file(filepath)
    
    print()
    print(f"Total replacements: {total_changes}")
    print("Done! Refresh your frontend to see the changes.")

if __name__ == "__main__":
    main()
