# Step Video Tab - Ke hoach chi tiet + doi chieu UI

Tai lieu nay dung lam "single source of truth" cho toan bo tab `Videos`.
Muc tieu: code tung buoc nho, moi buoc co UI + logic + test + screenshot doi chieu.

## 1) Nguon doi chieu
- Tube Atlas website: https://tubeatlas.com.vn/
- YouTube ref 1: https://www.youtube.com/watch?v=sAiYwVGZ6JI&t=1471s
- YouTube ref 2: https://www.youtube.com/watch?v=bNQd7nw2Zw0
- App hien tai: `ui/videos_tab.py`, `core/videos_fetcher.py`

## 1.1) Nguon moi user cung cap (uu tien cao)
- Help index (44 videos):
  - https://appbreed.com/help-videos-tube-atlas/
- Vimeo clips xac thuc:
  - 21 tube-atlas-downloading-videos: https://vimeo.com/702556179
  - 22 tube-atlas-download-video-thumbnails: https://vimeo.com/702556184
  - 11 tube-atlas-analyze-titles: https://vimeo.com/702556396
  - 14 tube-atlas-channels-tool: https://vimeo.com/702556438
  - Tube Atlas Trends tool: https://vimeo.com/713284733
- URL screenshot/thumbnail `vimeocdn` da xac thuc:
  - Videos tool (Search mode): https://i.vimeocdn.com/video/1419479442-225a8d75a5e147046b24d5bc42809210458338bcd247dea80cb1cf123f1ee77a-d?f=webp&region=us
  - Videos tool (Browse or Import mode): https://i.vimeocdn.com/video/1419479539-3c164ccfe087f1be85cbd5ec0fae467bf23701d86c19d625b4c3fc5b5ac9646b-d?f=webp&region=us
  - Filters UI: https://i.vimeocdn.com/video/1419479192-db34db2e3e910198fb9dcdac6e57b46ab93d46bb439e82ce8ccb899a892b9fbb-d?f=webp&region=us
  - Video ads: https://i.vimeocdn.com/video/1461701338-5f303f9adc5cbeaac3242d67753c45b920c2b0ea1a9b9e0b29b0fb12638aefab-d?f=webp&region=us
  - Related videos: https://i.vimeocdn.com/video/1461701108-cb750a85f7ab9bec09ae22e1d01323e7ba7d562a3edfb8635d3ccc23568edda2-d?f=webp&region=us
  - Ad-free player: https://i.vimeocdn.com/video/1503065816-3b5ae9b61c7e25195977288af161da6e1a824e3f395603b3a9af5f99e19cb35e-d?f=webp&region=us
  - Column configuration: https://i.vimeocdn.com/video/1503065455-3fe45b8d3876b97ac54b35253cc678ddbe71d087e570ce848ce079bf022daf2b-d?f=webp&region=us

## 1.2) Mapping nguon -> chuc nang can clone
| Nguon | Man hinh/chuc nang suy ra | Uu tien | Step de lam |
|---|---|---|---|
| https://appbreed.com/help-videos-tube-atlas/ | full feature inventory, ten nut/menu dung goc | P0 | SV-00A |
| https://vimeo.com/702556377 | layout chuan search mode, width cot, status strip | P0 | SV-03.x, SV-09 |
| https://vimeo.com/702556409 | luong browse/import links, nut Get Data, panel tra ve | P0 | SV-10, SV-11 |
| https://vimeo.com/747379514 | popup/player details cua video (co lien quan video-details/player) | P1 | SV-21, SV-24 |
| https://vimeo.com/702556224 | filter dialog day du + preset | P1 | SV-07, SV-14, SV-22 |
| https://vimeo.com/726146748 | thao tac video ads | P2 | SV-23 |
| https://vimeo.com/726146770 | related videos actions | P2 | SV-23 |
| https://vimeo.com/747379500 | chon an/hien cot, luu cau hinh cot | P1 | SV-25 |
| https://vimeo.com/702556179 | download video queue + progress | P1 | SV-26 |
| https://vimeo.com/702556184 | download thumbnails hang loat | P1 | SV-27 |
| https://vimeo.com/702556396 | analyze title module chi tiet | P1 | SV-17, SV-28 |
| https://vimeo.com/702556438 | handoff tu video -> channels | P2 | SV-29 |

