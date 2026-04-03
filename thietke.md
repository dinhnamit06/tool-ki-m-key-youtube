# TubeVibe - Thiet Ke Tong Hop (UI + Chuc Nang + Step)

Tai lieu nay gom cac diem da phan tich va roadmap chi tiet de code tung buoc, tranh sot chuc nang.
Tai lieu chi tiet rieng cho tab Videos nam o: `stepvideotab.md`.

## 1) Nguon tham chieu
- Tube Atlas website: https://tubeatlas.com.vn/
- Video tham chieu 1: https://www.youtube.com/watch?v=sAiYwVGZ6JI&t=1471s
- Video tham chieu 2: https://www.youtube.com/watch?v=bNQd7nw2Zw0

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

## V4 - Browse/Import mode: nhap link va get data (P1)
- UI:
  - o nhap links (moi dong 1 link),
  - nut Get Data.
- Logic:
  - parse link YouTube hop le,
  - lay metadata co ban cho tung link.
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
- Xong step hien tai moi goi y step tiep theo.
- Neu can anh UI bo sung, yeu cau user gui them ngay trong step do.

## 6) Dinh nghia Done cho Videos tab
- Luong Search, Browse/Import, Analyze chay on dinh.
- Bang cap nhat realtime.
- Context menu du backend chinh.
- Filter/Search/Auto-fit/Export dung.
- UI dong bo va de dung giong huong Tube Atlas.
