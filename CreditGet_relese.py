import os
import tkinter as tk
from tkinter import filedialog, ttk, scrolledtext
from mutagen import File as MutagenFile
import threading, traceback

# --- get_credit.py 相当 ---
import re, html, requests
from mutagen.id3 import ID3, ID3NoHeaderError, TXXX, TCOM, COMM
from mutagen.flac import FLAC
from mutagen.mp4 import MP4, MP4Tags, MP4FreeForm

# FLAC 用の一時保持キャッシュ
flac_pending = {}

USER_AGENT = "PythonTagEnricher/1.0"
HEADERS = {"User-Agent": USER_AGENT}
SEARCH_URL = "https://www.uta-net.com/search/?Aselect=2&Keyword={}"
SONG_PAGE_URL = "https://www.uta-net.com/song/{}/"


class Tooltip:
    """簡易ツールチップ。ウィジェットに bind して使う。"""
    PAD_X = 8
    PAD_Y = 6

    def __init__(self, widget, table_rows, description_lines, delay=300):
        self.widget = widget
        self.table_rows = table_rows
        self.description_lines = description_lines
        self.delay = delay
        self.tipwindow = None
        self.id = None
        widget.bind("<Enter>", self.schedule)
        widget.bind("<Leave>", self.hide)
        widget.bind("<Motion>", self.move)

    def schedule(self, event=None):
        self.unschedule()
        self.id = self.widget.after(self.delay, lambda: self.show(event))

    def unschedule(self):
        if self.id:
            try:
                self.widget.after_cancel(self.id)
            except Exception:
                pass
            self.id = None

    def show(self, event=None):
        if self.tipwindow:
            return
        x = y = 0
        x = self.widget.winfo_rootx() + self.PAD_X
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + self.PAD_Y

        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.attributes("-topmost", True)
        tw.geometry(f"+{x}+{y}")

        frame = tk.Frame(tw, bg="#ffffe0", bd=1, relief="solid")
        frame.pack()

        # 表ヘッダ
        header_bg = "#f0f0f0"
        for c, h in enumerate(self.table_rows[0]):
            lbl = tk.Label(frame, text=h, bg=header_bg, font=("TkDefaultFont", 9, "bold"), borderwidth=1, relief="groove", padx=6, pady=3)
            lbl.grid(row=0, column=c, sticky="nsew")

        # 表データ
        for r, row in enumerate(self.table_rows[1:], start=1):
            for c, cell in enumerate(row):
                lbl = tk.Label(frame, text=cell, bg="#ffffff", borderwidth=1, relief="groove", padx=6, pady=3)
                lbl.grid(row=r, column=c, sticky="nsew")

        # 少し余白を入れて説明文
        desc_frame = tk.Frame(tw, bg="#ffffe0", padx=8, pady=6)
        desc_frame.pack(fill="both")
        for line in self.description_lines:
            lbl = tk.Label(desc_frame, text=line, anchor="w", justify="left", bg="#ffffe0")
            lbl.pack(anchor="w")

    def move(self, event):
        # マウス移動で表示中なら追従（オプション）
        if self.tipwindow:
            x = self.widget.winfo_rootx() + self.PAD_X
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + self.PAD_Y
            try:
                self.tipwindow.geometry(f"+{x}+{y}")
            except Exception:
                pass

    def hide(self, event=None):
        self.unschedule()
        if self.tipwindow:
            try:
                self.tipwindow.destroy()
            except Exception:
                pass
            self.tipwindow = None

def build_integrated_composer(ext, info):
    composer = info.get("composer", "").strip()
    if ext == ".m4a":
        remixer = info.get("arranger", "").strip()
        if remixer == composer:
            return composer
        elif remixer:
            return f"{composer} / {remixer}"
        return composer
    elif ext == ".flac":
        lyricist = info.get("lyricist", "").strip()
        if lyricist == composer:
            return composer
        elif lyricist:
            return f"{lyricist} / {composer}"
        return composer
    return composer

def build_composer_tag(lyricist=None, composer=None, arranger=None):
    parts = []
    if lyricist:
        parts.append(f'作詞="{lyricist}"')
    if composer:
        parts.append(f'作曲="{composer}"')
    if arranger:
        parts.append(f'編曲="{arranger}"')
    return " ".join(parts)

def normalize(s):
    if not s:
        return ""
    # CV表記削除
    t = re.sub(r'\s*\(CV[:\s][^\)]+\)', '', s)
    # 全角スペースを半角に統一
    t = t.replace("　", " ")
    # スペースはすべて削除
    t = re.sub(r"\s+", "", t)
    # 小文字化
    return t.strip().lower()