## 1.3) Rule cap nhat nguon tham chieu
- Moi khi co anh/video moi:
  - them vao muc 1.1,
  - map vao bang 1.2,
  - tao SCR id trong muc 5.
- Neu ten nut/menu tren ref khac app:
  - uu tien doi ten theo ref (tru khi co ly do ky thuat).

## 1.4) Mapping ten anh user -> URL tham chieu da tim thay
- `video-details-3.png` -> tham chieu player/details:
  - https://vimeo.com/747379514
  - https://i.vimeocdn.com/video/1503065816-3b5ae9b61c7e25195977288af161da6e1a824e3f395603b3a9af5f99e19cb35e-d?f=webp&region=us
- `filters.png` -> tham chieu filters:
  - https://vimeo.com/702556224
  - https://i.vimeocdn.com/video/1419479192-db34db2e3e910198fb9dcdac6e57b46ab93d46bb439e82ce8ccb899a892b9fbb-d?f=webp&region=us
- `video-ads-1.png` -> tham chieu video ads:
  - https://vimeo.com/726146748
  - https://i.vimeocdn.com/video/1461701338-5f303f9adc5cbeaac3242d67753c45b920c2b0ea1a9b9e0b29b0fb12638aefab-d?f=webp&region=us
- `video-player-1.png` -> tham chieu ad-free player:
  - https://vimeo.com/747379514
  - https://i.vimeocdn.com/video/1503065816-3b5ae9b61c7e25195977288af161da6e1a824e3f395603b3a9af5f99e19cb35e-d?f=webp&region=us
- `column-configuration-1.png` -> tham chieu column config:
  - https://vimeo.com/747379500
  - https://i.vimeocdn.com/video/1503065455-3fe45b8d3876b97ac54b35253cc678ddbe71d087e570ce848ce079bf022daf2b-d?f=webp&region=us

## 2) Nguyen tac bat buoc (UI + dev flow)
- Nen den -> chu trang.
- Nen trang -> chu den.
- Link giu mau xanh.
- Moi step lam theo thu tu: `UI -> Logic -> Test`.
- Quy tac phoi hop (cap nhat 2026-04-03):
  - Sau khi xong phan UI cua step, phai dung va cho user xac nhan.
  - Khong tu dong lam tiep backend neu chua co xac nhan.
  - Chi gop UI+backend trong mot lan neu user yeu cau ro rang.
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
- `SV-21`:
  - popup video details (header + metadata + actions)
- `SV-22`:
  - filters dialog day du fields + apply/reset
- `SV-25`:
  - column configuration popup + an/hien cot
- `SV-26`:
  - download videos queue + progress bar
- `SV-27`:
  - thumbnail downloader result folder + status

## 5.4 Mau bang doi chieu SCR (copy cho moi step)
| ID | Mo ta can chup | File ref | File current | Ket qua |
|---|---|---|---|---|
| SCR-1 | Full layout | REF-... | CUR-... | PASS/FAIL |
| SCR-2 | Control state | REF-... | CUR-... | PASS/FAIL |
| SCR-3 | Data table | REF-... | CUR-... | PASS/FAIL |

## 6) Roadmap day du (khong gioi han 12 step)

## Pha A - Search mode

### SV-04 - Thumbnail cot Image (async) (done)
- UI:
  - Cot `Image` hien thumbnail that (khong con N/A).
- Logic:
  - tai thumbnail async, co fallback khi loi.
  - cache thumbnail theo URL.
  - doi kich thuoc thumbnail theo slider Image Size.
- Test:
  - 20 rows -> thumbnail hien tuan tu.
  - UI khong giat lag.
- SCR:
  - cot Image truoc/sau khi load xong.

### SV-05 - Search options mapping that (done)
- UI:
  - Sort, subtitles, creative commons, page count.
- Logic:
  - map option vao worker search:
    - `Sort`: Relevance / Upload date / View count (Rating fallback ve Relevance do du lieu rating khong on dinh tren YouTube search hien tai).
    - `Contains subtitles`: loc theo thong tin caption tracks tren watch page.
    - `Creative Commons License`: loc theo license text tren watch page.
    - `Pages`: quy doi `max_results` (1 page ~ 20 rows), kem `first_page_only` scan limit.
