# TubeVibe - Thiet Ke Tong Hop (UI + Chuc Nang + Step)

Tai lieu nay gom cac diem da phan tich va roadmap chi tiet de code tung buoc, tranh sot chuc nang.
Tai lieu chi tiet rieng cho tab Videos nam o: `stepvideotab.md`.
Tai lieu kien truc thuong mai nam o: `commercial_architecture.md`.

## 1) Nguon tham chieu
- Tube Atlas website: https://tubeatlas.com.vn/
- Video tham chieu 1: https://www.youtube.com/watch?v=sAiYwVGZ6JI&t=1471s
- Video tham chieu 2: https://www.youtube.com/watch?v=bNQd7nw2Zw0
- AppBreed Help Videos (index): https://appbreed.com/help-videos-tube-atlas/

## 1.1) URL da xac thuc cho Videos tab (cap nhat 2026-04-03)
- 21 tube-atlas-downloading-videos:
  - https://vimeo.com/702556179
  - https://i.vimeocdn.com/video/1419479118-653fc1fd9439e3fbd46498d98bd45d56e7ba435a01aacd46170b5fb507f5acf6-d?f=webp&region=us
- 22 tube-atlas-download-video-thumbnails:
  - https://vimeo.com/702556184
  - https://i.vimeocdn.com/video/1419479186-9937920e53d5698ed5cad3dfdd7ddee891c55c1f31ffba91f578a0e584abf678-d?f=webp&region=us
- 11 tube-atlas-analyze-titles:
  - https://vimeo.com/702556396
  - https://i.vimeocdn.com/video/1419482754-bb31964c8b3aaab73aa5d26199571a64f229ac20c5b58d752d49519b04578d26-d?f=webp&region=us
- 14 tube-atlas-channels-tool:
  - https://vimeo.com/702556438
  - https://i.vimeocdn.com/video/1419479541-c102fc34657d580c8c162cdddce077df29d3b3660e134e5f1dc20badc397beec-d?f=webp&region=us
- Tube Atlas Trends tool:
  - https://vimeo.com/713284733
  - https://i.vimeocdn.com/video/1437975831-8b21be6421c8259ddcf759340dfbd3fcc4937625d3f6f2a822e967bee606e9f8-d?f=webp&region=us
- Videos tool (Search mode tham chieu):
  - https://vimeo.com/702556377
  - https://i.vimeocdn.com/video/1419479442-225a8d75a5e147046b24d5bc42809210458338bcd247dea80cb1cf123f1ee77a-d?f=webp&region=us
- Videos tool (Browse or Import mode tham chieu):
  - https://vimeo.com/702556409
  - https://i.vimeocdn.com/video/1419479539-3c164ccfe087f1be85cbd5ec0fae467bf23701d86c19d625b4c3fc5b5ac9646b-d?f=webp&region=us
- Filters UI tham chieu:
  - https://vimeo.com/702556224
  - https://i.vimeocdn.com/video/1419479192-db34db2e3e910198fb9dcdac6e57b46ab93d46bb439e82ce8ccb899a892b9fbb-d?f=webp&region=us
- Video ads / related tham chieu:
  - https://vimeo.com/726146748
  - https://vimeo.com/726146770
- Ad-free player tham chieu:
  - https://vimeo.com/747379514
  - https://i.vimeocdn.com/video/1503065816-3b5ae9b61c7e25195977288af161da6e1a824e3f395603b3a9af5f99e19cb35e-d?f=webp&region=us
- Column configuration tham chieu:
  - https://vimeo.com/747379500
  - https://i.vimeocdn.com/video/1503065455-3fe45b8d3876b97ac54b35253cc678ddbe71d087e570ce848ce079bf022daf2b-d?f=webp&region=us

## 2) Nguyen tac UI thong nhat
- Nen den -> chu trang.
- Nen trang -> chu den.
- Link giu mau xanh (de phan biet co the click).
- Nut hanh dong chinh dung do `#e50914`.
- Do rong cot bang phai hop ly, khong bat buoc keo tay.
- Moi popup/settings dung style dong bo voi app.

## 3) Trang thai hien tai

### 3.1 Keywords tab
- Da co generate keyword bang Gemini.
- Da bo sung prompt theo huong niche YouTube tot hon:
  - intent mix (awareness/consideration/action),
  - evergreen + trend,
  - long-tail, tranh generic.
- Da bo sung parser output on dinh hon (xu ly newline/comma/bullet/numbering, dedupe, fallback).

