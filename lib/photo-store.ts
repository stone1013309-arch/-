// 網頁版：照片存在瀏覽器的 IndexedDB（localStorage 只有約 5MB，放不下照片）
// key 為日期 'YYYY-MM-DD'，value 為壓縮後的 JPEG Blob

const DB_NAME = 'fitness-photos'
const STORE = 'photos'

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1)
    req.onupgradeneeded = () => req.result.createObjectStore(STORE)
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function run<T>(
  mode: IDBTransactionMode,
  fn: (store: IDBObjectStore) => IDBRequest,
): Promise<T> {
  const db = await openDb()
  try {
    return await new Promise<T>((resolve, reject) => {
      const tx = db.transaction(STORE, mode)
      const req = fn(tx.objectStore(STORE))
      tx.oncomplete = () => resolve(req.result as T)
      tx.onerror = () => reject(tx.error)
    })
  } finally {
    db.close()
  }
}

export function idbGetPhoto(key: string): Promise<Blob | undefined> {
  return run('readonly', (s) => s.get(key))
}

export function idbPutPhoto(key: string, blob: Blob): Promise<void> {
  return run('readwrite', (s) => s.put(blob, key))
}

export function idbDeletePhoto(key: string): Promise<void> {
  return run('readwrite', (s) => s.delete(key))
}

// 縮到長邊 maxSize 並轉成 JPEG，手機原圖動輒 5MB 以上
export async function compressImage(file: Blob, maxSize = 1280, quality = 0.82): Promise<Blob> {
  const bitmap = await createImageBitmap(file)
  const scale = Math.min(1, maxSize / Math.max(bitmap.width, bitmap.height))
  const w = Math.round(bitmap.width * scale)
  const h = Math.round(bitmap.height * scale)
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  canvas.getContext('2d')!.drawImage(bitmap, 0, 0, w, h)
  bitmap.close()
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('壓縮失敗'))), 'image/jpeg', quality),
  )
}

export function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1] ?? '')
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(blob)
  })
}
