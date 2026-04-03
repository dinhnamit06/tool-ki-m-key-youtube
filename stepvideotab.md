# Step Video Tab - Ke hoach chi tiet + doi chieu UI

Tai lieu nay dung lam "single source of truth" cho toan bo tab `Videos`.
Muc tieu: code tung buoc nho, moi buoc co UI + logic + test + screenshot doi chieu.

## 1) Nguon doi chieu
- Tube Atlas website: https://tubeatlas.com.vn/
- YouTube ref 1: https://www.youtube.com/watch?v=sAiYwVGZ6JI&t=1471s
- YouTube ref 2: https://www.youtube.com/watch?v=bNQd7nw2Zw0
- App hien tai: `ui/videos_tab.py`, `core/videos_fetcher.py`

## 2) Nguyen tac bat buoc (UI + dev flow)
- Nen den -> chu trang.
- Nen trang -> chu den.
- Link giu mau xanh.
- Moi step lam theo thu tu: `UI -> Logic -> Test`.
- Khong nhay buoc, khong gom nhieu feature lon trong 1 step.
- Xong step phai cap nhat tai lieu nay ngay.

## 3) Hien trang da hoan thanh

### SV-01 (done) - Khung UI Videos
- Tabs mode: `Search`, `Browse or Import`, `Analyze`.
- Left panel + right table + bottom status/actions.

### SV-02 (done) - Dong bo theme V2
- Theme dark cho panel.
- Input/combo nen trang chu den.
- Button chinh do.

### SV-03 (done) - Search backend co ban
- `Search` chay that (worker nen): `core/videos_fetcher.py`.
- Do row realtime vao table.
- Co `Stop`.
- Co status message va `Total Items`.

### SV-03.1 (done) - Chinh width cot
- Fix header `Image`.
- Tang do doc bang.

### SV-03.2 (done) - Video link format
- Chuan hoa URL link video.
- Double click cot `Video Link` mo browser mac dinh.
- To mau link + tooltip full URL.

## 4) Ban do code hien tai (de doi chieu nhanh)

### `ui/videos_tab.py`
- Khoi tao/UI:
  - `__init__`, `setup_ui`
  - `_build_mode_bar`, `_build_left_panel`
  - `_build_search_left_page`, `_build_browse_left_page`, `_build_right_panel`
- Hanh vi:
  - `start_search`, `stop_search`
  - `_append_video_row`
  - `_on_table_cell_double_clicked`
  - `_update_status_labels`, `_set_status`

### `core/videos_fetcher.py`
- `VideoSearchWorker`:
  - parse trang YouTube search
  - trich xuat `videoRenderer`
  - emit tung video qua `video_signal`
  - emit status/error/finished

## 5) Chuan screenshot (SCR) bat buoc

## 5.1 Cau truc thu muc
- `docs/screenshots/videos/reference/` : anh tham chieu tu Tube Atlas/video.
- `docs/screenshots/videos/current/` : anh app hien tai.
- `docs/screenshots/videos/compare/` : anh ghep doi chieu (neu co).

## 5.2 Quy uoc ten file
- Dinh dang:
  - `REF-SV-<step>-<slug>.png`
  - `CUR-SV-<step>-<slug>.png`
  - `CMP-SV-<step>-<slug>.png`
- Vi du:
  - `REF-SV-03-search-mode-layout.png`
  - `CUR-SV-03-search-mode-layout.png`
  - `CMP-SV-03-layout-side-by-side.png`

## 5.3 Danh sach SCR toi thieu
- `SV-01`:
  - full tab Videos (chua data)
  - mode bar (`Search`, `Browse or Import`, `Analyze`)
- `SV-02`:
  - panel trai dark + input white/black
  - right table theme
- `SV-03`:
  - dang search (status running)
  - sau khi xong (Total Items > 0)
  - nut Stop dang enabled trong luc chay
- `SV-03.1`:
  - header Image khong bi cat
  - cot chinh de doc
- `SV-03.2`:
  - cot Video Link co mau link
  - tooltip URL full
  - browser mo link khi double-click

## 5.4 Mau bang doi chieu SCR (copy cho moi step)
| ID | Mo ta can chup | File ref | File current | Ket qua |
|---|---|---|---|---|
| SCR-1 | Full layout | REF-... | CUR-... | PASS/FAIL |
| SCR-2 | Control state | REF-... | CUR-... | PASS/FAIL |
| SCR-3 | Data table | REF-... | CUR-... | PASS/FAIL |

## 6) Roadmap day du (khong gioi han 12 step)

## Pha A - Search mode

### SV-04 - Thumbnail cot Image (async)
- UI:
  - Cot `Image` hien thumbnail that (khong con N/A).
- Logic:
  - tai thumbnail async, co fallback khi loi.