### 3.2 Trends tab
- Da co mini chart trong cot Chart.
- Double click cot Chart -> popup bieu do chi tiet.
- Da co settings popup.
- Da co context menu va mot phan backend.
- Da co mode mo external browser tuan tu theo keyword.
- Da co filter co ban (theo user xac nhan).

### 3.3 Videos tab
- Da co khung UI co ban (Search / Browse or Import / Analyze).
- Da cap nhat Step V2:
  - dong bo mau nen/chu theo rule tren,
  - nut do thong nhat,
  - input/combo nen trang chu den,
  - panel videos style dong bo hon.

### 3.4 Channels tab
- Da co 2 luong rieng:
  - `Search`
  - `Browse or Import`
- Da co enrich metadata va giam manh `not-given`.
- Da co:
  - File / Filters / Clear
  - right-click menu
  - Preview HTML Table / HTML Feed
  - Copy / Delete / Checkboxes / Search / Channels tool
- Da harden cho case nhieu row, rebuild, stale worker update.

### 3.5 Video to Text tab
- Da doi UI theo layout Tube Atlas:
  - 1 dong input `Video link or ID`
  - `Convert to Text`
  - `Auto Punctuate`
  - `See Video`
  - `Wrap lines`
  - editor transcript full trang
  - thanh duoi `Content Spinner / Replace / File / Copy / Clear`
- Da co backend `Convert to Text` cho YouTube:
  - nhan link / `watch?v=` / video ID / `href=...`
  - lay subtitle / auto-captions
  - do transcript goc vao editor
- Da co backend `Auto Punctuate` rule-based.
- Kien truc da chot:
  - `Convert to Text` = xuat transcript goc
  - `Auto Punctuate` = lam transcript de doc hon

### 3.6 Text to Video tab
### 3.7 Comments tab
- Da co UI shell theo layout Tube Atlas:
  - Video link or ID
  - 1. Load Video
  - Step 2 / Page scrolls / 2. Scroll & Extract
  - panel Loaded Video
  - bang comment voi cac cot chinh
  - nut duoi: Extract Comments, Start Autoscroll, File, Analyze, Filters, Clear
- Da co backend `1. Load Video`:
  - normalize video link / ID
  - worker nen lay metadata video that
  - load video vao panel browser ben trai
  - cleanup an toan khi `Clear` / `shutdown`
- Da co backend `2. Scroll & Extract`:
  - DOM scrape comment truc tiep tu embedded browser
  - `Extract Comments` = scrape comment hien co tren trang
  - `2. Scroll & Extract` = cuon theo so `Page scrolls` va gom comment
  - `Start Autoscroll` = cuon va extract lien tuc cho den khi dung
  - merge comment theo key de tranh duplicate
  - cleanup an toan khi load video moi / clear / shutdown
- Da co backend cho nut duoi:
  - `File`: export CSV/TXT, copy rows, copy comments
  - `Analyze`: popup `Analyze Comments`, stop words, generate word stats, `View Comments` HTML, profanity list
  - `Filters`: commenter / posted / has question / has profanity
  - `Clear`: reset video, comment rows, filter state
- Da co backend co ban cho `right-click`:
  - `Comments tool`
  - `Checkboxes`
  - `Filters`
  - `Copy`
  - `Search`
  - `Auto-fit column widths`
  - `Reset column widths`
  - `Delete`
- Da giu tuong thich voi luong send du lieu tu Videos va Channels.
- Da co `TTV-01` UI shell:
  - project header
  - source script panel
  - scene workflow panel
  - prompt workspace
  - generation panel
  - preview panel
- Da co `TTV-02` Scene List UI:
  - them/xoa/duplicate/reorder scene
  - scene inspector
- Da co `TTV-03` backend tao `Scene Plan` tu:
  - script thuong
  - output `Extract Structure`
- Da chot huong:
  - day se la noi xu ly `scene plan`, `prompt generation`, `Veo`, `batch clip generation`
  - khong nhung Veo vao `Video to Text`

## 4) Roadmap Videos tab (lam tung step nho)

## V1 - Khung UI (done)
- Muc tieu: co bo cuc tab Videos, cot bang, thanh duoi, mode button.
- Kiem thu: vao tab Videos thay day du thanh phan UI.

## V2 - Theme/UI dong bo (done)
- Muc tieu: dung rule mau nen/chu thong nhat.
- Kiem thu:
  - nen den chu trang,
  - nen trang chu den,
  - link mau xanh.

