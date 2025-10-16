#!/bin/zsh
# ============================================================
# build_macos.command
# macOS用: CreditGet_release.py を PyInstaller でビルド
# ダブルクリックで完了する自動化スクリプト
#CreditGet_release.py と 同じフォルダに
# build_macos.command を保存します。
#
#ターミナルで実行権限を付与します：
#
#chmod +x build_macos.command
#
#Finderから build_macos.command を ダブルクリック すると：
#
#PyInstaller が自動インストール（初回のみ）
#
#dist/CreditGet_release が生成
#
#すぐに実行可能な macOS バイナリが完成します 🎉
# ============================================================

echo "🍎 macOS ビルドスクリプトを開始します..."
cd "$(dirname "$0")"

# Python3 確認
if ! command -v python3 &>/dev/null; then
  echo "❌ Python3 が見つかりません。https://www.python.org/downloads/mac-osx/ からインストールしてください。"
  exit 1
fi

# PyInstaller がなければインストール
if ! python3 -m pip show pyinstaller &>/dev/null; then
  echo "⚙️ PyInstaller をインストール中..."
  python3 -m pip install pyinstaller
fi

# dist フォルダをクリア
if [ -d "dist" ]; then
  echo "🧹 既存の dist フォルダを削除します..."
  rm -rf dist
fi

# ビルド対象ファイル確認
if [ ! -f "CreditGet_release.py" ]; then
  echo "❌ CreditGet_release.py が見つかりません。このスクリプトと同じフォルダに置いてください。"
  exit 1
fi

# ビルド開始
echo "🏗️ ビルドを開始します..."
python3 -m PyInstaller --onefile --windowed CreditGet_release.py

# ビルド結果確認
if [ -f "dist/CreditGet_release" ]; then
  echo "✅ ビルド完了: dist/CreditGet_release"
  chmod +x dist/CreditGet_release
else
  echo "❌ ビルドに失敗しました。エラーログを確認してください。"
  exit 1
fi

# 実行権限と起動確認
echo "🚀 実行権限を付与しました。"
echo ""
echo "👉 以下のコマンドで起動できます："
echo "   ./dist/CreditGet_release"
echo ""
echo "または Finder で dist フォルダを開いてダブルクリックでも実行可能です。"
echo ""
echo "✅ 処理が完了しました！"
