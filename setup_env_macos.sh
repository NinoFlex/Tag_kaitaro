#!/bin/bash
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "仮想環境作成完了。run_macos_venv.command をダブルクリックして起動してください。"
