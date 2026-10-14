# 健身日記

每天記錄訓練的手機 App。用 Next.js 寫，可以當網頁（PWA）用，也用 Capacitor 包成 Android / iOS App。

- **預設腿 → 拉 → 推循環**：依上一次的訓練自動判斷「今天該練什麼」，新紀錄會預選建議部位
- **沒練就是休息**：當天沒記錄，隔天起自動算成休息日（今天還沒過完不算）；也可以手動按「休息」
- **今天做了什麼**：勾選部位＋寫下動作、重量、組數
- **今日照片**：拍照或從相簿選，自動壓縮後存在手機上
- **AI 判斷**：把照片＋備註交給 Claude，判斷今天練的是腿／拉／推，並給一句建議，可一鍵套用
- **備份到手機**：把紀錄＋照片打包成一個 `.json` 檔，存到手機的「檔案」或「下載」，換手機時用「從備份還原」

## 開發

```bash
pnpm install
cp .env.example .env.local   # 填入 ANTHROPIC_API_KEY（只有 AI 判斷需要）
pnpm dev
```

部署到 Vercel 時，在專案的 Environment Variables 加上 `ANTHROPIC_API_KEY`。

## 手機 App（Capacitor）

### Android：直接下載 APK

1. 到 GitHub repo 的 **Actions** 分頁 → **Android APK** → 點最新一次成功的執行
2. 下載最下方的 artifact `fitness-log-apk`（zip，解開是 `app-debug.apk`）
3. 傳到手機安裝（第一次要允許「安裝不明來源的應用程式」）

每次 push 都會自動重新打包；新版 APK 直接覆蓋安裝即可，**資料會保留**（APK 用固定簽章 `android/app/debug.keystore`）。

### 自己打包

```bash
pnpm build:app      # 輸出靜態網站到 out/ 並同步到 android/、ios/
pnpm android        # 用 Android Studio 開啟，按 Run 裝到手機
pnpm ios            # 用 Xcode 開啟（需要 Mac；裝到自己的 iPhone 要 Apple ID 簽名）
```

### App 裡的 AI 判斷

App 是純靜態網頁，沒有伺服器，AI 判斷會呼叫線上網站的 `/api/judge`（API key 留在伺服器，不會放進 App）：

1. 把這個專案部署到 Vercel，設定 `ANTHROPIC_API_KEY`
2. 打包 App 時設定 `NEXT_PUBLIC_API_BASE=https://你的網站.vercel.app`
   - GitHub Actions：repo **Settings → Secrets and variables → Actions → Variables** 新增 `API_BASE`
   - 本機：寫在 `.env.local`

## 資料存在哪？

### App 版：手機內存

| 資料 | 位置 |
|---|---|
| 訓練紀錄 | App 資料夾裡的 `fitness-log.json` |
| 照片 | App 資料夾裡的 `photos/YYYY-MM-DD.jpg` |

- 存成真正的檔案（Capacitor Filesystem，`Directory.Data`），不受清除瀏覽器資料影響，**解除安裝 App 才會刪除**
- iPhone 可以在「檔案」App →「我的 iPhone」→「健身日記」看到這些檔案
- 第一次開 App 時，如果 WebView 裡有舊資料會自動搬進檔案
- 換手機前用「備份到手機」產生備份檔（可存到「檔案」、Google 雲端硬碟），新手機再「從備份還原」

### 網頁版：瀏覽器

| 資料 | 位置 |
|---|---|
| 訓練部位、備註、AI 判斷結果 | 瀏覽器 `localStorage`（key：`fitness-workout-log-v2`） |
| 照片 | 瀏覽器 `IndexedDB`（資料庫 `fitness-photos`），壓縮成長邊 1280px 的 JPEG |

開啟時會請瀏覽器「持久保存」，但清除瀏覽器資料仍會消失，請定期備份。

兩個版本的資料都只在手機上，不會上傳（按 AI 判斷時，照片只會送給 Claude 判斷一次，不會被保存）。