## V3 - Search mode: lay danh sach video co ban (P1) (done)
- UI:
  - nut Search su dung du lieu tu `Search Phrase`,
  - status message ro rang.
- Logic:
  - tim kiem YouTube theo tu khoa,
  - do du lieu vao bang ngay khi co ket qua.
- Da implement:
  - chay thread nen (UI khong bi dung),
  - them row realtime vao table,
  - co nut Stop de dung qua trinh,
  - cap nhat Total Items/Selected rows ngay khi co row moi.
- Cot du lieu toi thieu:
  - checkbox, image placeholder, video id, video link, source, search phrase, title, description.
- Kiem thu:
  - nhap 1 phrase -> co dong ket qua trong bang,
  - Total Items cap nhat dung.

## V4 - Browse/Import mode: nhap link va get data (P1) (done)
- UI:
  - o nhap links (moi dong 1 link),
  - nut Get Data.
- Logic:
  - parse link YouTube hop le,
  - lay metadata co ban cho tung link (oEmbed),
  - do row realtime khong block UI,
  - co stop import.
- Kiem thu:
  - paste 3-5 link -> bang them dong dung thu tu,
  - link loi duoc bo qua co thong bao.

## V5 - Right-click menu cho Videos table (P1)
- UI menu:
  - Copy (selected/all),
  - Auto-fit columns,
  - Reset columns,
  - Delete selected,
  - Search nhanh (Google/YouTube).
- Logic:
  - selected row dung theo checkbox + selected rows.
- Kiem thu:
  - copy dung noi dung,
  - delete xong cap nhat Total Items.

## V5A - Trending Videos backend (P1)
- UI:
  - nut Trending Videos hoat dong that.
- Logic:
  - nap du lieu trending vao table.
- Kiem thu:
  - bam nut -> table co ket qua.

## V6 - Filter + Search trong bang (P1)
- UI:
  - dialog Filter,
  - dialog Search (keyword trong title/description).
- Logic:
  - loc theo source/text,
  - highlight ket qua search.
- Kiem thu:
  - filter on/off ngay,
  - reset filter tro ve full data.

## V7 - Auto-fit va luu kich thuoc cot (P2)
- Chuc nang:
  - auto-fit all columns,
  - reset default width,
  - optional nho width theo session.
- Kiem thu:
  - bang de doc khong tran chu qua nhieu.

## V8 - Export/File actions (P2)
- Chuc nang:
  - Save CSV / Excel / TXT,
  - copy all keywords/video links.
- Kiem thu:
  - file xuat dung cot va so dong.

## V9 - Analyze mode (P2)
- UI:
  - panel thong ke nhanh (so luong video, avg title length, etc.).
- Logic:
  - tinh metrics tu data da co trong table.
- Kiem thu:
  - so lieu doi theo data input.

## V10 - Performance + stability (P1)
- Chuc nang:
  - xu ly theo batch nho,
  - cap nhat row realtime,
  - UI khong bi tre.
- Kiem thu:
  - 50-100 rows van thao tac duoc.

## V11 - Error handling (P1)
- Chuc nang:
  - thong bao loi ro rang,
  - retry nhe cho request fail tam thoi.
- Kiem thu:
  - mo phong loi mang -> app khong vo.

## V12 - Polish final (P2)
- Chinh spacing/icon/chu/tooltip.
- Chot hanh vi context menu + keyboard shortcut can thiet.
- Kiem thu regression nhanh toan tab.

## 4.1) Roadmap Video to Text tab (lam tung step nho)

## VTT-01 - UI shell Tube Atlas (done)
- Muc tieu:
  - 1 dong input `Video link or ID`
  - 3 nut chinh `Convert to Text`, `Auto Punctuate`, `See Video`
  - `Wrap lines`
  - editor transcript full trang
  - thanh duoi:
    - trai: `Content Spinner`, `Replace`
    - giua: `Content: X Lines | Y Words | Z Characters`
    - phai: `File`, `Copy`, `Clear`
- Test:
  - layout giong ref, chu de doc, editor nen trang chu den.

## VTT-02 - Convert to Text backend (done)
- Muc tieu:
  - nhan YouTube link / ID
  - lay transcript tu subtitle hoac auto-caption
  - do transcript goc vao editor
- Rule:
  - khong lam dep transcript o step nay
  - uu tien dung, day du va on dinh
- Test:
  - full link, `watch?v=...`, video ID, `href="..."`
  - transcript hien len editor

