#!/usr/bin/env python3
"""
医薬品供給状況チェッカー 更新スクリプト
=========================================
使い方:
  1. data/inventory.csv  ← 職場システムからエクスポートしたCSVに差し替え
  2. data/mhlw.xlsx      ← 厚労省サイトからDLした最新Excelに差し替え
  3. python3 update.py   ← 実行するとindex.htmlが再生成される
  4. git add . && git commit -m "update" && git push  ← GitHub Pagesに反映
"""

import csv
import json
import sys
from datetime import date
from pathlib import Path

# --- 依存ライブラリ確認 ---
try:
    import openpyxl
except ImportError:
    print("openpyxlをインストールします...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "openpyxl", "--break-system-packages", "-q"])
    import openpyxl

# --- パス設定 ---
BASE_DIR  = Path(__file__).parent
DATA_DIR  = BASE_DIR / "data"
INVENTORY = DATA_DIR / "inventory.csv"
MHLW_XLSX = DATA_DIR / "mhlw.xlsx"
OUTPUT    = BASE_DIR / "index.html"

# --- 採用薬CSV読み込み ---
def load_inventory(path: Path) -> list[dict]:
    inventory = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            inventory.append(row)
    print(f"  採用薬: {len(inventory)} 品")
    return inventory

# --- 厚労省Excel読み込み（照合用 + 全件検索用を同時取得）---
def load_mhlw(path: Path) -> tuple[dict, list[dict]]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    mhlw_map  = {}   # YJコード → 照合用dict（タブ①）
    mhlw_all  = []   # 全件リスト（タブ②）
    count = 0
    for row in ws.iter_rows(min_row=3, values_only=True):
        yj = str(row[4]).strip() if row[4] else ""
        if not yj or yj == "None":
            continue

        # タブ① 照合用（既存と同じ）
        mhlw_map[yj] = {
            "name":    str(row[5]).strip()  if row[5]  else "",
            "maker":   str(row[6]).strip()  if row[6]  else "",
            "status":  str(row[11]).strip() if row[11] else "",
            "reason":  str(row[13]).strip() if row[13] else "",
            "outlook": str(row[14]).strip() if row[14] else "",
            "volume":  str(row[16]).strip() if row[16] else "",
        }

        # タブ② 全件検索用（列を拡張）
        mhlw_all.append({
            "yj":      yj,
            "cls":     str(row[1]).strip()  if row[1]  else "",   # ②薬効分類
            "comp":    str(row[2]).strip()  if row[2]  else "",   # ③成分名
            "unit":    str(row[3]).strip()  if row[3]  else "",   # ④規格単位
            "name":    str(row[5]).strip()  if row[5]  else "",   # ⑥品名
            "maker":   str(row[6]).strip()  if row[6]  else "",   # ⑦製造販売業者名
            "status":  str(row[11]).strip() if row[11] else "",   # ⑫出荷対応
            "updated": str(row[12]).strip() if row[12] else "",   # ⑬情報更新日
            "reason":  str(row[13]).strip() if row[13] else "",   # ⑭限定出荷/供給停止の理由
            "outlook": str(row[14]).strip() if row[14] else "",   # ⑮解除見込み
            "volume":  str(row[16]).strip() if row[16] else "",   # ⑰出荷量
        })
        count += 1
    wb.close()
    print(f"  厚労省データ: {count} 品")
    return mhlw_map, mhlw_all

# --- マッチング（タブ①用・既存と同じ）---
def merge(inventory: list[dict], mhlw: dict) -> list[dict]:
    results = []
    for item in inventory:
        yj = item["YJコード"].strip()
        m  = mhlw.get(yj)
        results.append({
            "yj":      yj,
            "name":    item["医薬品名"],
            "maker":   item["製造販売元メーカー"],
            "stock":   item["在庫数"],
            "status":  m["status"]  if m else "未掲載",
            "reason":  m["reason"]  if m else "",
            "outlook": m["outlook"] if m else "",
            "volume":  m["volume"]  if m else "",
            "last_rx": item["最終処方日"],
            "expire":  item["直近の有効期限"],
        })

    restricted = [r for r in results if r["status"] not in ("未掲載", "①通常出荷", "")]
    print(f"  出荷制限あり: {len(restricted)} 品 / {len(results)} 品中")
    return results

# --- HTML生成 ---
def build_html(data: list[dict], mhlw_all: list[dict], updated: str) -> str:
    js_data     = json.dumps(data,     ensure_ascii=False, separators=(",", ":"))
    js_mhlw_all = json.dumps(mhlw_all, ensure_ascii=False, separators=(",", ":"))

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>医薬品供給状況チェッカー</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=IBM+Plex+Mono:wght@400;600&display=swap');
  :root {{
    --bg:#f4f2ee;--surface:#fff;--border:#d8d3c8;--text:#1a1814;--muted:#7a7570;
    --accent:#2c5282;
    --ok:#276749;--ok-bg:#f0fff4;--ok-bd:#9ae6b4;
    --warn:#744210;--warn-bg:#fffbeb;--warn-bd:#f6ad55;
    --danger:#742a2a;--danger-bg:#fff5f5;--danger-bd:#fc8181;
    --ul:#4a5568;--ul-bg:#f7fafc;--ul-bd:#cbd5e0;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Noto Sans JP',sans-serif;background:var(--bg);color:var(--text);min-height:100vh}}

  /* ── タブ ── */
  .tab-bar{{background:var(--text);display:flex;padding:0 16px;gap:4px;position:sticky;top:0;z-index:200}}
  .tab-btn{{padding:14px 18px 12px;color:#a0aec0;font-size:13px;font-weight:600;cursor:pointer;border:none;background:none;border-bottom:3px solid transparent;font-family:'Noto Sans JP',sans-serif;transition:all .15s;white-space:nowrap}}
  .tab-btn.active{{color:#fff;border-bottom-color:#68d391}}
  .tab-pane{{display:none}}
  .tab-pane.active{{display:block}}

  header{{background:var(--text);color:#fff;padding:14px 20px 10px;}}
  header h1{{font-size:15px;font-weight:700;letter-spacing:.05em;margin-bottom:3px}}
  header .sub{{font-size:11px;color:#a0aec0;font-family:'IBM Plex Mono',monospace}}

  .controls{{padding:14px 16px;background:var(--surface);border-bottom:1px solid var(--border);display:flex;flex-wrap:wrap;gap:10px;align-items:center}}
  .search-wrap{{flex:1;min-width:200px;position:relative}}
  .search-wrap::before{{content:'🔍';position:absolute;left:10px;top:50%;transform:translateY(-50%);font-size:13px}}
  .search-wrap input{{width:100%;padding:9px 12px 9px 34px;border:1.5px solid var(--border);border-radius:8px;font-size:14px;font-family:'Noto Sans JP',sans-serif;background:var(--bg);color:var(--text);outline:none;transition:border-color .15s}}
  .search-wrap input:focus{{border-color:var(--accent)}}
  .filters{{display:flex;gap:6px;flex-wrap:wrap;align-items:center}}
  .fbtn{{padding:7px 12px;border-radius:20px;border:1.5px solid var(--border);background:var(--surface);font-size:12px;font-family:'Noto Sans JP',sans-serif;cursor:pointer;transition:all .15s;white-space:nowrap;font-weight:500}}
  .fbtn.active, .fbtn.f-all{{background:var(--text);color:#fff;border-color:var(--text)}}
  .fbtn.f-danger{{background:var(--danger-bg);color:var(--danger);border-color:var(--danger-bd)}}
  .fbtn.f-warn{{background:var(--warn-bg);color:var(--warn);border-color:var(--warn-bd)}}
  .fbtn.f-ok{{background:var(--ok-bg);color:var(--ok);border-color:var(--ok-bd)}}

  /* ── 検索フィルター（タブ②） ── */
  .search-grid{{padding:12px 16px;background:var(--surface);border-bottom:1px solid var(--border);display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:8px}}
  .sf-wrap{{display:flex;flex-direction:column;gap:3px}}
  .sf-wrap label{{font-size:11px;color:var(--muted);font-weight:500}}
  .sf-wrap input, .sf-wrap select{{padding:7px 10px;border:1.5px solid var(--border);border-radius:6px;font-size:13px;font-family:'Noto Sans JP',sans-serif;background:var(--bg);color:var(--text);outline:none}}
  .sf-wrap input:focus, .sf-wrap select:focus{{border-color:var(--accent)}}

  .stats{{padding:9px 16px;display:flex;gap:16px;font-size:12px;color:var(--muted);border-bottom:1px solid var(--border);background:var(--surface);font-family:'IBM Plex Mono',monospace;flex-wrap:wrap}}
  .si{{display:flex;align-items:center;gap:5px}}
  .dot{{width:8px;height:8px;border-radius:50%}}
  .dot.d{{background:#fc8181}}.dot.w{{background:#f6ad55}}.dot.o{{background:#68d391}}
  .wrap{{padding:12px 16px}}
  table{{width:100%;border-collapse:collapse;background:var(--surface);border-radius:10px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08);font-size:13px}}
  thead{{background:#2d3748;color:#e2e8f0}}
  thead th{{padding:10px 12px;text-align:left;font-weight:600;font-size:11px;letter-spacing:.06em;white-space:nowrap}}
  tbody tr{{border-bottom:1px solid #f0ede8;transition:background .1s}}
  tbody tr:hover{{background:#fafaf8}}
  tbody tr:last-child{{border-bottom:none}}
  td{{padding:9px 12px;vertical-align:middle}}
  .dname{{font-weight:500;font-size:12.5px;line-height:1.4;max-width:240px}}
  .dmaker{{font-size:11px;color:var(--muted);margin-top:2px}}
  .dcomp{{font-size:11px;color:var(--muted);margin-top:2px;font-style:italic}}
  .yj{{font-family:'IBM Plex Mono',monospace;font-size:10.5px;color:var(--muted)}}
  .badge{{display:inline-block;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:600;white-space:nowrap;border:1px solid}}
  .bs{{background:var(--danger-bg);color:var(--danger);border-color:var(--danger-bd)}}
  .bw{{background:var(--warn-bg);color:var(--warn);border-color:var(--warn-bd)}}
  .bo{{background:var(--ok-bg);color:var(--ok);border-color:var(--ok-bd)}}
  .bu{{background:var(--ul-bg);color:var(--ul);border-color:var(--ul-bd)}}
  .reason{{font-size:11px;color:var(--muted);max-width:180px;line-height:1.3}}
  .snum{{font-family:'IBM Plex Mono',monospace;font-size:12px;text-align:right}}
  .szero{{color:var(--danger);font-weight:600}}
  .none{{text-align:center;padding:48px;color:var(--muted)}}
  .foot{{text-align:center;padding:16px;font-size:11px;color:var(--muted);border-top:1px solid var(--border)}}
  @media(max-width:600px){{.hsp{{display:none}}.dname{{max-width:150px}}}}
</style>
</head>
<body>

<header>
  <h1>💊 医薬品供給状況チェッカー</h1>
  <div class="sub">厚労省データ照合 · 最終更新 {updated}</div>
</header>

<!-- タブバー -->
<div class="tab-bar">
  <button class="tab-btn active" onclick="switchTab('t1',this)">📋 採用薬チェック</button>
  <button class="tab-btn"        onclick="switchTab('t2',this)">🔍 供給状況検索</button>
</div>

<!-- ═══════════════════════════════════════════
     タブ① 採用薬チェック（既存機能）
═══════════════════════════════════════════ -->
<div id="t1" class="tab-pane active">
  <div class="controls">
    <div class="search-wrap">
      <input type="text" id="q1" placeholder="薬品名・メーカー・YJコードで検索..." oninput="render1()">
    </div>
    <div class="filters">
      <button class="fbtn f-all"  id="b1-all"    onclick="filt1('all')">すべて</button>
      <button class="fbtn"        id="b1-danger"  onclick="filt1('danger')">⛔ 供給停止</button>
      <button class="fbtn"        id="b1-warn"    onclick="filt1('warn')">⚠️ 限定出荷</button>
      <button class="fbtn"        id="b1-ok"      onclick="filt1('ok')">✅ 通常出荷</button>
    </div>
  </div>
  <div class="stats" id="stats1"></div>
  <div class="wrap">
    <table>
      <thead><tr>
        <th>医薬品名</th>
        <th class="hsp">YJコード</th>
        <th>供給状況</th>
        <th class="hsp">理由</th>
        <th>在庫数</th>
      </tr></thead>
      <tbody id="tbody1"></tbody>
    </table>
    <div class="none" id="none1" style="display:none">該当する医薬品が見つかりません</div>
  </div>
</div>

<!-- ═══════════════════════════════════════════
     タブ② 供給状況全件検索
═══════════════════════════════════════════ -->
<div id="t2" class="tab-pane">
  <div class="search-grid">
    <div class="sf-wrap">
      <label>品名 / 成分名</label>
      <input type="text" id="q2-name" placeholder="例：アムロジピン" oninput="render2()">
    </div>
    <div class="sf-wrap">
      <label>製造販売業者</label>
      <input type="text" id="q2-maker" placeholder="例：日医工" oninput="render2()">
    </div>
    <div class="sf-wrap">
      <label>薬効分類</label>
      <input type="text" id="q2-cls" placeholder="例：214" oninput="render2()">
    </div>
    <div class="sf-wrap">
      <label>出荷対応</label>
      <select id="q2-status" onchange="render2()">
        <option value="">すべて</option>
        <option value="①通常出荷">①通常出荷</option>
        <option value="②限定出荷（自社の事情）">②限定出荷（自社）</option>
        <option value="③限定出荷（他社品の影響）">③限定出荷（他社品）</option>
        <option value="④限定出荷（その他）">④限定出荷（その他）</option>
        <option value="⑤供給停止">⑤供給停止</option>
      </select>
    </div>
    <div class="sf-wrap">
      <label>出荷量</label>
      <select id="q2-volume" onchange="render2()">
        <option value="">すべて</option>
        <option value="A．出荷量通常">A．通常</option>
        <option value="Aプラス．出荷量増加">A+．増加</option>
        <option value="B．出荷量減少">B．減少</option>
        <option value="C．出荷停止">C．停止</option>
        <option value="D．薬価削除予定">D．薬価削除予定</option>
      </select>
    </div>
  </div>
  <div class="stats" id="stats2"></div>
  <div class="wrap">
    <table>
      <thead><tr>
        <th>品名 / 成分名</th>
        <th class="hsp">薬効分類</th>
        <th>出荷対応</th>
        <th class="hsp">理由 / 解除見込み</th>
        <th class="hsp">出荷量</th>
      </tr></thead>
      <tbody id="tbody2"></tbody>
    </table>
    <div class="none" id="none2" style="display:none">該当する医薬品が見つかりません</div>
  </div>
</div>

<div class="foot">
  厚労省「医薬品安定供給・流通確認システム」データをもとに照合<br>
  更新: data/ の2ファイルを差し替えて <code>python3 update.py</code> を実行
</div>

<script>
// ─── データ ───
const D1 = {js_data};
const D2 = {js_mhlw_all};

// ─── タブ切替 ───
function switchTab(id, btn) {{
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  btn.classList.add('active');
}}

// ═══════════════════════════════
// タブ① 採用薬チェック
// ═══════════════════════════════
const cat1 = s => !s || s === '未掲載' ? 'u' : s.includes('供給停止') ? 'd' : s.includes('限定出荷') ? 'w' : s.includes('通常') ? 'o' : 'u';
const badge1 = s => {{
  const c = cat1(s);
  const m = {{d:['bs','⛔ 供給停止'], w:['bw','⚠️ 限定出荷'], o:['bo','✅ 通常出荷'], u:['bu','— 未掲載']}};
  const [cl, lb] = m[c];
  return `<span class="badge ${{cl}}">${{lb}}</span>`;
}};
let cf1 = 'all';
function render1() {{
  const q = document.getElementById('q1').value.toLowerCase();
  const order = {{d:0, w:1, o:2, u:3}};
  let fd = D1.filter(d => {{
    const ms = !q || d.name.toLowerCase().includes(q) || d.maker.toLowerCase().includes(q) || d.yj.toLowerCase().includes(q);
    const mf = cf1 === 'all' ? true : cat1(d.status) === cf1[0];
    return ms && mf;
  }}).sort((a,b) => order[cat1(a.status)] - order[cat1(b.status)]);
  const cnt = {{d:0, w:0, o:0, u:0}};
  fd.forEach(d => cnt[cat1(d.status)]++);
  document.getElementById('stats1').innerHTML =
    `<span class="si"><span class="dot d"></span>供給停止 <strong>${{cnt.d}}</strong></span>` +
    `<span class="si"><span class="dot w"></span>限定出荷 <strong>${{cnt.w}}</strong></span>` +
    `<span class="si"><span class="dot o"></span>通常出荷 <strong>${{cnt.o}}</strong></span>` +
    `<span class="si">未掲載 <strong>${{cnt.u}}</strong></span>` +
    `<span class="si" style="margin-left:auto">表示 <strong>${{fd.length}}</strong>件</span>`;
  const tb = document.getElementById('tbody1');
  if (!fd.length) {{ tb.innerHTML = ''; document.getElementById('none1').style.display = 'block'; return; }}
  document.getElementById('none1').style.display = 'none';
  tb.innerHTML = fd.map(d =>
    `<tr><td><div class="dname">${{d.name}}</div><div class="dmaker">${{d.maker}}</div></td>` +
    `<td class="yj hsp">${{d.yj}}</td><td>${{badge1(d.status)}}</td>` +
    `<td class="reason hsp">${{d.reason ? d.reason.replace(/^[\\d０-９]+[．.] */,'') : '—'}}</td>` +
    `<td class="snum${{parseFloat(d.stock)===0?' szero':''}}">${{d.stock}}</td></tr>`
  ).join('');
}}
function filt1(f) {{
  cf1 = f;
  document.querySelectorAll('#t1 .fbtn').forEach(b => b.className = 'fbtn');
  const m = {{all:'f-all', danger:'f-danger', warn:'f-warn', ok:'f-ok'}};
  document.getElementById('b1-'+f).classList.add(m[f]);
  render1();
}}

// ═══════════════════════════════
// タブ② 供給状況全件検索
// ═══════════════════════════════
const cat2 = s => !s ? 'u' : s.includes('供給停止') ? 'd' : s.includes('限定出荷') ? 'w' : s.includes('通常') ? 'o' : 'u';
const badge2 = s => {{
  if (!s) return '<span class="badge bu">—</span>';
  const c = cat2(s);
  const m = {{d:['bs','⛔ 供給停止'], w:['bw','⚠️ 限定出荷'], o:['bo','✅ 通常'], u:['bu','—']}};
  const [cl, lb] = m[c];
  return `<span class="badge ${{cl}}">${{lb}}</span>`;
}};

function render2() {{
  const qName   = document.getElementById('q2-name').value.toLowerCase();
  const qMaker  = document.getElementById('q2-maker').value.toLowerCase();
  const qCls    = document.getElementById('q2-cls').value.toLowerCase();
  const qStatus = document.getElementById('q2-status').value;
  const qVol    = document.getElementById('q2-volume').value;

  const order = {{d:0, w:1, o:2, u:3}};
  let fd = D2.filter(d => {{
    if (qName   && !d.name.toLowerCase().includes(qName) && !d.comp.toLowerCase().includes(qName)) return false;
    if (qMaker  && !d.maker.toLowerCase().includes(qMaker))  return false;
    if (qCls    && !d.cls.toLowerCase().includes(qCls))      return false;
    if (qStatus && d.status !== qStatus)                     return false;
    if (qVol    && d.volume !== qVol)                        return false;
    return true;
  }}).sort((a,b) => order[cat2(a.status)] - order[cat2(b.status)]);

  const cnt = {{d:0, w:0, o:0, u:0}};
  fd.forEach(d => cnt[cat2(d.status)]++);
  document.getElementById('stats2').innerHTML =
    `<span class="si"><span class="dot d"></span>供給停止 <strong>${{cnt.d}}</strong></span>` +
    `<span class="si"><span class="dot w"></span>限定出荷 <strong>${{cnt.w}}</strong></span>` +
    `<span class="si"><span class="dot o"></span>通常出荷 <strong>${{cnt.o}}</strong></span>` +
    `<span class="si" style="margin-left:auto">表示 <strong>${{fd.length}}</strong> / 全${{D2.length}}件</span>`;

  const tb = document.getElementById('tbody2');
  // 表示上限：5000件（ブラウザ負荷対策）
  const show = fd.slice(0, 5000);
  if (!fd.length) {{ tb.innerHTML = ''; document.getElementById('none2').style.display = 'block'; return; }}
  document.getElementById('none2').style.display = 'none';
  tb.innerHTML = show.map(d =>
    `<tr><td><div class="dname">${{d.name}}</div>` +
    `<div class="dcomp">${{d.comp}}</div>` +
    `<div class="dmaker">${{d.maker}}</div></td>` +
    `<td class="hsp" style="font-size:11px;color:var(--muted)">${{d.cls}}</td>` +
    `<td>${{badge2(d.status)}}</td>` +
    `<td class="reason hsp">${{
      (d.reason  ? d.reason.replace(/^[\\d０-９]+[．.] */,'')  : '') +
      (d.outlook ? '<br><span style="color:#2c5282">解除見込: ' + d.outlook + '</span>' : '')
      || '—'
    }}</td>` +
    `<td class="hsp" style="font-size:11px">${{d.volume || '—'}}</td></tr>`
  ).join('');
  // 件数が多い場合の注記
  if (fd.length > 5000) {{
    tb.innerHTML += `<tr><td colspan="5" style="text-align:center;padding:12px;font-size:12px;color:var(--muted)">※ 上位5,000件を表示中（全${{fd.length}}件）— 検索条件を絞ってください</td></tr>`;
  }}
}}

// 初期描画
render1();
render2();
</script>
</body>
</html>"""

# --- メイン ---
def main():
    print("=== 医薬品供給状況チェッカー 更新スクリプト ===")

    for p in [INVENTORY, MHLW_XLSX]:
        if not p.exists():
            print(f"エラー: {p} が見つかりません")
            sys.exit(1)

    print("読み込み中...")
    inventory          = load_inventory(INVENTORY)
    mhlw_map, mhlw_all = load_mhlw(MHLW_XLSX)

    print("照合中...")
    data = merge(inventory, mhlw_map)

    print("HTML生成中...")
    updated = date.today().strftime("%Y-%m-%d")
    html = build_html(data, mhlw_all, updated)
    OUTPUT.write_text(html, encoding="utf-8")

    print(f"\n✅ 完了: {OUTPUT}")
    print("次のステップ:")
    print(f"  git add . && git commit -m \"update {updated}\" && git push")

if __name__ == "__main__":
    main()