- Test:
  - doi sort -> thu tu ket qua thay doi (upload date/view count).
  - subtitles/license filter co tac dung (co the cham hon do can check watch page).
- SCR:
  - tung option bat/tat.

### SV-05A - Trending Videos button backend (done)
- UI:
  - nut `Trending Videos` khong con placeholder.
  - them `Trending region` combo (co ban).
- Logic:
  - worker rieng `TrendingVideosWorker` fetch tu `/feed/trending`.
  - do row realtime vao table + dung `Stop` chung.
  - ho tro region code co ban (US, VN, GB, IN, JP, KR, BR, DE, FR).
- Test:
  - bam nut -> co data vao table.
- SCR:
  - before/after click Trending Videos.

### SV-06 - Table context menu (Videos) (done)
- UI:
  - right-click menu day du.
- Logic:
  - `Open Video Link` cho row dang click.
  - `Copy` submenu:
    - copy selected rows (uu tien checkbox, fallback row highlight)
    - copy all rows
    - copy selected/all video links
  - delete selected rows + delete all rows (co confirm).
- Test:
  - selected theo checkbox hoat dong dung.
- SCR:
  - menu + ket qua copy/delete.

### SV-07 - Filter dialog (Videos) (done)
- UI:
  - popup filter theo source/text/range.
- Logic:
  - popup `Filter Videos` voi cac truong:
    - Source
    - Search Phrase contains
    - Title contains
    - Description contains
  - apply filter dua tren cache row goc (khong mat du lieu).
  - reset filter (dialog reset + menu context `Reset Filters`).
  - button `Filters` o day mo dialog that.
- Test:
  - filter on/off dung so luong row.
- SCR:
  - dialog + truoc/sau filter.

### SV-08 - Search trong table (done)
- UI:
  - popup `Search In Table`:
    - input keyword
    - buttons `Find`, `Prev`, `Next`, `Close`
  - context menu:
    - `Search...`
    - `Clear Search Highlight`
- Logic:
  - tim tren cac cot data (Video ID -> Description).
  - highlight cell match mau vang.
  - next/prev de nhay qua tung ket qua.
- Test:
  - tim title/description keyword.
- SCR:
  - highlight ket qua.

### SV-09 - Auto-fit + Reset columns (done)
- UI:
  - menu item va nut neu can.
- Logic:
  - right-click menu co:
    - `Auto-fit column widths`
    - `Reset column widths`
  - auto-fit: resize theo noi dung hien tai.
  - reset: quay ve mode/width mac dinh cua table.
- Test:
  - width doi dung va reset dung.
- SCR:
  - truoc/sau auto-fit.

## Pha B - Browse/Import mode

### SV-10 - Parse many links (multiline) (done)
- UI:
  - input multiline one-link-per-line.
- Logic:
  - parse, clean, dedupe link.
  - support: `watch`, `youtu.be`, `shorts`, `live`, plain 11-char video ID.
  - `Get Data` import rows vao table ngay lap tuc (metadata placeholder).
- Test:
  - mix link hop le/khong hop le.
  - imported count + skipped invalid count hien ro.
- SCR:
  - input mau + ket qua parse.

### SV-11 - Get Data for imported links (done)
- UI:
  - Get Data co progress/status.
- Logic:
  - fetch metadata theo link.
  - do row realtime.
  - metadata tu YouTube oEmbed (title/channel/thumbnail URL).
  - co `Stop` rieng cho import process.
- Test:
  - 10 links -> hien 10 row.
  - truong hop metadata fail van giu row (fallback title).
- SCR:
  - running + finished states.

### SV-12 - Validation + Error handling (done)
- UI:
  - thong bao loi ro rang.
- Logic:
  - retry nhe.
  - skip row loi khong vo ca batch.
  - import metadata retry 3 lan (backoff ngan).
  - ket thuc import hien summary: invalid links + metadata fail details.
- Test:
  - simulate timeout/invalid URL.
  - truong hop fail metadata: row van duoc giu lai.
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

