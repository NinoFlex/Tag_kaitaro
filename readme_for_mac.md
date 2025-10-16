以下は、あなたの `CreditGet_modified.py` を **macOS 上で安全に実行するための完全な手順書** です。
（添付の `setup_env_macos.sh`, `run_macos_venv.command`, `run_macos.command` をすべて使用します。）

---

## 🧭 手順書：macOS上で `CreditGet_modified.py` を実行する方法

### ① フォルダ構成の準備

1. 任意の場所にフォルダを作成します（例：`~/MusicTagTool`）。
2. 以下のファイルをすべて同じフォルダに配置してください：

   ```
   CreditGet_modified.py
   setup_env_macos.sh
   run_macos.command
   run_macos_venv.command
   requirements.txt（存在する場合）
   ```

   💡 `requirements.txt` がない場合は、後述のステップで自動生成します。

---

### ② 実行権限を付与する

macOS のセキュリティ対策により、`.sh` や `.command` ファイルは実行権限が必要です。

1. ターミナルを開く（Spotlight で「Terminal」と入力）。
2. フォルダに移動します：

   ```bash
   cd ~/MusicTagTool
   ```
3. 実行権限を付与：

   ```bash
   chmod +x setup_env_macos.sh run_macos.command run_macos_venv.command
   ```

---

### ③ 仮想環境のセットアップ

`setup_env_macos.sh` は Python 仮想環境を自動で作成し、必要なライブラリをインストールします。

1. ターミナルで以下を実行：

   ```bash
   ./setup_env_macos.sh
   ```
2. 出力例：

   ```
   仮想環境作成完了。run_macos_venv.command をダブルクリックして起動してください。
   ```

   となれば成功です。

> 💡 `requirements.txt` がない場合は、自動で `pip install mutagen requests` などを行ってください。

---

### ④ 実行する

作業完了後は、次のいずれかの方法でプログラムを実行できます。

#### ✅ 方法1：ダブルクリック実行（推奨）

* Finder で `run_macos_venv.command` を **ダブルクリック**
  → ターミナルが開き、自動的に仮想環境が有効化されて
  `CreditGet_modified.py` が実行されます。

#### ✅ 方法2：手動で実行

* ターミナルで以下を入力：

  ```bash
  source .venv/bin/activate
  python CreditGet_modified.py
  ```

---

### ⑤ 動作確認

* 実行すると、対象フォルダ内の音楽ファイル（`.flac`, `.m4a`, `.mp3` など）を解析し、
  Uta-Net などからタグ情報を自動付与します。
* 進行ログがターミナルに出力されます。
* 終了後、同じディレクトリのファイルが更新されていれば成功です。

---

### ⑥ トラブルシューティング

| 問題                        | 対応                                                  |
| ------------------------- | --------------------------------------------------- |
| 「command not found」       | `chmod +x` を忘れていないか確認                               |
| 「Permission denied」       | ターミナルに `sudo chmod +x *.command` と入力                |
| 「No module named mutagen」 | 仮想環境を再構築：<br>`rm -rf .venv && ./setup_env_macos.sh` |
| Python のバージョンが古い          | macOS の Python3.9 以上を推奨                             |

---

### ⑦ アンインストールしたい場合

仮想環境を削除するだけでOKです：

```bash
rm -rf .venv
```

---

## 🧩 実行イメージ

```
~/MusicTagTool/
├── CreditGet_modified.py
├── setup_env_macos.sh
├── run_macos.command
├── run_macos_venv.command
├── requirements.txt
└── .venv/           ← 自動生成（Python仮想環境）
```

---

この手順に従えば、macOS 上で GUI クリックのみで `CreditGet_modified.py` が安全・安定的に動作します。
必要であれば、`requirements.txt` の推奨内容（mutagen, requestsなど）も出力できます。希望しますか？
