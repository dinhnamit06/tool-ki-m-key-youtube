# YTB RPM - Thiet Ke Tong Hop

Tai lieu nay la ban thiet ke rieng cho app `TOOL CHECK RPM/ytbrpm.py`.
Muc tieu cua app nay la mo phong va phat trien lai flow `RPM / Niche Finder / Channel insight`
tham chieu tu video NexLev ma khong lam lon logic cua tool YTB chinh.

## 1) Nguon tham chieu
- Video local trong workspace:
  - `Cach su dung Nexlev de check RPM kenh Youtube moi nhat 2024 (SIEU XIN) - YouTube.mp4`
- Video YouTube tham chieu:
  - `https://www.youtube.com/watch?v=XRMTSzl0rxw`
- Frame da tach de quan sat UI:
  - `docs/frames/frame_001.jpg`
  - `docs/frames/frame_002.jpg`
  - `docs/frames/frame_003.jpg`
  - `docs/frames/frame_012.jpg`
  - `docs/frames/frame_013.jpg`

## 2) Huong san pham
- Lam `desktop app` rieng truoc.
- Cau truc phai tach lop:
  - `ui/`
  - `core/`
  - `utils/`
  - `docs/`
- Core phai duoc viet sao cho co the:
  - tach ra sau nay
  - boc lai thanh web app neu can

## 3) Muc tieu V1
- Co `ytbrpm.py` chay duoc.
- Co shell `RPM Finder` theo bo cuc app tham chieu.
- Co `search mode`:
  - `Keyword`
  - `Channel`
- Co `Advanced Filters` popup.
- Co `channel cards` va `detail metrics`.
- Co `filter service` local de chay duoc khong can API that.

## 4) Bo cuc UI da chot cho V1

### 4.1 Sidebar
- logo text
- nhom menu:
  - AI Niche Finder
  - Dashboard
  - Keywords
  - Custom Keywords
  - Channels
  - Saved
  - RPM Predictor
  - NexLev AI

### 4.2 Top Search Bar
- `Keyword / Channel`
- o search
- `Search`
- `Advanced Filters`
- `Reset Filters`
- `Hide Revealed Channels`

### 4.3 Results
- danh sach `ChannelCard`
- card co:
  - title
  - badge `Picked by AI`
  - subscribers
  - avg views per video
  - days since start
  - number of uploads
  - monetized
- expand de hien metric cards:
  - categories
  - total views
  - avg monthly views
  - total revenue generated
  - avg monthly revenue
  - RPM
  - last upload
  - avg monthly upload freq
  - avg video length
  - has shorts

### 4.4 Advanced Filters
- category
- subscriber count
- first upload date
- last upload date
- RPM
- revenue generated
- revenue per month
- total channel views
- views per month
- average views
- median views
- videos uploaded
- uploads per week
- average video length
- monetized
- shorts

## 4.5 Pham vi V1 da chot lai sau khi mo xe ky hon
- V1 chi cover:
  - `AI Niche Finder overview`
  - top search/filter
  - popup advanced filters
  - channel cards + expanded metrics
- V1 KHONG co gang clone ngay:
  - `Channels page` voi filter sidebar co dinh
  - `RPM Predictor` page
  - `NexLev AI`
  - browser auth/session flow

## 4.6 Man hinh future da xac nhan can tach rieng

### Channels page
- layout 2 cot:
  - trai: filter sidebar co dinh + filter template
  - phai: cards/results

### RPM Predictor page
- layout rieng theo channel search
- nhap ten channel
- nut `Get RPM`
- hien output predictor

### NexLev AI page
- chat/query style UI
- go prompt tren scraped data

## 5) Trang thai hien tai
- V1 shell da co.
- Dataset dang la `sample local data`.
- App da duoc refactor thanh `shared shell + sidebar + stacked pages`.
- Da co:
  - `AI Niche Finder overview`
  - `Channels page` voi filter sidebar co dinh
- Chua co:
  - browser login / scraping NexLev
  - template filter
  - rpm predictor page
  - nexlev ai page
  - advanced mode
  - export/import
  - persistence
  - RPM prediction logic rieng

## 6) Nguyen tac ky thuat
- UI va core khong duoc tron file lung tung.
- Filter logic nam trong `core/rpm_service.py`.
- Sample data nam trong `core/rpm_data.py`.
- UI card va popup tach file rieng.
- Tinh nang future:
  - browser automation
  - remote fetch
  - local cache
  - export package

## 7) Huong di tiep
- Lam tung step nho giong tool YTB.
- Sau V1 shell:
  1. `Filter template` UI cho channels page
  2. luu/nap template
  3. sort/ranking controls
  4. `RPM Predictor` page
  5. browser login flow neu can
