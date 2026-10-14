// 儲存層：
// - 手機 App（Capacitor）：寫成檔案存在 App 的內部儲存空間（Directory.Data）
//     fitness-log.json        訓練紀錄
//     photos/YYYY-MM-DD.jpg   每日照片
//   解除安裝 App 才會刪除，不受清除瀏覽器資料影響
// - 網頁版：紀錄存 localStorage、照片存 IndexedDB

import { Capacitor } from '@capacitor/core'
import { Directory, Encoding, Filesystem } from '@capacitor/filesystem'
import { loadLocalLog, normalize, saveLocalLog, type WorkoutLog } from '@/lib/workouts'
import { blobToBase64, idbDeletePhoto, idbGetPhoto, idbPutPhoto } from '@/lib/photo-store'

const LOG_FILE = 'fitness-log.json'
const photoPath = (key: string) => `photos/${key}.jpg`

export function isNativeApp(): boolean {
  return Capacitor.isNativePlatform()
}

async function fileExists(path: string): Promise<boolean> {
  try {
    await Filesystem.stat({ path, directory: Directory.Data })
    return true
  } catch {
    return false
  }
}

export async function loadLog(): Promise<WorkoutLog> {
  if (!isNativeApp()) return loadLocalLog()
  if (!(await fileExists(LOG_FILE))) {
    // 第一次開 App：若 WebView 裡有舊資料就搬過來
    const legacy = loadLocalLog()
    if (Object.keys(legacy).length) await saveLog(legacy)
    return legacy
  }
  const { data } = await Filesystem.readFile({
    path: LOG_FILE,
    directory: Directory.Data,
    encoding: Encoding.UTF8,
  })
  return normalize(JSON.parse(typeof data === 'string' ? data : await data.text()))
}

export async function saveLog(log: WorkoutLog): Promise<void> {
  if (!isNativeApp()) {
    saveLocalLog(log)
    return
  }
  await Filesystem.writeFile({
    path: LOG_FILE,
    directory: Directory.Data,
    encoding: Encoding.UTF8,
    data: JSON.stringify(log),
  })
}

export async function getPhoto(key: string): Promise<Blob | undefined> {
  if (!isNativeApp()) return idbGetPhoto(key)
  if (!(await fileExists(photoPath(key)))) return undefined
  const { data } = await Filesystem.readFile({ path: photoPath(key), directory: Directory.Data })
  if (typeof data !== 'string') return data
  const bin = atob(data)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return new Blob([bytes], { type: 'image/jpeg' })
}

export async function putPhoto(key: string, blob: Blob): Promise<void> {
  if (!isNativeApp()) return idbPutPhoto(key, blob)
  await Filesystem.writeFile({
    path: photoPath(key),
    directory: Directory.Data,
    data: await blobToBase64(blob),
    recursive: true,
  })
}

export async function deletePhoto(key: string): Promise<void> {
  if (!isNativeApp()) return idbDeletePhoto(key)
  if (await fileExists(photoPath(key))) {
    await Filesystem.deleteFile({ path: photoPath(key), directory: Directory.Data })
  }
}
