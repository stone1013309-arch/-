export type WorkoutType = 'push' | 'pull' | 'legs' | 'full'

export interface WorkoutTypeMeta {
  key: WorkoutType
  label: string
  short: string
  // Tailwind 用的語意 token 名稱
  color: string
  fg: string
}

// 預設分化：腿 → 拉 → 推
export const WORKOUT_TYPES: WorkoutTypeMeta[] = [
  { key: 'legs', label: '腿', short: '腿', color: 'legs', fg: 'legs-foreground' },
  { key: 'pull', label: '拉', short: '拉', color: 'pull', fg: 'pull-foreground' },
  { key: 'push', label: '推', short: '推', color: 'push', fg: 'push-foreground' },
  { key: 'full', label: '全體', short: '全', color: 'full', fg: 'full-foreground' },
]

export const TYPE_MAP: Record<WorkoutType, WorkoutTypeMeta> = WORKOUT_TYPES.reduce(
  (acc, t) => {
    acc[t.key] = t
    return acc
  },
  {} as Record<WorkoutType, WorkoutTypeMeta>,
)

// AI 看照片＋備註後的判斷結果
export interface AiJudgement {
  types: WorkoutType[]
  confidence: 'high' | 'medium' | 'low'
  summary: string
  tips: string
}

// 單日紀錄：訓練部位（可複選）＋ 自由文字備註 ＋ 是否有照片（照片本體存在 IndexedDB）
export interface DayEntry {
  types: WorkoutType[]
  note: string
  hasPhoto?: boolean
  ai?: AiJudgement
}

// 一整月的紀錄： { 'YYYY-MM-DD': { types: ['push', 'legs'], note: '...' } }
export type WorkoutLog = Record<string, DayEntry>

const STORAGE_KEY = 'fitness-workout-log-v2'
const LEGACY_KEY = 'fitness-workout-log-v1'

function normalize(parsed: unknown): WorkoutLog {
  if (!parsed || typeof parsed !== 'object') return {}
  const out: WorkoutLog = {}
  for (const [key, val] of Object.entries(parsed as Record<string, unknown>)) {
    if (Array.isArray(val)) {
      // 舊格式：僅有部位陣列
      out[key] = { types: val as WorkoutType[], note: '' }
    } else if (val && typeof val === 'object') {
      const v = val as { types?: unknown; note?: unknown; hasPhoto?: unknown; ai?: unknown }
      out[key] = {
        types: Array.isArray(v.types) ? (v.types as WorkoutType[]) : [],
        note: typeof v.note === 'string' ? v.note : '',
        hasPhoto: v.hasPhoto === true,
        ai: v.ai && typeof v.ai === 'object' ? (v.ai as AiJudgement) : undefined,
      }
    }
  }
  return out
}

export function loadLog(): WorkoutLog {
  if (typeof window === 'undefined') return {}
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (raw) return normalize(JSON.parse(raw))
    // 從舊版格式遷移
    const legacy = window.localStorage.getItem(LEGACY_KEY)
    if (legacy) return normalize(JSON.parse(legacy))
    return {}
  } catch {
    return {}
  }
}

export function saveLog(log: WorkoutLog) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(log))
  } catch {
    // 忽略儲存失敗（例如隱私模式）
  }
}

/* ---------- 腿拉推循環判斷 ---------- */

export const ROTATION: WorkoutType[] = ['legs', 'pull', 'push']

export interface Suggestion {
  type: WorkoutType
  reason: string
  // 上一次訓練（找不到則為 null）
  last: { key: string; types: WorkoutType[]; daysAgo: number } | null
}

function daysBetween(fromKey: string, to: Date): number {
  const [y, m, d] = fromKey.split('-').map(Number)
  const from = new Date(y, m - 1, d)
  const target = new Date(to.getFullYear(), to.getMonth(), to.getDate())
  return Math.round((target.getTime() - from.getTime()) / 86_400_000)
}

// 依「腿 → 拉 → 推」循環，從 date 之前最近一次有練腿/拉/推的紀錄推算今天該練什麼
export function suggestFor(log: WorkoutLog, date: Date): Suggestion {
  const dateKey = toKey(date)
  const keys = Object.keys(log)
    .filter((k) => k < dateKey && log[k].types.some((t) => ROTATION.includes(t)))
    .sort()
  const lastKey = keys[keys.length - 1]

  if (!lastKey) {
    return { type: 'legs', reason: '還沒有紀錄，從腿日開始循環', last: null }
  }

  const lastTypes = log[lastKey].types
  // 同一天練了多個部位時，以循環中最後面的那個為準
  const lastIdx = Math.max(...lastTypes.map((t) => ROTATION.indexOf(t)))
  const next = ROTATION[(lastIdx + 1) % ROTATION.length]
  const daysAgo = daysBetween(lastKey, date)
  const lastLabel = lastTypes.map((t) => TYPE_MAP[t].label).join('＋')
  const when = daysAgo === 1 ? '昨天' : `${daysAgo} 天前`

  let reason = `${when}練${lastLabel}，循環下一個是${TYPE_MAP[next].label}`
  if (daysAgo >= 4) reason += `；已休息 ${daysAgo - 1} 天，記得先暖身`
  return { type: next, reason, last: { key: lastKey, types: lastTypes, daysAgo } }
}

// 最近 n 筆有訓練的紀錄（給 AI 參考）
export function recentHistory(log: WorkoutLog, date: Date, n = 7) {
  const dateKey = toKey(date)
  return Object.keys(log)
    .filter((k) => k < dateKey && log[k].types.length > 0)
    .sort()
    .slice(-n)
    .map((k) => ({ date: k, types: log[k].types, note: log[k].note }))
}

/* ---------- 日期工具 ---------- */

export function toKey(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function isSameDay(a: Date, b: Date): boolean {
  return toKey(a) === toKey(b)
}

// 是否為今天或過去（用來判斷未訓練的日子是否自動標為休息）
export function isTodayOrPast(d: Date): boolean {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  return target.getTime() <= today.getTime()
}

export const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']

export const MONTH_NAMES = [
  '1 月',
  '2 月',
  '3 月',
  '4 月',
  '5 月',
  '6 月',
  '7 月',
  '8 月',
  '9 月',
  '10 月',
  '11 月',
  '12 月',
]

export interface CalendarCell {
  date: Date
  key: string
  inMonth: boolean
}

// 產生月曆格子（含前後補齊，週日為每週第一天）
export function buildMonthGrid(year: number, month: number): CalendarCell[] {
  const first = new Date(year, month, 1)
  const startOffset = first.getDay() // 0 = 週日
  const start = new Date(year, month, 1 - startOffset)

  const cells: CalendarCell[] = []
  for (let i = 0; i < 42; i++) {
    const date = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i)
    cells.push({
      date,
      key: toKey(date),
      inMonth: date.getMonth() === month,
    })
  }
  // 若最後一整週都不在本月則裁掉（保持 5 或 6 週）
  while (cells.length > 35 && cells.slice(35).every((c) => !c.inMonth)) {
    cells.length = 35
  }
  return cells
}