def get_uta_net_song_id(title, artist):
    q = requests.utils.quote(title)
    search_url = SEARCH_URL.format(q)
    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return None, f"検索ページ取得エラー: {e}"

    html_text = resp.text
    pattern = re.compile(
        r'(?si)<tr[^>]*class="border-bottom"[^>]*>.*?'
        r'/song/(\d+)/".*?songlist-title[^>]*>([^<]+)</span>.*?'
        r'/artist/\d+/"[^>]*>([^<]+)</a>',
        re.DOTALL
    )
    matches = pattern.findall(html_text)
    if not matches:
        return None, "候補が見つかりませんでした。"

    candidates = [{"Id": int(m[0]), "Title": m[1].strip(), "Artist": m[2].strip()} for m in matches]
    ntitle = normalize(title)
    nartist = normalize(artist)
    pref = nartist[:3] if len(nartist) >= 3 else nartist

    # タイトル一致条件
    exact = [c for c in candidates if normalize(c["Title"]) == ntitle]
    front_match = [c for c in candidates if normalize(c["Title"]).startswith(ntitle)]
    partial = [c for c in candidates if ntitle in normalize(c["Title"])]

    # --- 修正ポイント ---
    # 「or」ではなく合体させることで全候補を対象にする
    stage1 = []
    stage1.extend(exact)
    stage1.extend(front_match)
    stage1.extend(partial)

    if not stage1:
        return None, "候補が見つかりませんでした。"

    # --- アーティスト名の先頭2文字が一致するもののみを選択 ---
    by_artist = [c for c in stage1 if normalize(c["Artist"]).startswith(pref)]
    if by_artist:
        return by_artist[0]["Id"], None

    # 一致しなければスキップ
    return None, f"アーティスト名の先頭2文字が一致する候補が見つかりませんでした。{matches}"


def get_song_page_info(song_id):
    url = SONG_PAGE_URL.format(song_id)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return None, f"曲ページ取得エラー: {e}"

    html_text = resp.text
    info = {"anime": "", "lyricist": "", "composer": "", "arranger": ""}

    # アニメ情報
    p_anime = re.search(r'(?s)<p[^>]*class="[^"]*ms-2\s+ms-md-3\s+mb-0[^"]*"[^>]*>(.*?)</p>', html_text)
    if p_anime:
        anime = re.sub(r'\s+', ' ', html.unescape(p_anime.group(1))).strip()
        info["anime"] = anime

    # 詳細情報 (作詞・作曲・編曲)
    p_detail = re.search(r'(?s)<p[^>]*class="[^"]*ms-2\s+ms-md-3\s+detail\s+mb-0[^"]*"[^>]*>(.*?)</p>', html_text)
    if p_detail:
        text = re.sub(r'<[^>]+>', ' ', p_detail.group(1))
        text = re.sub(r'\s+', ' ', html.unescape(text)).strip()

    # 作詞
    m = re.search(r'作詞：\s*(.+?)(?=\s*(作曲：|編曲：|発売日：|$))', text)
    if m:
        info["lyricist"] = m.group(1).strip()

    # 作曲
    m2 = re.search(r'作曲：\s*(.+?)(?=\s*(作詞：|編曲：|発売日：|$))', text)
    if m2:
        info["composer"] = m2.group(1).strip()

    # 編曲
    m3 = re.search(r'編曲：\s*(.+?)(?=\s*(作詞：|作曲：|発売日：|$))', text)
    if m3:
        info["arranger"] = m3.group(1).strip()

    msg = f"取得結果 → アニメ='{info['anime']}', 作詞='{info['lyricist']}', 作曲='{info['composer']}', 編曲='{info['arranger']}'"
    if not info["anime"]:
        msg = "タイアップ情報が見つかりませんでした。 " + msg
    return info, msg




