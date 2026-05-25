# pylint: disable=all
# ─────────────────────────────────────────
#  ShowMe — setup.py
#  Run this once after cloning.
#  Checks dependencies, creates folders,
#  reminds you to download the Vosk model.
# ─────────────────────────────────────────

import os
import sys
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))

print("\n ShowMe — Setup\n" + "─" * 40)

# 1. Install requirements
print("\n[1/3] Installing Python packages...")
subprocess.check_call([sys.executable, "-m", "pip", "install", "-r",
                       os.path.join(BASE, "requirements.txt")])

# 2. Create folders
print("\n[2/3] Creating folders...")
for folder in ["model", "assets", "apps"]:
    path = os.path.join(BASE, folder)
    os.makedirs(path, exist_ok=True)
    print(f"      ✓ {folder}/")

# 3. Check for Vosk model
print("\n[3/3] Checking Vosk model...")
model_dir = os.path.join(BASE, "model")
models = [d for d in os.listdir(model_dir)
          if os.path.isdir(os.path.join(model_dir, d)) and "vosk" in d.lower()]

if models:
    print(f"      ✓ Model found: {models[0]}")
else:
    print("""
      ✗ No Vosk model found in model/ folder.

      Download it here:
      https://alphacephei.com/vosk/models

      Get: vosk-model-small-en-us-0.15  (~40MB)
      Unzip into:  showme/model/

      Then run:  python main.py
    """)
    sys.exit(1)

print("\n" + "─" * 40)
print(" Setup complete. Run:  python main.py")
print("─" * 40 + "\n")
