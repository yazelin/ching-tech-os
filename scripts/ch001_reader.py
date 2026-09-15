#!/usr/bin/env python3
"""CH001_export（鼎新 e-Go 傾印）的讀取器。

來源：`smb://192.168.11.6/d/CH001_export`，590 個 `.txt`、197 個有資料。
格式：Big5 系列編碼、`|` 分隔、**無標題列**、`0x00` 表 NULL、CRLF 斷列。

## 為什麼不能 `open(...).read().decode("big5").split("|")`

Big5 雙位元組字的低位元組範圍是 `0x40-0x7E` 與 `0xA1-0xFE`，**其中 `0x7C`
就是 `|` 本身**。先 decode 再 split 有兩個獨立的壞法：

1. 用 `errors="replace"` 時，任何一個解不開的字會連帶吃掉後面的位元組，
   分隔符從那裡開始全部錯位（實測 `KJSNHB` 有 113 列因此欄數不對）。
2. 就算解得開，若改用 bytes 直接 `split(b"|")`，低位元組是 `0x7C` 的中文字
   會被從中間切斷。

所以這裡改成：**先用狀態機在 bytes 上切欄，再逐欄解碼**。

## 編碼

197 張表裡 176 張 `big5` 解得開、5 張要 `cp950`、10 張要 `big5hkscs`；
另有 6 張（客戶主檔 `TPADFA`、聯絡人 `CRMIKG`、銷貨單 `JSKKEA`/`JSKKEB`、
報價單 `DCSIAA`/`DCSIAB`）含舊系統造字（`0x8140-0xA0FE` 區，全檔共 42 處，
位元組為 `81a7`／`8168`／`836a`），三種編碼都解不開。造字不靜默丟棄，
而是落到 Unicode 私用區佔位；真要還原字形得跟原系統要造字檔。

用法：

    from ch001_reader import read
    for row in read("CH001_export/TPADGA.txt"):
        ...  # row 是 list[str]，欄位順序即原始位置
"""

LEAD = range(0x81, 0xFF)          # Big5 前導位元組
TRAIL = lambda b: 0x40 <= b <= 0x7E or 0xA1 <= b <= 0xFE

def split_row(buf: bytes):
    """把一列切成欄位（bytes），跳過雙位元組字內部的 0x7C。"""
    out, cur, i = [], bytearray(), 0
    while i < len(buf):
        c = buf[i]
        if c in LEAD and i + 1 < len(buf) and TRAIL(buf[i + 1]):
            cur += buf[i:i + 2]; i += 2; continue
        if c == 0x7C:
            out.append(bytes(cur)); cur = bytearray(); i += 1; continue
        cur.append(c); i += 1
    out.append(bytes(cur))
    return out

def decode_cell(cell: bytes, udf: dict | None = None) -> str:
    """逐欄解碼；造字用 udf 對照表，否則以 U+E000 起的私用區佔位（不靜默丟字）。"""
    for enc in ("big5hkscs", "cp950", "big5"):
        try: return cell.decode(enc)
        except UnicodeDecodeError: pass
    out, i = [], 0
    while i < len(cell):
        c = cell[i]
        if c < 0x80: out.append(chr(c)); i += 1; continue
        pair = cell[i:i + 2]
        for enc in ("big5hkscs", "cp950", "big5"):
            try: out.append(pair.decode(enc)); break
            except UnicodeDecodeError: pass
        else:
            key = pair.hex()
            out.append(udf.get(key) if udf and key in udf
                       else chr(0xE000 + (pair[0] << 8 | pair[1]) % 0x1800))
        i += 2
    return "".join(out)

def read(path, limit=None, udf=None, max_bytes=None):
    """逐列產出已解碼的欄位清單。以 CRLF 斷列（欄位內不會出現裸 CR/LF）。

    max_bytes 只讀檔頭若干位元組（盤點取樣用），會捨棄最後一段不完整的列。
    """
    with open(path, "rb") as fh:
        data = fh.read(max_bytes) if max_bytes else fh.read()
    if max_bytes and len(data) == max_bytes:
        data = data[:data.rfind(b"\r\n") + 2] or data
    data = data.replace(b"\x00", b"")
    for k, line in enumerate(data.split(b"\r\n")):
        if limit and k >= limit: break
        if not line.strip(b"| "): continue
        yield [decode_cell(c, udf).strip() for c in split_row(line)]
