import sys
import os
from pathlib import Path

print(f"Python: {sys.executable}")
print(f"CWD: {os.getcwd()}")
print(f"main.py path: {Path('src/main.py').resolve()}")

with open('src/main.py', 'r') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if 'sqlite3.connect' in line:
            print(f"Line {i+1}: {line.strip()}")
