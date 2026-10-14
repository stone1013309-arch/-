// 備份 / 還原：把紀錄＋照片打包成一個 JSON 檔，存到手機的「檔案」/「下載」/雲端硬碟

import { Directory, Encoding, Filesystem } from '@capacitor/filesystem'
import { Share } from '@capacitor/share'
import { type WorkoutLog } from '@/lib/workouts'
import { blobToBase64 } from '@/lib/photo-store'
import { deletePhoto, getPhoto, isNativeApp, loadLog, putPhoto, saveLog } from '@/lib/storage'

interface BackupFile {
  app: 'fitness-log'
  version: 1
  exportedAt: string
  log: WorkoutLog
  photos: Record<string, string> // 日期 → JPEG base64
}

// 網頁版：請瀏覽器把本站資料標成「持久保存」，空間不足時不會被自動清掉
// App 版：資料本來就是檔案，直接回傳 true
export async function requestPersistentStorage(): Promise<boolean> {
  if (isNativeApp()) return true
  try {
    if (!navigator.storage?.persist) return false
    if (await navigator.storage.persisted()) return true
    return await navigator.storage.persist()
  } catch {
    return false
  }
}

export async function exportBackup(): Promise<'shared' | 'downloaded'> {
  const log = await loadLog()
  const photos: Record<string, string> = {}
  for (const [key, entry] of Object.entries(log)) {
    if (!entry.hasPhoto) continue
    const blob = await getPhoto(key).catch(() => undefined)
    if (blob) photos[key] = await blobToBase64(blob)
  }
  const data: BackupFile = {
    app: 'fitness-log',
    version: 1,
    exportedAt: new Date().toISOString(),
    log,
    photos,
  }
  const d = new Date()
  const name = `fitness-log-backup-${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}.json`
  const json = JSON.stringify(data)

  // App：先寫到暫存資料夾，再開系統分享選單（可存到「檔案」、雲端硬碟、傳給自己）
  if (isNativeApp()) {
    const { uri } = await Filesystem.writeFile({
      path: name,
      directory: Directory.Cache,
      encoding: Encoding.UTF8,
      data: json,
    })
    await Share.share({ title: '健身日記備份', files: [uri] })
    return 'shared'
  }

  const file = new File([json], name, { type: 'application/json' })

  // 手機瀏覽器用分享選單，可選「儲存到檔案」；不支援時改用下載
  if (navigator.canShare?.({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title: '健身日記備份' })
      return 'shared'
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') throw e
    }
  }
  const url = URL.createObjectURL(file)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
  return 'downloaded'
}

function base64ToBlob(b64: string): Blob {
  const bin = atob(b64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return new Blob([bytes], { type: 'image/jpeg' })
}

// 用備份檔整個取代目前的資料，回傳還原的天數
export async function importBackup(file: File): Promise<number> {
  const data = JSON.parse(await file.text()) as Partial<BackupFile>
  if (data.app !== 'fitness-log' || !data.log || typeof data.log !== 'object') {
    throw new Error('這不是健身日記的備份檔')
  }
  const current = await loadLog()
  for (const key of Object.keys(current)) {
    if (current[key].hasPhoto) await deletePhoto(key).catch(() => {})
  }
  for (const [key, b64] of Object.entries(data.photos ?? {})) {
    await putPhoto(key, base64ToBlob(b64))
  }
  await saveLog(data.log)
  return Object.keys(data.log).length
}