## VTT-03 - Auto Punctuate rule-based (done)
- Muc tieu:
  - local formatting khong dung AI
  - sua spacing / viet hoa / them dau cau / chia doan hop ly hon
- Rule:
  - `Convert to Text` giu transcript goc
  - `Auto Punctuate` moi lam dep transcript
- Ghi chu:
  - da bo sung lua chon `AI Enhanced (Gemini)` tren cung nut `Auto Punctuate`
- Test:
  - transcript truoc/sau co khac biet
  - noi dung khong bi mat

## VTT-04 - File menu UI (done)
- Muc tieu:
  - menu `File` co:
    - Save TXT
    - Load TXT
    - Export cleaned text
    - Save copy
- Test:
  - mo menu dung layout

## VTT-05 - File menu backend (done)
- Muc tieu:
  - luu/noi transcript va transcript cleaned
- Test:
  - luu file va mo lai dung noi dung

## VTT-06 - Replace UI (done)
- Muc tieu:
  - popup `Find / Replace`
- Test:
  - popup mo dung layout

## VTT-07 - Replace backend (done)
- Muc tieu:
  - find next
  - replace current
  - replace all
- Test:
  - replace dung so lan

## VTT-08 - Content Spinner UI (done)
- Muc tieu:
  - popup chon mode spin
  - basic / ai enhanced (de sau)
- Test:
  - popup mo dung layout

## VTT-09 - Content Spinner backend basic (done)
- Muc tieu:
  - spin nhe o muc sentence/phrase
  - khong dung AI truoc
- Test:
  - output thay doi nhung van giu nghia tuong doi

## VTT-10 - Clean Script UI (done)
- Muc tieu:
  - them nut/popup `Clean Script`
- Test:
  - popup options ro rang

## VTT-11 - Clean Script backend (done)
- Muc tieu:
  - bo filler, noise, caption rac, lap
  - giu script sach hon cho cac buoc sau
- Test:
  - transcript sach hon ro rang

## VTT-12 - Summarize UI (done)
- Muc tieu:
  - popup/chon mode summary
- Test:
  - UI ro rang, co output area

## VTT-13 - Summarize backend (done)
- Muc tieu:
  - short summary
  - bullet summary
  - key takeaways
- Test:
  - output dung theo mode

## VTT-14 - Extract Structure UI (done)
- Muc tieu:
  - UI de hien:
    - hook
    - intro
    - main points
    - CTA
- Test:
  - layout de doc

## VTT-15 - Extract Structure backend (done)
- Muc tieu:
  - rut cau truc tu transcript
  - `AI Enhanced (Gemini)` da duoc noi vao mode Extract Structure, co fallback local
- Test:
  - output co logic video ro rang

## VTT-16 - Rewrite Similar Script UI (done)
- Muc tieu:
  - popup/options de viet lai script tu transcript goc
- Test:
  - UI co mode va output area

## VTT-17 - Rewrite Similar Script backend (done)
- Muc tieu:
  - viet script moi cung logic, khong copy tho
- Test:
  - output khac wording nhung giu flow

## VTT-H1 - Hardening pass (done)
- Muc tieu:
  - khong de `Extract Structure` va `Rewrite Similar Script` khoa UI khi goi AI
  - khong de worker song sot khi dong dialog, clear output, convert moi, hoac tat app
  - giu fallback local neu AI loi
- Da lam:
  - tach `AI Extract Structure` sang worker nen
  - tach `AI Rewrite Similar Script` sang worker nen
  - bo sung quan ly background workers o tab `Video to Text`
  - `Clear`, `Convert to Text`, `shutdown()` deu request stop cac worker AI dang chay
  - neu AI loi thi:
    - `Extract Structure` fallback local `Detailed`
    - `Rewrite Similar Script` fallback local rewrite
- Test:
  - AI success
  - AI fail -> local fallback
  - `Clear` trong luc worker dang chay
  - `shutdown()` trong luc worker dang chay

## 4.2) Roadmap Text to Video tab (de rieng, lam sau)

## TTV-01 - UI shell Text to Video (done)
- Muc tieu:
  - project layout rieng cho scene-based workflow
- Da co:
  - `Project Name`
  - `Load Script`
  - `Create Scene Plan`
  - `Generate Prompts`
  - `Veo Settings`
  - `Render Project`
  - `Source Script`
  - `Scene Workflow`
  - `Prompt Workspace`
  - `Generation`
  - `Preview`
- Test:
  - tab mount vao navbar chinh
  - shell render on dinh, chua co backend scene/Veo