def set_credit_tag(filepath, role, value, force_overwrite=False):
    """
    role: "作詞者" / "作曲者" / "コメント" / "リミキサー"
    value: 書き込みたい値
    force_overwrite: True の場合、既存値があっても強制的に上書きする
    """
    if not value:
        return f"[{os.path.basename(filepath)}] {role} の値なし → スキップ"

    ext = os.path.splitext(filepath)[1].lower()
    updated = False
    msg = ""

    try:
        if ext == ".mp3":
            try:
                id3 = ID3(filepath)
            except ID3NoHeaderError:
                id3 = ID3()
                msg += "ID3ヘッダなし → 新規作成; "

            if role == "作詞者":
                frames = id3.getall("TXXX:LYRICIST")
                existing = frames[0].text[0] if frames and frames[0].text else ""
                if force_overwrite or existing in ("", "0"):
                    id3.delall("TXXX:LYRICIST")
                    id3.add(TXXX(encoding=3, desc="LYRICIST", text=[value]))
                    updated = True
                    msg = f"作詞者 上書き (既存='{existing}') → '{value}'"
                else:
                    msg = f"作詞者 既存='{existing}' → スキップ"

            elif role == "作曲者":
                existing = id3.getall("TCOM")[0].text[0] if id3.getall("TCOM") and id3.getall("TCOM")[0].text else ""
                if force_overwrite or existing in ("", "0"):
                    id3.delall("TCOM")
                    id3.add(TCOM(encoding=3, text=[value]))
                    updated = True
                    msg = f"作曲者 上書き (既存='{existing}') → '{value}'"
                else:
                    msg = f"作曲者 既存='{existing}' → スキップ"

            elif role == "コメント":
                comms = [c for c in id3.getall("COMM") if c.lang == "eng" and c.desc == ""]
                if not comms:
                    id3.add(COMM(encoding=3, lang="eng", desc="", text=[value]))
                    updated = True
                    msg = f"コメント 新規書き込み → '{value}'"
                else:
                    existing = " ".join(str(t) for t in comms[0].text if t).strip()
                    if force_overwrite or existing in ("", "0"):
                        comms[0].encoding = 3
                        comms[0].text = [value]
                        updated = True
                        msg = f"コメント 上書き (既存='{existing}') → '{value}'"
                    else:
                        msg = f"コメント 既存='{existing}' → スキップ"

            elif role == "リミキサー":
                frames = id3.getall("TXXX:MIXARTIST")
                existing = frames[0].text[0] if frames and frames[0].text else ""
                if force_overwrite or existing in ("", "0"):
                    id3.delall("TXXX:MIXARTIST")
                    id3.add(TXXX(encoding=3, desc="MIXARTIST", text=[value]))
                    updated = True
                    msg = f"リミキサー 上書き (既存='{existing}') → '{value}'"
                else:
                    msg = f"リミキサー 既存='{existing}' → スキップ"

            id3.save(filepath, v2_version=3)

        elif ext == ".flac":
            flac = FLAC(filepath)

            if role == "作詞者":
                None
            elif role == "作曲者":
                existing = flac.get("COMPOSER", [""])[0] if "COMPOSER" in flac else ""
                if force_overwrite or not existing:
                    flac["COMPOSER"] = value
                    updated = True
                    msg = f"作曲者 書き込み → '{value}'"
                else:
                    msg = f"作曲者 既存='{existing}' → スキップ"

            elif role == "コメント":
                existing = flac.get("COMMENT", [""])[0] if "COMMENT" in flac else ""
                if force_overwrite or not existing:
                    flac["COMMENT"] = value
                    updated = True
                    msg = f"コメント 書き込み → '{value}'"
                else:
                    msg = f"コメント 既存='{existing}' → スキップ"

            elif role == "リミキサー":
                existing = flac.get("MIXARTIST", [""])[0] if "MIXARTIST" in flac else ""
                if force_overwrite or not existing:
                    flac["MIXARTIST"] = value
                    updated = True
                    msg = f"リミキサー 書き込み → '{value}'"
                else:
                    msg = f"リミキサー 既存='{existing}' → スキップ"

            flac.save()

        elif ext == ".m4a":
            mp4 = MP4(filepath)
            tags = mp4.tags or MP4Tags()

            if role == "作詞者":
                existing = tags.get("©lyr", [""])[0] if "©lyr" in tags else ""
                if force_overwrite or existing in ("", "0"):
                    tags["©lyr"] = [value]
                    updated = True
                    msg = f"作詞者 書き込み → '{value}'"
                else:
                    msg = f"作詞者 既存='{existing}' → スキップ"

            elif role == "作曲者":
                existing = tags.get("©wrt", [""])[0] if "©wrt" in tags else ""
                if force_overwrite or existing in ("", "0"):
                    tags["©wrt"] = [value]
                    updated = True
                    msg = f"作曲者 書き込み → '{value}'"
                else:
                    msg = f"作曲者 既存='{existing}' → スキップ"

            elif role == "コメント":
                existing = tags.get("©cmt", [""])[0] if "©cmt" in tags else ""
                if force_overwrite or existing in ("", "0"):
                    tags["©cmt"] = [value]
                    updated = True
                    msg = f"コメント 書き込み → '{value}'"
                else:
                    msg = f"コメント 既存='{existing}' → スキップ"

            elif role == "リミキサー":
                None

            mp4.tags = tags
            mp4.save()

        else:
            msg = f"未対応フォーマット '{ext}'"

    except Exception as e:
        msg = f"{role} 書き込み中エラー: {e}"

    return f"[{os.path.basename(filepath)}] {msg}"




