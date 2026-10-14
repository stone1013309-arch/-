# 健身日記

每天記錄訓練的手機網頁 App（Next.js，可加到主畫面當 PWA）。

- **預設腿 → 拉 → 推循環**：依上一次的訓練自動判斷「今天該練什麼」，新紀錄會預選建議部位
- **今天做了什麼**：勾選部位＋寫下動作、重量、組數
- **今日照片**：拍照或從相簿選，自動壓縮後存在手機上
- **AI 判斷**：把照片＋備註交給 Claude，判斷今天練的是腿／拉／推，並給一句建議，可一鍵套用

## 開發

```bash
pnpm install
cp .env.example .env.local   # 填入 ANTHROPIC_API_KEY（只有 AI 判斷需要）
pnpm dev
```

部署到 Vercel 時，在專案的 Environment Variables 加上 `ANTHROPIC_API_KEY`。

## 資料存在哪？

| 資料 | 位置 | 說明 |
|---|---|---|
| 訓練部位、備註、AI 判斷結果 | 瀏覽器 `localStorage`（key：`fitness-workout-log-v2`） | 純文字，很小 |
| 照片 | 瀏覽器 `IndexedDB`（資料庫 `fitness-photos`） | 壓縮成長邊 1280px 的 JPEG |

資料**只存在你這支手機的這個瀏覽器裡**，不會上傳到任何伺服器（按 AI 判斷時，照片只會送給 Claude 判斷一次，不會被保存）。
所以清除瀏覽器資料或換手機時紀錄會消失。

需要跨裝置同步或備份時，可以改接雲端：

- **Supabase**（推薦）：Postgres 存紀錄＋ Storage 存照片，有免費額度，也有登入功能
- **Firebase**：Firestore ＋ Cloud Storage
- **Vercel Postgres / Blob**：如果部署在 Vercel，最好整合
