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

### Results area
- danh sach cards rong
- moi card co title + badge `Picked by AI`
- metric tong quan tren dong card
- co the expand de xem metric sau

### Advanced Filters popup
- popup trung tam
- chia theo nhieu nhom range
- ton tai:
  - slider/range inputs
  - category select
  - date select
  - radio Yes/No/All

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

## 6) Ket luan
Da du thong tin de bat dau code app desktop V1 dung huong.
Chua du de clone 100% moi chi tiet phu, nen can lam theo step nho va doi chieu them khi can.
