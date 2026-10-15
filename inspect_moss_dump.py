import re
import json

with open(r'c:\Users\donpv\OneDrive\Desktop\meg\dump\dump.cs', 'r', encoding='utf-8') as f:
    text = f.read()

print("=== 1. SEARCH FOR ALL JCNCJFIENNM (PACKET HANDLERS) NEAR MOSS ===")
lines = text.split('\n')
for i, line in enumerate(lines):
    if '[JCNCJFIENNM(' in line:
        # Check next 3 lines
        context = '\n'.join(lines[i:i+4])
        for j in range(max(0, i-50), min(len(lines), i+10)):
            if 'MossMerchant' in lines[j]:
                print(f"Line {i+1}:\n{context}")
                break

print("\n=== 2. MOSS PACKET DEFINITIONS ===")
for i, line in enumerate(lines):
    if 'MossMerchant' in line and ('class' in line or 'struct' in line):
        print(f"Line {i+1}: {line}")

print("\n=== 3. METHODS OF MossMerchantWindow ===")
start = -1
for i, line in enumerate(lines):
    if 'public class MossMerchantWindow : GameBehaviour' in line:
        start = i
        break

if start != -1:
    for k in range(start, start + 80):
        print(f"{k+1}: {lines[k]}")

print("\n=== 4. MMossMerchantWindow ALL FIELDS & METHODS ===")
start_m = -1
for i, line in enumerate(lines):
    if 'public class MMossMerchantWindow : MossMerchantWindow' in line:
        start_m = i
        break

if start_m != -1:
    for k in range(start_m, start_m + 160):
        print(f"{k+1}: {lines[k]}")
