# TubeVibe - Commercial Architecture

Tai lieu nay mo ta huong di lau dai va chuyen nghiep nhat de dua TubeVibe tu app local thanh san pham co the cho thue, update, kiem soat premium va giam rui ro lo logic.

## 1) Muc tieu kinh doanh
- Ban app theo thang/quy/nam.
- Khach chi cai `setup.exe` va dung, khong can biet `main.py`.
- Co the cap nhat version moi ma khong gui source.
- Co the bat/tat premium, khoa tai khoan, khoa version cu.
- Khong luu key AI va secret trong app client.

## 2) Nguyen tac cot loi
- Code chay tren may khach thi khong the giau 100%.
- Cai gi quan trong thi khong duoc tin client.
- App desktop chi nen la UI client + workflow local.
- Logic premium, license, AI key, quota, update policy phai nam tren server.

## 3) Kien truc tong the de xuat

### 3.1 Desktop client
Cong nghe:
- Python + PyQt6
- Build bang Nuitka
- Dong goi installer bang Inno Setup

Vai tro:
- UI cac tab
- table, filter, export/import
- session local
- thumbnail rendering
- local cache nhe
- goi API len server cho cac chuc nang premium

Khong nen giu:
- Gemini/OpenAI key that
- token noi bo
- logic premium cot loi
- logic license duy nhat o local

### 3.2 Backend API
Cong nghe de xuat:
- FastAPI
- PostgreSQL
- Nginx reverse proxy
- HTTPS

Vai tro:
- login
- license check
- subscription / plan
- quota su dung
- AI generation
- update manifest
- remote config
- usage logging
- khoa thiet bi / khoa tai khoan

### 3.3 Database
Bang can co:
- `users`
- `plans`
- `subscriptions`
- `devices`
- `licenses`
- `usage_logs`
- `app_versions`
- `feature_flags`
- `refresh_tokens` neu can login lau dai

## 4) Phan tach logic local va server

### 4.1 Nen de o local
- UI va dieu huong
- cac bang du lieu
- sort/filter/search trong bang
- session save/load
- export CSV/TXT
- cache ket qua da co
- preview hinh, popup, workflow nguoi dung

### 4.2 Nen dua len server
- Gemini title generator premium
- keyword generation premium
- scoring / ranking formula rieng
- goi AI co ton phi
- quota theo user
- check premium
- danh sach feature theo goi
- version policy va force update

## 5) Bai toan build va installer

### 5.1 Tai sao khach khong can `main.py`
- `main.py` chi la entrypoint khi phat trien.
- Sau khi build, khach chi can:
  - `TubeVibe.exe`
  - `TubeVibe_Setup.exe`

### 5.2 Huong build de xuat
- Build bang Nuitka de kho reverse hon PyInstaller.
- Obfuscation la lop phu, khong phai giai phap duy nhat.
- Neu co module rat nhay cam, co the:
  - tach sang API
  - hoac Cython/Nuitka rieng cho module do

### 5.3 Huong dong goi
- Inno Setup tao:
  - shortcut desktop
  - Start Menu shortcut
  - uninstall entry
  - app icon
  - version metadata

## 6) Bai toan update

### 6.1 Cach chuyen nghiep nhat
App mo len se goi API:
- `/app/version`
- `/app/news`
- `/license/check`

Server tra ve:
- latest version
- minimum supported version
- force update hay khong
- download URL
- release note

### 6.2 Hanh vi app
- Neu da moi nhat: cho vao app ngay.
- Neu co ban moi: hien popup update.
- Neu force update: chan dung ban cu.

### 6.3 Giai doan dau nen lam
- Chi can popup bao co ban moi + nut mo trang tai installer.
- Chua can auto-download installer ngay.

## 7) Bai toan license va premium

### 7.1 Nhung cach yeu neu chi lam local
- check file local `license.json`
- check bien `is_premium`
- an/hien button premium

Cac cach tren deu de bi bypass.

### 7.2 Huong dung
- User login tai khoan.
- App gui:
  - account
  - device id
  - app version
- Server tra ve:
  - plan
  - feature duoc phep dung
  - expiration
  - force update status

### 7.3 Device binding
Nen lam nhe:
- moi tai khoan duoc 1-3 may tuy goi
- doi may qua dashboard/admin
- khong khoa qua gac gay phan user that

## 8) Bao mat thuc te

### 8.1 Nen lam
- khong hardcode API key trong app
- build bang Nuitka
- tach premium logic len server
- check online dinh ky
- remote disable account
- version gate
- log usage co muc do

### 8.2 Khong nen ky vong sai
- installer khong dong nghia voi an duoc code 100%
- obfuscation khong the thay the backend
- client-side premium check khong du an toan

## 9) Kien truc thu muc de xuat cho source

```text
tool ytb/
  main.py
  ui/
    main_window.py
    keywords_tab.py
    trends_tab.py
    videos_tab.py
    ...
  core/
    videos_fetcher.py
    trends_fetcher.py
    ...
  services/
    auth_service.py
    license_service.py
    update_service.py
    api_client.py
  utils/
    config.py
    session_store.py
    constants.py
    logging_setup.py
  generated/
  build/
  installer/
```

Ghi chu:
- `main.py` phai mong, chi bootstrap.
- `services/` nen sinh ra khi bat dau lam backend integration.

## 10) Luong su dung chuyen nghiep cho khach

1. Khach tai `TubeVibe_Setup.exe`
2. Cai dat
3. Mo app
4. Dang nhap
5. App check version + license
6. Server tra ve feature duoc phep
7. User dung app
8. App goi API cho tinh nang premium

## 11) Lo trinh thuc hien de xuat

### Phase 1 - Hoan thien local product
- Lam xong UI/logic cac tab chinh
- Save session
- Export/import
- Build workflow on dinh

### Phase 2 - Chuan hoa source
- `main.py` bootstrap-only
- tach ro `ui / core / services / utils`
- logging
- error handling
- config runtime

### Phase 3 - Build thuong mai
- script build Nuitka
- script tao installer Inno Setup
- icon, version, shortcut

### Phase 4 - Update infrastructure
- them app version
- API version manifest
- popup update
- force update neu can

### Phase 5 - License infrastructure
- login
- check plan
- device binding
- han dung

### Phase 6 - Premium migration
- chuyen AI / key / quota sang server
- cac tinh nang premium goi API

## 12) Thu tu uu tien thuc te cho TubeVibe
- Uu tien 1: hoan thien tab local
- Uu tien 2: build `.exe` va `setup.exe`
- Uu tien 3: them update checker
- Uu tien 4: them login/license
- Uu tien 5: day AI va premium logic len server

Ly do:
- Neu nhay vao backend qua som, san pham local chua on dinh thi se ton cong gap doi.

## 13) Ket luan
Huong lau dai va chuyen nghiep nhat cho TubeVibe la:

- Desktop app PyQt6 de lam client
- Build bang Nuitka
- Installer bang Inno Setup
- Update bang version API
- License va premium check online
- Secret va logic premium dat tren backend FastAPI

Day la huong co the:
- ban duoc
- update duoc
- khoa premium duoc
- scale duoc
- giam rui ro lo logic hon so voi app local thuần