## TTV-02 - Scene List UI (done)
- Muc tieu:
  - list cac scene voi duration, prompt, note
- Da co:
  - toolbar `Add Scene / Duplicate / Remove / Move Up / Move Down`
  - bang scene 7 cot:
    - `Scene`
    - `Scene Title`
    - `Duration`
    - `Visual Goal`
    - `Voiceover`
    - `Status`
    - `Clip`
  - scene inspector co:
    - `Selected scene`
    - `Shot Type`
    - `Scene Notes`
  - thao tac UI cuc bo:
    - them row
    - duplicate row
    - xoa row
    - doi thu tu row
    - cap nhat scene count / selected count
- Test:
  - them/xoa/duplicate/reorder scene trong bang khong loi
  - row selected cap nhat inspector dung

## TTV-03 - Backend tao Scene Plan tu script (done)
- Muc tieu:
  - tach script thanh cac scene co logic
- Da co:
  - nhan `Source Script` hien tai va tao scene plan that
  - uu tien script co heading:
    - `Hook`
    - `Intro`
    - `Main Points`
    - `CTA`
  - neu la script thuong:
    - uu tien tach theo paragraph
    - fallback sang structure extractor local
  - tu dong do lai bang scene:
    - `Scene Title`
    - `Duration`
    - `Visual Goal`
    - `Voiceover`
    - `Status`
    - `Clip`
  - cap nhat `Prompt Workspace` va `Preview` o muc tom tat scene plan
- Test:
  - script thuong tao duoc scene plan
  - script tu `Extract Structure` tao duoc hook / intro / main points / cta thanh scene rows

## TTV-04 - Prompt Editor UI (done)
- Muc tieu:
  - edit prompt cho tung scene
- Da co:
  - `Selected prompt scene`
  - `Prompt Format`
    - `Scene Prompt`
    - `Detailed Prompt`
    - `Veo Prompt`
  - prompt editor co the sua tay cho row dang chon
  - `Apply to Selected Scene`
  - `Reset Prompt`
  - `Copy Prompt`
  - prompt draft local duoc giu theo tung row
- Test:
  - doi scene -> prompt draft doi theo
  - reset prompt -> quay ve template
  - duplicate / move row khong lam mat prompt draft da save

## TTV-05 - Backend Generate Scene Prompts (done)
- Muc tieu:
  - prompt generation tu script/scene
- Da co:
  - nut `Generate Prompts` chay that
  - serialize toan bo scene hien co trong bang
  - goi Gemini mot lan cho ca batch scene
  - luu `prompt_draft` vao tung row
  - fallback local prompt template neu Gemini loi
  - co worker nen + cleanup khi `Clear` / `shutdown`
- Test:
  - local prompt fallback sinh prompt cho tung scene
  - prompt draft duoc luu vao row meta
  - `Clear` reset state va khong de worker cu de lai status/prompt

## TTV-06 - Veo Settings UI (done)
- Muc tieu:
  - model, duration, aspect ratio, quality
- Da co:
  - popup `Veo Settings`
  - state luu rieng cho project:
    - model
    - clip duration
    - aspect ratio
    - resolution
    - variants
    - quality
    - native audio
    - scene prompt usage
    - voiceover guidance
    - negative prompt
  - `Save`
  - `Reset Defaults`
  - `Close`
- Ghi chu:
  - hien tai chi la UI + luu state
  - chua goi Veo backend

## TTV-07 - Backend Generate Single Scene (done)
- Muc tieu:
  - goi Veo cho 1 scene
- Da co:
  - `Generate One` dung scene dang chon
  - lay `prompt_draft` hoac Veo template de tao request
  - goi Gemini Veo qua REST `predictLongRunning`
  - poll operation den khi xong
  - download clip `.mp4` ve `generated/text_to_video/...`
  - cap nhat row:
    - `Status`
    - `Clip`
  - luu metadata:
    - `clip_path`
    - `veo_operation_name`
    - `veo_video_uri`
- Ghi chu:
  - neu setting duration khong hop le cho model/hinh do, app se tu clamp ve gia tri Veo ho tro

## TTV-08 - Backend Batch Generate Scenes (done)
- Muc tieu:
  - render nhieu scene lien tiep
- Da co:
  - `Generate All` chay tuan tu tung scene
  - reuse chung backend Veo cua `Generate One`
  - queue dua tren `scene_no`, khong dua tren `row index`
  - co the `Clear`/shutdown trong luc batch dang chay
  - neu gap loi quota/rate-limit/billing thi dung batch som
  - cuoi batch co summary:
    - so scene thanh cong
    - so scene loi

