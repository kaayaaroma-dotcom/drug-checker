# 医薬品供給状況チェッカー

採用薬と厚労省の医薬品供給状況データを照合して、出荷制限のある薬品を一覧表示するツールです。

---

## フォルダ構成

```
drug-checker/
├── update.py        ← 実行するだけでindex.htmlを再生成
├── README.md
├── data/
│   ├── inventory.csv   ← 職場システムからエクスポートしたCSV（差し替え用）
│   └── mhlw.xlsx       ← 厚労省からDLした最新Excel（差し替え用）
└── index.html          ← 自動生成（直接編集しない）
```

---

## 初回セットアップ（一度だけ）

### 1. Python確認
```bash
python3 --version  # 3.8以上であればOK
pip install openpyxl
```

### 2. GitHubリポジトリ作成
1. [github.com](https://github.com) でログイン
2. 右上「+」→「New repository」
3. Repository name: `drug-checker`（任意）
4. **Public** を選択（GitHub Pages無料利用のため）
5. 「Create repository」

### 3. このフォルダをGitHubにアップロード
```bash
cd drug-checker
git init
git add .
git commit -m "initial"
git branch -M main
git remote add origin https://github.com/【ユーザー名】/drug-checker.git
git push -u origin main
```

### 4. GitHub Pagesを有効化
1. GitHubのリポジトリページ → 「Settings」
2. 左メニュー「Pages」
3. Source: 「Deploy from a branch」→ Branch: `main` / `/ (root)`
4. 「Save」

数分後に `https://【ユーザー名】.github.io/drug-checker/` でアクセス可能になります。

---

## 定期更新手順（月1〜2回）

### Step 1: データ差し替え
- `data/inventory.csv` ← 職場システムから最新CSVをエクスポートして上書き
- `data/mhlw.xlsx` ← 厚労省サイトから最新Excelをダウンロードして上書き

厚労省ダウンロード先:
https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryou/kouhatu-iyaku/04_00003.html

### Step 2: HTML再生成
```bash
python3 update.py
```

### Step 3: GitHubにプッシュ
```bash
git add .
git commit -m "update $(date +%Y-%m-%d)"
git push
```

数分後にGitHub Pagesが自動更新されます。

---

## データについて

- **inventory.csv**: YJコード・医薬品名・製造販売元メーカー・在庫数 等の列が必要です
- **mhlw.xlsx**: 厚労省「医薬品安定供給・流通確認システム」のExcelファイルをそのまま使用

---

## 注意事項

- このリポジトリをPublicにする場合、在庫数・採用薬リストがインターネット上に公開されます
- 職場のルールに応じてPrivateリポジトリ＋有料プラン、またはローカル運用をご検討ください