- Test:
  - 20 rows -> thumbnail hien tuan tu.
  - UI khong giat lag.
- SCR:
  - cot Image truoc/sau khi load xong.

### SV-05 - Search options mapping that
- UI:
  - Sort, subtitles, creative commons, page count.
- Logic:
  - map option vao request/loc ket qua.
- Test:
  - doi sort -> thu tu ket qua doi.
  - subtitles/license filter co tac dung.
- SCR:
  - tung option bat/tat.

### SV-06 - Table context menu (Videos)
- UI:
  - right-click menu day du.
- Logic:
  - copy selected/all, delete selected, open link.
- Test:
  - selected theo checkbox hoat dong dung.
- SCR:
  - menu + ket qua copy/delete.

### SV-07 - Filter dialog (Videos)
- UI:
  - popup filter theo source/text/range.
- Logic:
  - apply/reset filter.
- Test:
  - filter on/off dung so luong row.
- SCR:
  - dialog + truoc/sau filter.

### SV-08 - Search trong table
- UI:
  - popup quick search.
- Logic:
  - highlight va next/prev match.
- Test:
  - tim title/description keyword.
- SCR:
  - highlight ket qua.

### SV-09 - Auto-fit + Reset columns
- UI:
  - menu item va nut neu can.
- Logic:
  - auto-fit all, reset default widths.
- Test:
  - width doi dung va reset dung.
- SCR:
  - truoc/sau auto-fit.

## Pha B - Browse/Import mode

### SV-10 - Parse many links (multiline)
- UI:
  - input multiline one-link-per-line.
- Logic:
  - parse, clean, dedupe link.
- Test:
  - mix link hop le/khong hop le.
- SCR:
  - input mau + ket qua parse.

### SV-11 - Get Data for imported links
- UI:
  - Get Data co progress/status.
- Logic:
  - fetch metadata theo link.
  - do row realtime.
- Test:
  - 10 links -> hien 10 row.
- SCR:
  - running + finished states.

### SV-12 - Validation + Error handling
- UI:
  - thong bao loi ro rang.
- Logic:
  - retry nhe.
  - skip row loi khong vo ca batch.
- Test:
  - simulate timeout/invalid URL.
- SCR:
  - message box/status loi.

## Pha C - Data tools + output

### SV-13 - File/Export that
- UI:
  - File menu: CSV/Excel/TXT.
- Logic:
  - xuat dung cot, dung encoding.
- Test:
  - mo file va so khop row/cot.
- SCR:
  - menu + file output.

### SV-14 - Filters button backend
- UI:
  - button Filters khong con placeholder.
- Logic:
  - mo filter dialog that.
- Test:
  - ket qua filter tuong duong right-click.
- SCR:
  - button flow.

### SV-15 - Clear/File UX polish
- UI:
  - clear confirm, status update.
- Logic:
  - clear nhanh khi dataset lon.
- Test:
  - clear 100+ rows.
- SCR:
  - before/after clear.

## Pha D - Analyze mode

### SV-16 - Analyze panel UI
- UI:
  - cards thong ke co ban.
- Logic:
  - tinh tren dataset hien tai.
- Test:
  - thay doi data -> chi so doi.
- SCR:
  - panel analyze full.

### SV-17 - Analyze metrics backend
- Chi so goi y:
  - avg title length,
  - top repeated terms,
  - source ratio,
  - missing description ratio.
- Test:
  - metrics khop data thuc.
- SCR:
  - ket qua metrics.

## Pha E - On dinh + polish

### SV-18 - Performance hardening
- Muc tieu:
  - 100 rows van muot.
  - loading non-blocking.
- Test:
  - benchmark nhe.
- SCR:
  - status khi load lon.

### SV-19 - Regression checklist
- Kiem tra lai toan bo:
  - Search mode
  - Browse mode
  - Context menu
  - Filter/Search
  - Export
  - Analyze

### SV-20 - Final UX polish
- spacing, icon, tooltip, empty states.
- chot ban release-ready.

## 7) Checklist test manual (dung lai moi lan)
- [ ] Search phrase rong -> canh bao.
- [ ] Search phrase hop le -> co data.
- [ ] Stop dung giua qua trinh.
- [ ] Link double-click mo browser.
- [ ] Checkbox row + selected counter dung.
- [ ] Table clear update counters.
- [ ] Status message dung theo state.
- [ ] App khong freeze khi dang load.

## 8) Muc ghi chu doi chieu (update sau moi step)
- Step vua xong:
- File da sua:
- Test da chay:
- SCR da chup:
- Van de ton dong:

## 9) Quy dinh truoc khi sang step tiep
- Neu step hien tai chua PASS UI + PASS logic + PASS test + co SCR -> khong qua step moi.