### SV-16 - Analyze panel UI (done)
- UI:
  - popup `Videos Analyze` khi bam nut Analyze.
  - cards thong ke:
    - Total Videos
    - Avg Title Length
    - Missing Description
  - 2 box chi tiet:
    - Source Ratio
    - Top Repeated Terms (Title)
- Logic:
  - tinh tren dataset hien thi hien tai trong table.
- Test:
  - thay doi data -> chi so doi.
- SCR:
  - panel analyze full.

### SV-17 - Analyze metrics backend (done)
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

## Pha F - Parity nang cao theo nguon moi (Tube Atlas help/video)

### SV-00A - Build feature inventory tu Help index (44 videos)
- Muc tieu:
  - lap bang "feature matrix" doi chieu theo ten video huong dan.
- Dau ra:
  - danh sach: da co / dang lam / chua co.
- Test:
  - moi item co owner step ro rang.

### SV-21 - Video details popup
- UI:
  - popup khi double-click row (hoac menu action).
  - hien title, channel, link, description, thumbnail, metrics co ban.
- Logic:
  - doc du lieu tu row hien tai.
- Test:
  - 5 row bat ky -> popup dung data.

### SV-22 - Filters dialog parity
- UI:
  - clone bo cuc `filters.png`.
- Logic:
  - filter theo source, text, duration/range (neu du lieu co).
  - co preset va reset.
- Test:
  - ket qua filter khop so row.

### SV-23 - Video ads / related actions
- UI:
  - nut/menu lien quan den ads va related.
- Logic:
  - mo URL search/ref theo video hien tai.
- Test:
  - action tao URL dung context.

### SV-24 - Ad-free player popup
- UI:
  - player window theo `video-player-1.png`.
- Logic:
  - embed/open video selected.
- Test:
  - chon row -> player mo dung video.

### SV-25 - Column configuration
- UI:
  - popup chon cot hien/hidden theo `column-configuration-1.png`.
- Logic:
  - apply ngay tren table.
  - luu cau hinh cot theo session.
- Test:
  - restart app -> giu cau hinh (neu da ho tro persistent).

### SV-26 - Download videos queue
- UI:
  - queue jobs + progress.
- Logic:
  - download selected/all.
  - retry + skip loi.
- Test:
  - 10 jobs -> progress dung, file ra dung thu muc.

### SV-27 - Download thumbnails batch
- UI:
  - action download thumbnail selected/all.
- Logic:
  - luu file ten theo video id.
- Test:
  - file image tao dung so luong.

### SV-28 - Analyze titles advanced
- UI:
  - panel thong ke title/chu de.
- Logic:
  - average length, repeated terms, actionable score co ban.
- Test:
  - thay data -> metrics doi dung.

### SV-29 - Video -> Channels handoff
- UI:
  - action send selected/all sang Channels tab.
- Logic:
  - truyen payload channel id/link (neu co).
- Test:
  - channels tab nhan du lieu dung.

### SV-30 - Cross-tool parity review
- Muc tieu:
  - doi chieu lan cuoi voi ref video/help.
- Test:
  - PASS checklist parity theo bang 1.2.

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

## 8.1) Feature matrix mau (dien sau moi step)
| Feature | Ref source | Status | Step owner | Ghi chu |
|---|---|---|---|---|
| Search mode layout | Vimeo screenshot search mode | done/doing/todo | SV-xx | |
| Browse import layout | Vimeo screenshot browse mode | done/doing/todo | SV-xx | |
| Video details popup | `video-details-3.png` | done/doing/todo | SV-21 | |
| Filters dialog | `filters.png` | done/doing/todo | SV-22 | |
| Column config | `column-configuration-1.png` | done/doing/todo | SV-25 | |
| Download videos | `21 tube-atlas-downloading-videos` | done/doing/todo | SV-26 | |
| Download thumbnails | `22 tube-atlas-download-video-thumbnails` | done/doing/todo | SV-27 | |
| Analyze titles | `11 tube-atlas-analyze-titles` | done/doing/todo | SV-28 | |

## 9) Quy dinh truoc khi sang step tiep
- Neu step hien tai chua PASS UI + PASS logic + PASS test + co SCR -> khong qua step moi.