# --- GUI 部分 ---
class AudioTagGUI:
    def show_credits(self):
        """クレジットウィンドウ（モーダル風）"""
        try:
            if hasattr(self, "_credits_win") and self._credits_win.winfo_exists():
                self._credits_win.lift()
                return
        except Exception:
            pass

        win = tk.Toplevel(self.root)
        self._credits_win = win
        win.title("About — あんたの音源、勝手にタグ書い太郎")
        win.transient(self.root)
        win.resizable(False, False)
        win.attributes("-topmost", True)

        # 親ウィンドウをブロックする簡易モーダル
        win.grab_set()

        # 外枠スタイル
        outer = tk.Frame(win, bg="#2b2b2b", bd=0)
        outer.pack(fill="both", expand=True)
        frame = tk.Frame(outer, padx=18, pady=14, bg="#2b2b2b")
        frame.pack()

        # タイトルエリア
        title_lbl = tk.Label(frame, text="あんたの音源、勝手にタグ書い太郎", font=("Helvetica", 16, "bold"), fg="#ffd966", bg="#2b2b2b")
        title_lbl.pack(anchor="center")
        subtitle = tk.Label(frame, text="— 人柱 Edition —", font=("Helvetica", 10, "italic"), fg="#ffd966", bg="#2b2b2b")
        subtitle.pack(anchor="center", pady=(0,10))

        # 左: ロゴ領域（仮） 右: 基本情報
        info_frame = tk.Frame(frame, bg="#2b2b2b")
        info_frame.pack(fill="x", pady=(0,10))

        left_info = tk.Frame(info_frame, bg="#2b2b2b")
        left_info.grid(row=0, column=1, sticky="w")

        lbl_version = tk.Label(left_info, text="Version 1.0.0", font=("Helvetica", 10, "bold"), fg="#ffffff", bg="#2b2b2b")
        lbl_version.pack(anchor="w")
        lbl_copy = tk.Label(left_info, text="Copyright © 2025 新野", fg="#d0d0d0", bg="#2b2b2b")
        lbl_copy.pack(anchor="w")
        lbl_author = tk.Label(left_info, text="Developer: 新野", fg="#d0d0d0", bg="#2b2b2b")
        lbl_author.pack(anchor="w")

        # 区切り
        sep = tk.Frame(frame, height=2, bg="#444444")
        sep.pack(fill="x", pady=(6,10))

        # 主要貢献者（豪華カード風）
        contrib_frame = tk.Frame(frame, bg="#2b2b2b")
        contrib_frame.pack(fill="x", pady=(0,8))
        ctitle = tk.Label(contrib_frame, text="開発", font=("Helvetica", 11, "bold"), fg="#ffd966", bg="#2b2b2b")
        ctitle.pack(anchor="w")
        contrib_text = "新野（UI設計）・新野（仕様定義）・新野（実装）・新野（デバッグ）"
        clbl = tk.Label(contrib_frame, text=contrib_text, fg="#e8e8e8", bg="#2b2b2b", wraplength=480, justify="left")
        clbl.pack(anchor="w", pady=(4,0))

        # 技術スタックとサードパーティをカード風で並べる
        stack_frame = tk.Frame(frame, bg="#2b2b2b")
        stack_frame.pack(fill="x", pady=(8,8))
        left = tk.Frame(stack_frame, bg="#2b2b2b")
        right = tk.Frame(stack_frame, bg="#2b2b2b")
        left.pack(side="left", anchor="n", padx=(0,20))
        right.pack(side="left", anchor="n")

        ltitle = tk.Label(left, text="使用技術", font=("Helvetica", 10, "bold"), fg="#ffd966", bg="#2b2b2b")
        ltitle.pack(anchor="w")
        litems = "Python 3.x\nMutagen（音声タグ操作）\nrequests（HTTP）\nTkinter（GUI）"
        ltxt = tk.Label(left, text=litems, fg="#e8e8e8", bg="#2b2b2b", justify="left")
        ltxt.pack(anchor="w", pady=(4,0))

        rtitle = tk.Label(right, text="サードパーティ資産", font=("Helvetica", 10, "bold"), fg="#ffd966", bg="#2b2b2b")
        rtitle.pack(anchor="w")
        ritems = "FontAwesome アイコン（CC BY 4.0）"
        rtxt = tk.Label(right, text=ritems, fg="#e8e8e8", bg="#2b2b2b", justify="left")
        rtxt.pack(anchor="w", pady=(4,0))

        # ライセンスボックス
        lic_frame = tk.Frame(frame, bg="#1b1b1b", bd=1, relief="solid")
        lic_frame.pack(fill="x", pady=(10,6))
        lic_title = tk.Label(lic_frame, text="License", font=("Helvetica", 10, "bold"), fg="#ffd966", bg="#1b1b1b")
        lic_title.pack(anchor="w", padx=8, pady=(6,0))
        lic_txt = tk.Label(lic_frame, text="This software is distributed under the MIT License.", fg="#dcdcdc", bg="#1b1b1b", wraplength=520, justify="left")
        lic_txt.pack(anchor="w", padx=8, pady=(4,8))

        # 配布とサポート欄（ユーモアを含む）
        support_frame = tk.Frame(frame, bg="#2b2b2b")
        support_frame.pack(fill="x", pady=(6,10))
        sup_title = tk.Label(support_frame, text="Distribution & Support", font=("Helvetica", 10, "bold"), fg="#ffd966", bg="#2b2b2b")
        sup_title.pack(anchor="w")
        sup_text = (
            "このソフトウェアは新野のお友達やお世話になった人に配布しています。\n"
            "バグや要望は新野に言いつけてください。気が向いたら更新します。"
        )
        sup_lbl = tk.Label(support_frame, text=sup_text, fg="#e8e8e8", bg="#2b2b2b", wraplength=520, justify="left")
        sup_lbl.pack(anchor="w", pady=(4,0))

        # ASCIIキャラクター（装飾）
        ascii_frame = tk.Frame(frame, bg="#2b2b2b")
        ascii_frame.pack(fill="x", pady=(8,2))
        ascii_text = "　　　 ∧ ∧＿\n　　／(*ﾟーﾟ) ／＼\n　／|￣∪∪￣|＼／\n　　|＿＿＿＿|／"
        ascii_lbl = tk.Label(ascii_frame, text=ascii_text, fg="#ffd966", bg="#2b2b2b", justify="left", font=("Courier", 10))
        ascii_lbl.pack(anchor="center")

        # アクションボタン群
        btns = tk.Frame(frame, bg="#2b2b2b")
        btns.pack(fill="x", pady=(10,0))

        def _close():
            try:
                win.grab_release()
            except Exception:
                pass
            win.destroy()

        btn_close = tk.Button(btns, text="閉じる", command=_close)
        btn_close.pack(side="right", padx=(6,0))

        # 任意: 寄付ボタン（外部リンクを開く場合は webbrowser.open を使う）
        # import webbrowser
        # def _donate():
        #     webbrowser.open("https://example.com/donate")
        # btn_donate = tk.Button(btns, text="Support / Donate", command=_donate)
        # btn_donate.pack(side="right")

        # フォーカスを閉じるボタンに移す
        btn_close.focus_set()



    def __init__(self, root):
        self.root = root
        self.root.title("あんたの音源、勝手にタグ書い太郎")
        self.file_list = []
        self.stop_flag = False  # 中断フラグ追加

        # フォルダパス表示バー
        frame_path = tk.Frame(root)
        frame_path.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(frame_path, text="フォルダ:").pack(side=tk.LEFT)
        self.entry_path = tk.Entry(frame_path, width=80)
        self.entry_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(frame_path, text="参照", command=self.select_folder).pack(side=tk.LEFT)

        # 実行 / 中断ボタン
        frame_top = tk.Frame(root)
        frame_top.pack(fill=tk.X, padx=5, pady=5)
        self.btn_run = tk.Button(frame_top, text="実行", command=self.start_process)
        self.btn_run.pack(side=tk.LEFT, padx=5)
        self.btn_stop = tk.Button(frame_top, text="中断", command=self.stop_process, state="disabled")
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        # クレジットボタン（frame_top に右寄せで配置）
        self.btn_credits = tk.Button(frame_top, text="クレジット", command=self.show_credits)
        self.btn_credits.pack(side=tk.RIGHT, padx=5)

        # 進捗ラベルを中断ボタンの右に配置
        self.progress_label = tk.Label(frame_top, text="", fg="blue")
        self.progress_label.pack(side=tk.LEFT, padx=10)

        self.write_mode = tk.StringVar(value="A")  # デフォルトはタイプA
        def update_mode_visibility():
            if self.write_mode.get() == "A":
                self.chk_integrate.pack(side=tk.LEFT, padx=(10,0))
            else:
                self.chk_integrate.pack_forget()

        self.frame_mode = tk.Frame(root)
        self.frame_mode.pack(fill=tk.X, padx=5, pady=2)
        info_btn_mode = tk.Label(self.frame_mode, text="❓", cursor="hand2")
        info_btn_mode.pack(side=tk.LEFT, padx=(6,0))


        tk.Label(self.frame_mode, text="書き込み形式:").pack(side=tk.LEFT)
        tk.Radiobutton(self.frame_mode, text="タイプA（個別形式）", variable=self.write_mode, value="A", command=update_mode_visibility).pack(side=tk.LEFT)
        tk.Radiobutton(self.frame_mode, text="タイプB（統合形式）", variable=self.write_mode, value="B", command=update_mode_visibility).pack(side=tk.LEFT)
        self.integrate_unwritable_tags = tk.BooleanVar(value=False)
        self.chk_integrate = tk.Checkbutton(self.frame_mode, text="ファイルの仕様上書き込めないタグを作曲者タグに統合する", variable=self.integrate_unwritable_tags)
        self.chk_integrate.pack(side=tk.LEFT, padx=(10,0))
        table = [
            ["ファイル形式ごとに書き込み可能なタグ", "コメント", "作詞者", "作曲者", "リミキサー"],
            [".m4aファイル(iTunesから買った音源など)", "◯", "◯", "◯", "✕"],
            [".mp3ファイル", "◯", "◯", "◯", "◯"],
            [".flacファイル", "◯", "✕", "◯", "◯"],
        ]

        description = [
            "recordboxでは、上記の表の通り、ファイル形式によって保存できるタグが異なります。これは技術的に仕方がないことなのです。",
            "タイプA(個別形式)では、Webから取得した情報をファイル形式ごとに書き込み可能なタグのみ書き込みます。",
            "タイプB(統合形式)では、上記に加え、「作曲者」タグに 「作詞=\"\" 作曲=\"\" 編曲=\"\" 」という形式で、Webから取得した情報を書き込みます。",
            "作曲者タグにクレジット情報を集約させたい場合はタイプBを選択してください。",
            "",
            "タイプAを選んで「ファイルの仕様上書き込めないタグを作曲者タグに統合する」を有効化すると、取得した、m4aのリミキサー/flacの作詞者が作曲者タグに書き込まれます。",
        ]

        Tooltip(info_btn_mode, table, description, delay=200)

        # 上書き設定用チェックボックス
        self.overwrite_flags = {
            "コメント": tk.BooleanVar(value=False),
            "作詞者": tk.BooleanVar(value=False),
            "作曲者": tk.BooleanVar(value=False),
            "リミキサー": tk.BooleanVar(value=False),
        }

        self.frame_overwrite = tk.Frame(root)
        self.frame_overwrite.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(self.frame_overwrite, text="上書きするタグ:").pack(side=tk.LEFT)

        for label, var in self.overwrite_flags.items():
            tk.Checkbutton(self.frame_overwrite, text=label, variable=var).pack(side=tk.LEFT)

        frame_mid = tk.Frame(root)
        frame_mid.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("タイトル", "アーティスト", "コメント", "作詞者", "作曲者", "リミキサー", "サイズ")
        self.tree = ttk.Treeview(frame_mid, columns=columns, show="headings")

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150, anchor=tk.W)

        # スクロールバー追加
        scrollbar = ttk.Scrollbar(frame_mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        frame_bottom = tk.Frame(root)
        frame_bottom.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log = scrolledtext.ScrolledText(frame_bottom, height=10, state="disabled")
        self.log.pack(fill=tk.BOTH, expand=True)

    def log_message(self, msg):
        self.log.config(state="normal")
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.config(state="disabled")

    def select_folder(self):
        folder = filedialog.askdirectory(mustexist=True)
        if not folder:
            return
        self.entry_path.delete(0, tk.END)
        self.entry_path.insert(0, folder)
        self.load_files(folder)

    def load_files(self, folder):
        def task():
            self.file_list = []
            self.tree.delete(*self.tree.get_children())
            exts = (".mp3", ".flac", ".m4a")

            all_files = [os.path.join(root, f)
                        for root, _, files in os.walk(folder)
                        for f in files if f.lower().endswith(exts)]
            total = len(all_files)

            for idx, filepath in enumerate(all_files, 1):
                self.file_list.append(filepath)
                tags = self.read_tags(filepath)

                # TreeView更新はUIスレッドで
                self.root.after(0, lambda tags=tags: self.tree.insert("", tk.END, values=tags))

                # 進捗ラベルをUIスレッドで更新
                if idx % 20 == 0 or idx == total:
                    self.root.after(0, lambda i=idx: self.progress_label.config(
                        text=f"{i}/{total} 件 読み込み完了"))

            self.root.after(0, lambda: self.progress_label.config(
                text=f"{total} 件のファイルを読み込みました"))

        threading.Thread(target=task, daemon=True).start()

    def read_tags(self, filepath):
        try:
            ext = os.path.splitext(filepath)[1].lower()
            audio = MutagenFile(filepath, easy=True)
            title, artist, comment, lyricist, composer, remixer = "", "", "", "", "", ""

            if not audio:
                return [os.path.basename(filepath), "", "", "", "", ""]

            if ext == ".mp3":
                id3 = ID3(filepath)
                title = audio.get("title", [""])[0]
                artist = audio.get("artist", [""])[0]
                comment = ""
                comms = [c for c in id3.getall("COMM") if c.lang == "eng" and c.desc == ""]
                if comms and comms[0].text:
                    comment = " ".join(str(t) for t in comms[0].text if t).strip()
                lyricist = ""
                frames = id3.getall("TXXX:LYRICIST")
                if frames and frames[0].text:
                    lyricist = frames[0].text[0]
                composer = id3.getall("TCOM")[0].text[0] if id3.getall("TCOM") else ""
                frames = id3.getall("TXXX:MIXARTIST")
                if frames and frames[0].text:
                    remixer = frames[0].text[0]
            elif ext == ".flac":
                flac = FLAC(filepath)
                title = flac.get("TITLE", [""])[0]
                artist = flac.get("ARTIST", [""])[0]
                comment = flac.get("COMMENT", [""])[0] if "COMMENT" in flac else ""
                lyricist = flac.get("LYRICIST", [""])[0] if "LYRICIST" in flac else ""
                composer = flac.get("COMPOSER", [""])[0] if "COMPOSER" in flac else ""
                remixer = flac.get("MIXARTIST", [""])[0] if "MIXARTIST" in flac else ""
            elif ext == ".m4a":
                mp4 = MP4(filepath)
                title = mp4.tags.get("©nam", [""])[0] if "©nam" in mp4.tags else ""
                artist = mp4.tags.get("©ART", [""])[0] if "©ART" in mp4.tags else ""
                comment = mp4.tags.get("©cmt", [""])[0] if "©cmt" in mp4.tags else ""

                # 作詞者は ©lyr
                lyricist = mp4.tags.get("©lyr", [""])[0] if "©lyr" in mp4.tags else ""

                # 作曲者は ©wrt
                composer = mp4.tags.get("©wrt", [""])[0] if "©wrt" in mp4.tags else ""

                remixer = ""  # m4a 非対応

            size = f"{os.path.getsize(filepath)/1024:.1f} KB"
            self.log_message(f"title: {title} artist:{artist} comment:{comment} lyricist:{lyricist} composer:{composer} size:{size}")
            return [title, artist, comment, lyricist, composer, remixer, size]

        except Exception:
            self.log_message(f"タグ読み取りエラー: {filepath} → {traceback.format_exc()}")
            return [os.path.basename(filepath), "", "", "", "", ""]

    def stop_process(self):
        """中断ボタン押下時にフラグをセット"""
        self.stop_flag = True
        self.log_message("処理中断要求を受け付けました。")

    def start_process(self):
        folder = self.entry_path.get().strip()
        if not folder or not os.path.isdir(folder):
            self.log_message("有効なフォルダを指定してください。")
            return
        self.stop_flag = False
        # 操作不可にする
        self.btn_run.config(state="disabled")
        self.btn_stop.config(state="normal")
        # ラジオ・チェックを無効化
        for w in self.frame_mode.winfo_children():
            try:
                w.config(state="disabled")
            except Exception:
                pass
        for w in self.frame_overwrite.winfo_children():
            try:
                w.config(state="disabled")
            except Exception:
                pass

        threading.Thread(target=self.run_action, daemon=True).start()


    def run_action(self):
        self.log_message("Web情報を取得してタグを書き込みます...")
        for i, filepath in enumerate(self.file_list):
            if self.stop_flag:
                self.log_message("処理を中断しました。")
                break
            try:
                ext = os.path.splitext(filepath)[1].lower()
                title, artist = "", ""
                if ext == ".mp3":
                    audio = ID3(filepath)
                    title = audio.get("TIT2").text[0] if audio.get("TIT2") else ""
                    artist = audio.get("TPE1").text[0] if audio.get("TPE1") else ""
                elif ext == ".flac":
                    audio = FLAC(filepath)
                    title = audio.get("TITLE", [""])[0]
                    artist = audio.get("ARTIST", [""])[0]
                elif ext == ".m4a":
                    audio = MP4(filepath)
                    title = audio.tags.get("©nam", [""])[0] if "©nam" in audio.tags else ""
                    artist = audio.tags.get("©ART", [""])[0] if "©ART" in audio.tags else ""

                if not title or not artist:
                    self.log_message(f"タイトル/アーティスト不足: {filepath}")
                    continue

                song_id, err = get_uta_net_song_id(title, artist)
                if err:
                    self.log_message(f"{os.path.basename(filepath)} → {err}")
                    continue
                info, msg = get_song_page_info(song_id)
                if not info:
                    self.log_message(f"{os.path.basename(filepath)} → {msg}")
                    continue
                self.log_message(f"{os.path.basename(filepath)} → {msg}")

                lyricist = info.get("lyricist", "")
                composer = info.get("composer", "")
                arranger = info.get("arranger", "")
                mode = self.write_mode.get()
                ext = os.path.splitext(filepath)[1].lower()
                # 作詞者
                if lyricist:
                    res = set_credit_tag(filepath, "作詞者", lyricist, force_overwrite=self.overwrite_flags["作詞者"].get())
                    self.log_message(res)

                # 作曲者
                if mode == "B":
                    if composer or lyricist or arranger:
                        composer_tag_value = build_composer_tag(lyricist=lyricist, composer=composer, arranger=arranger)
                        res = set_credit_tag(filepath, "作曲者", composer_tag_value, force_overwrite=self.overwrite_flags["作曲者"].get())
                        self.log_message(res)
                elif mode == "A":
                    if composer and self.integrate_unwritable_tags.get():
                        value = build_integrated_composer(ext, info)
                        res = set_credit_tag(filepath, "作曲者", value, force_overwrite=self.overwrite_flags["作曲者"].get())
                    elif composer:
                        res = set_credit_tag(filepath, "作曲者", composer, force_overwrite=self.overwrite_flags["作曲者"].get())
                        self.log_message(res)

                # リミキサー（編曲者）
                if arranger:
                    res = set_credit_tag(filepath, "リミキサー", arranger, force_overwrite=self.overwrite_flags["リミキサー"].get())
                    self.log_message(res)

                # コメント（アニメ情報）
                if info.get("anime"):
                    res = set_credit_tag(filepath, "コメント", info["anime"], force_overwrite=self.overwrite_flags["コメント"].get())
                    self.log_message(res)

                # TreeView 更新
                tags = self.read_tags(filepath)
                self.root.after(0, lambda i=i, tags=tags: self.tree.item(self.tree.get_children()[i], values=tags))

                self.log_message(f"更新完了: {os.path.basename(filepath)}")
            except Exception:
                self.log_message(f"エラー: {filepath}\n{traceback.format_exc()}")

        self.log_message("処理が完了しました。")
        # ボタン状態を元に戻す
        self.root.after(0, lambda: self.btn_run.config(state="normal"))
        self.root.after(0, lambda: self.btn_stop.config(state="disabled"))
        # ラジオ・チェックを再度有効化
        def _enable_inputs():
            for w in self.frame_mode.winfo_children():
                try:
                    w.config(state="normal")
                except Exception:
                    pass
            for w in self.frame_overwrite.winfo_children():
                try:
                    w.config(state="normal")
                except Exception:
                    pass
        self.root.after(0, _enable_inputs)


if __name__ == "__main__":
    root = tk.Tk()
    app = AudioTagGUI(root)
    root.mainloop()
