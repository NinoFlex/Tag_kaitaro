#!/bin/bash
# ターミナルが開いて実行されます。スクリプトと同じフォルダに置いてください.
cd "$(dirname "$0")"

# python3 を使って起動
if command -v python3 >/dev/null 2>&1; then
  python3 CreditGet_relese.py
else
  echo "python3 が見つかりません。Homebrewや公式から Python をインストールしてください。"
fi

read -n 1 -s -r -p "終了するには Enter を押してください..."
echo
