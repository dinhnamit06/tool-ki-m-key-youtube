# TubeVibe - Thiet Ke Tong Hop (UI + Chuc Nang + Step)

Tai lieu nay gom cac diem da phan tich va roadmap chi tiet de code tung buoc, tranh sot chuc nang.
Tai lieu chi tiet rieng cho tab Videos nam o: `stepvideotab.md`.

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
