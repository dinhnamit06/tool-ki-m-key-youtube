# Phan Tich Video NexLev RPM

Tai lieu nay tom tat nhung gi da boc tach duoc tu video tham chieu va file video local.

## 1) Ban chat san pham
Day khong phai mot man "check RPM" don le.
No la mot flow rong hon:
- tim niche / channel
- loc bang metric
- xem channel cards
- xem RPM, revenue, monthly views
- danh gia kha nang kiem tien

## 2) Thanh phan UI chinh

### Sidebar
- logo NexLev
- menu cong cu
- muc active: `AI Niche Finder`

### Search + search mode
- combobox `Keyword / Channel`
- search text box
- ket hop voi `Advanced Filters`
- co auto-suggestion dropdown khi go tu khoa
- mode `Channel` va `Keyword` xuat hien o nhieu man khac nhau

### Results area
- danh sach cards rong
- moi card co title + badge `Picked by AI`
- metric tong quan tren dong card
- co the expand de xem metric sau
- co icon/hanh dong o ben phai card
- co trang thai `revealed / unrevealed`

### Advanced Filters popup
- popup trung tam
- chia theo nhieu nhom range
- ton tai:
  - slider/range inputs
  - category select
  - date select
  - radio Yes/No/All

## 2.1) Cac man hinh lon da xac nhan tu video

### A. AI Niche Finder overview
- day la man hien tai da du thong tin de lam `V1 shell`
- hien danh sach channel cards
- filter nhanh tren top bar
- `Advanced Filters` mo popup

### B. Channels page co filter sidebar co dinh
- day la man khac voi overview page
- ben trai la filter sidebar co dinh, khong phai popup:
  - `Filter template`
  - `Apply`
  - category
  - subscriber count
  - first/last upload date
  - RPM
  - revenue generated
  - revenue per month
  - total channel views
  - views per month
- ben phai la channel detail cards mo rong san
- co nghia la ve sau app can it nhat 2 layout:
  - overview page
  - channels page

### C. RPM Predictor page
- co trang rieng `RPM Predictor`
- top bar:
  - mode `Channel`
  - input `Search a channel...`
- khu giua:
  - title `RPM Predictor`
  - subtitle `AI Powered RPM Predictor`
  - o nhap va nut `Get RPM`
- day la flow khac voi `Niche Finder`, khong nen nhet chung mot widget don gian

### D. NexLev AI page
- co page hoi dap / prompt query tren scraped data
- co cac suggestion san:
  - average view count > 10,000
  - total revenue generated > $50,000
  - keywords co RPM > 7$
  - channels < 200,000 subscribers
- day khong phai RPM checker cot loi, nhung la clue de thiet ke future `AI query layer`

## 3) Du lieu cot loi can model hoa
- title
- category
- subscribers
- avg views per video
- days since start
- upload count
- monetized
- total views
- avg monthly views
- total revenue generated
- avg monthly revenue
- rpm
- last upload days ago
- avg monthly upload frequency
- avg video length
- has shorts
- first upload date
- last upload date
- median views
- uploads per week
- picked by ai
- revealed
- keywords

## 3.1) Du lieu / hanh vi bo sung da nhan dien
- `filter template` la first-class feature, khong phai chi la shortcut nho
- `revealed channels` can co state luu lai de filter an/hien
- card detail co xu huong hien:
  - category
  - total views
  - avg monthly views
  - total revenue generated
  - avg monthly revenue
  - rpm
  - last upload
  - avg monthly upload freq
  - avg video length
  - has shorts
  - most popular videos
- co flow tu channel card -> mo channel YouTube that de check tay
- co flow tu prompt tieng tu nhien -> query tren data channel

## 4) Ky thuat phu hop cho app desktop
- PyQt la hop ly de:
  - lam card list
  - popup filter phuc tap
  - browser shell neu can
  - export/import local

## 5) Cac diem chua xac thuc 100%
- logic template filter that cua NexLev
- exact ranking heuristics
- cache/session/backend calls that
- browser auth flow chi tiet
- exact schema cua `RPM Predictor` output page
- exact data path giua `NexLev AI` va `Channels`

## 6) Ket luan
Da du thong tin de bat dau code app desktop V1 dung huong.
Chua du de clone 100% moi chi tiet phu, nen can lam theo step nho va doi chieu them khi can.

## 7) Ket luan cap nhat sau lan mo xe thu 2
- `V1 shell` hien tai dang cover dung nhat cho man `AI Niche Finder overview`.
- `V2` can them `Channels page` rieng voi filter sidebar co dinh.
- `V3` moi nen tach them `RPM Predictor`.
- `NexLev AI` de sau, vi no la layer hoi dap tren data da scrape.