## TTV-09 - Clip Manager UI (done)
- Muc tieu:
  - quan ly clip da tao
- Da co:
  - popup `Clip Manager`
  - bang clip rows theo tung scene:
    - scene
    - title
    - status
    - clip file
    - model
    - output
  - preview metadata clip:
    - clip path
    - model
    - operation
    - video uri
  - nut:
    - `Refresh`
    - `Open Clip`
    - `Open Folder`
    - `Close`
- Ghi chu:
  - hien tai `Open Clip` va `Open Folder` moi la UI placeholder

## TTV-10 - Export Project Package (done)
- Muc tieu:
  - xuat:
    - script
    - prompts
    - shot list
    - metadata
- Da co:
  - `Export Package` xuat project thanh thu muc bundle
  - xuat:
    - `source_script.txt`
    - `scene_plan.json`
    - `scene_plan.txt`
    - `prompt_drafts.json`
    - `prompt_drafts.txt`
    - `clip_manifest.json`
    - `veo_settings.json`
    - `project_manifest.json`
  - tu dong copy cac clip da generate vao thu muc `clips/` neu file con ton tai


## TTV-11 - Browser Fallback UI (done)
- Muc tieu:
  - co luong tay khi Veo API het quota hoac tam thoi khong dung duoc
- Da co:
  - nut Browser Fallback trong khung Generation
  - popup Browser Fallback Queue
  - queue scene theo tung row:
    - Scene
    - Title
    - Status
    - Prompt
  - preview prompt va voiceover cua scene dang chon
  - nut:
    - Copy Prompt
    - Copy Voiceover
    - Open Browser Flow
    - Mark Pending
    - Import Clip
    - Next Scene
    - Close
- Ghi chu:
  - step nay la UI-first cho luong fallback qua browser
  - Copy Prompt va Copy Voiceover da chay that
  - Open Browser Flow, Mark Pending, Import Clip se duoc noi backend o step sau

## TTV-PAUSE - Tam dung Text to Video (note)
- Ngay note: 2026-04-07
- User yeu cau tam thoi bo qua tab `Text to Video`.
- Khong tiep tuc cac step cua `Text to Video` cho den khi:
  - tat ca cong viec cua tab khac da xong, hoac
  - user noi ro quay lai tab nay.
- Step pending tiep theo khi quay lai:
  - backend `Open Browser Flow`

## 4.3) Cau noi Video to Text -> Text to Video
- Bridge-01:
  - `Send Clean Script to Text to Video`
- Bridge-02:
  - `Extract Structure -> auto-fill Scene Plan`
- Bridge-03:
  - `Rewrite Similar Script -> Generate Scene Prompts`
- Nguyen tac:
  - `Video to Text` chi xu ly transcript/script
  - `Text to Video` moi xu ly Veo, scene, prompt, generation

## 5) Quy tac lam viec tiep theo (bat buoc)
- Chi lam tung step nho.
- Moi step phai co:
  1) UI,
  2) Logic,
  3) Test.
- Quy tac phoi hop (cap nhat 2026-04-03):
  - Lam UI truoc.
  - Xong UI phai dung lai, bao user review/xac nhan.
  - Chi lam backend sau khi user dong y qua step backend.
  - Chi duoc gop UI+backend trong 1 step khi user yeu cau ro rang hoac feature khong the tach.
- Xong step hien tai moi goi y step tiep theo.
- Neu can anh UI bo sung, yeu cau user gui them ngay trong step do.

## 6) Dinh nghia Done cho Videos tab
- Luong Search, Browse/Import, Analyze chay on dinh.
- Bang cap nhat realtime.
- Context menu du backend chinh.
- Filter/Search/Auto-fit/Export dung.
- UI dong bo va de dung giong huong Tube Atlas.

## 7) Dinh nghia Done cho Video to Text tab
- `Convert to Text` xuat transcript goc on dinh.
- `Auto Punctuate` co rule-based va de nang cap AI sau.
- `File`, `Replace`, `Content Spinner` co UI + backend co ban.
- Co the dung tab nay de:
  - doc transcript
  - clean script
  - summarize
  - extract structure
  - rewrite similar script

## 8) Dinh nghia Done cho Text to Video tab
- Co scene workflow rieng.
- Co prompt generation.
- Co Veo settings + generate clips.
- Co duong dan nhan script tu `Video to Text`.



