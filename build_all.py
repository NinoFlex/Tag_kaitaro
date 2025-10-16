import os
import platform
import subprocess

script = "CreditGet_modified.py"

if platform.system() == "Windows":
    print("🪟 Windows向けビルドを開始...")
    subprocess.run(["pyinstaller", "--onefile", "--noconsole", script])
    print("✅ dist/CreditGet_modified.exe を生成しました。")
elif platform.system() == "Darwin":
    print("🍎 macOS向けビルドを開始...")
    subprocess.run(["pyinstaller", "--onefile", "--windowed", script])
    print("✅ dist/CreditGet_modified を生成しました。")
else:
    print("このOSでは自動ビルドに対応していません。")