'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { Camera, ChevronLeft, ChevronRight, Download, Moon, Sun, Upload } from 'lucide-react'
import { cn } from '@/lib/utils'
import { WorkoutPickerSheet } from '@/components/workout-picker-sheet'
import {
  WORKOUT_TYPES,
  TYPE_MAP,
  WEEKDAYS,
  MONTH_NAMES,
  buildMonthGrid,
  toKey,
  isSameDay,
  isRestDay,
  suggestFor,
  recentHistory,
  type DayEntry,
  type WorkoutLog,
} from '@/lib/workouts'
import { deletePhoto, isNativeApp, loadLog, putPhoto, saveLog } from '@/lib/storage'
import { exportBackup, importBackup, requestPersistentStorage } from '@/lib/backup'

const THEME_KEY = 'fitness-theme'

function useTheme() {
  const [theme, setTheme] = useState<'light' | 'dark'>('light')

  useEffect(() => {
    const root = document.documentElement
    const initial = root.classList.contains('dark') ? 'dark' : 'light'
    setTheme(initial)
  }, [])

  const toggle = () => {
    setTheme((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark'
      const root = document.documentElement
      root.classList.toggle('dark', next === 'dark')
      root.style.colorScheme = next
      try {
        window.localStorage.setItem(THEME_KEY, next)
      } catch {
        // 忽略
      }
      return next
    })
  }

  return { theme, toggle }
}

export function WorkoutCalendar() {
  const today = useMemo(() => new Date(), [])
  const [view, setView] = useState({ year: today.getFullYear(), month: today.getMonth() })
  const [log, setLog] = useState<WorkoutLog>({})
  const [activeDate, setActiveDate] = useState<Date | null>(null)
  const [mounted, setMounted] = useState(false)
  const { theme, toggle } = useTheme()

  const [persisted, setPersisted] = useState<boolean | null>(null)
  const [backupMsg, setBackupMsg] = useState<string | null>(null)
  const importRef = useRef<HTMLInputElement>(null)

  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    loadLog()
      .then(setLog)
      .catch(() => setSaveError('讀取紀錄失敗'))
      .finally(() => setMounted(true))
    requestPersistentStorage().then(setPersisted)
  }, [])

  const handleExport = async () => {
    setBackupMsg(null)
    try {
      const how = await exportBackup()
      setBackupMsg(how === 'shared' ? '已產生備份檔' : '備份檔已下載到手機')
    } catch (e) {
      if (!(e instanceof DOMException && e.name === 'AbortError')) setBackupMsg('備份失敗')
    }
  }

  const handleImport = async (file: File | undefined) => {
    if (!file) return
    if (!window.confirm('還原會取代目前所有紀錄與照片，確定嗎？')) return
    try {
      const days = await importBackup(file)
      setLog(await loadLog())
      setBackupMsg(`已還原 ${days} 天的紀錄`)
    } catch (e) {
      setBackupMsg(e instanceof Error ? e.message : '還原失敗')
    } finally {
      if (importRef.current) importRef.current.value = ''
    }
  }

  const cells = useMemo(() => buildMonthGrid(view.year, view.month), [view])

  const goPrev = () =>
    setView((v) => {
      const m = v.month - 1
      return m < 0 ? { year: v.year - 1, month: 11 } : { year: v.year, month: m }
    })
  const goNext = () =>
    setView((v) => {
      const m = v.month + 1
      return m > 11 ? { year: v.year + 1, month: 0 } : { year: v.year, month: m }
    })
  const goToday = () => setView({ year: today.getFullYear(), month: today.getMonth() })

  const handleSave = async (entry: DayEntry | null, photo: Blob | null | undefined) => {
    if (!activeDate) return
    const key = toKey(activeDate)
    let saved = entry
    try {
      if (photo) await putPhoto(key, photo)
      else if (photo === null || !entry) await deletePhoto(key)
    } catch {
      // 照片存不進去（例如瀏覽器隱私模式），只保存文字紀錄
      if (saved) saved = { ...saved, hasPhoto: false }
    }
    const next = { ...log }
    if (!saved) {
      delete next[key] // 清空紀錄
    } else {
      next[key] = saved
    }
    setLog(next)
    setActiveDate(null)
    try {
      await saveLog(next)
      setSaveError(null)
    } catch {
      setSaveError('儲存失敗，請再試一次')
    }
  }

  const todaySuggestion = useMemo(() => (mounted ? suggestFor(log, today) : null), [log, today, mounted])
  const todayEntry = mounted ? log[toKey(today)] : undefined

  // 統計本月
  const stats = useMemo(() => {
    const counts: Record<string, number> = { legs: 0, pull: 0, push: 0, full: 0, rest: 0 }
    for (const c of cells) {
      if (!c.inMonth) continue
      const entry = log[c.key]
      if (entry?.types?.length) {
        entry.types.forEach((t) => (counts[t] += 1))
      } else if (isRestDay(entry, c.date)) {
        counts.rest += 1
      }
    }
    return counts
  }, [cells, log])

  const isCurrentMonth = view.year === today.getFullYear() && view.month === today.getMonth()

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-md flex-col px-4 pb-10 pt-6">
      {/* 標題列 */}
      <header className="mb-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">訓練日曆</h1>
            <p className="mt-0.5 text-sm text-muted-foreground">預設腿 → 拉 → 推，點日期記錄</p>
          </div>
          <div className="flex items-center gap-2">
            {!isCurrentMonth && (
              <button
                onClick={goToday}
                className="rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium transition-colors hover:bg-accent"
              >
                今天
              </button>
            )}
            <button
              onClick={toggle}
              aria-label={theme === 'dark' ? '切換為亮色主題' : '切換為暗色主題'}
              className="flex h-9 w-9 items-center justify-center rounded-full border border-border bg-card text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
          </div>
        </div>
      </header>

      {/* 今日判斷：依腿拉推循環 */}
      {todaySuggestion && (
        <button
          onClick={() => setActiveDate(today)}
          className="mb-5 flex w-full items-center gap-3 rounded-2xl border border-border bg-card p-4 text-left transition-colors hover:bg-accent"
        >
          {todayEntry?.rest && !todayEntry.types.length ? (
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-muted text-muted-foreground">
              <Moon className="h-6 w-6" />
            </span>
          ) : (
            <span
              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-xl font-bold"
              style={{
                backgroundColor: `var(--${TYPE_MAP[todaySuggestion.type].color})`,
                color: `var(--${TYPE_MAP[todaySuggestion.type].fg})`,
              }}
            >
              {TYPE_MAP[todaySuggestion.type].short}
            </span>
          )}
          <span className="min-w-0">
            <span className="block text-sm font-semibold">
              {todayEntry?.types.length
                ? `今天已記錄：${todayEntry.types.map((t) => TYPE_MAP[t].label).join('＋')}`
                : todayEntry?.rest
                  ? '今天休息'
                  : `今天該練：${TYPE_MAP[todaySuggestion.type].label}`}
            </span>
            <span className="mt-0.5 block text-xs text-muted-foreground">{todaySuggestion.reason}</span>
          </span>
        </button>
      )}

      {/* 月份切換 */}
      <div className="mb-4 flex items-center justify-between">
        <button
          onClick={goPrev}
          aria-label="上個月"
          className="rounded-full p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <div className="text-center">
          <span className="font-mono text-lg font-semibold tabular-nums">
            {view.year} · {MONTH_NAMES[view.month]}
          </span>
        </div>
        <button
          onClick={goNext}
          aria-label="下個月"
          className="rounded-full p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <ChevronRight className="h-5 w-5" />
        </button>
      </div>

      {/* 星期標頭 */}
      <div className="mb-1.5 grid grid-cols-7 gap-1.5">
        {WEEKDAYS.map((w, i) => (
          <div
            key={w}
            className={cn(
              'py-1 text-center text-xs font-medium',
              i === 0 || i === 6 ? 'text-muted-foreground/70' : 'text-muted-foreground',
            )}
          >
            {w}
          </div>
        ))}
      </div>

      {/* 日期格子 */}
      <div className="grid grid-cols-7 gap-1.5">
        {cells.map((c) => {
          const entry = mounted ? log[c.key] : undefined
          const hasWorkout = entry?.types && entry.types.length > 0
          const hasNote = mounted && !!entry?.note
          const hasPhoto = mounted && !!entry?.hasPhoto
          const isToday = isSameDay(c.date, today)
          const isRest = mounted && c.inMonth && isRestDay(entry, c.date)

          return (
            <button
              key={c.key}
              onClick={() => setActiveDate(c.date)}
              className={cn(
                'relative flex aspect-square flex-col items-center justify-start gap-1 rounded-xl border p-1 pt-1.5 transition-all active:scale-95',
                c.inMonth
                  ? 'border-border bg-card'
                  : 'border-transparent bg-transparent opacity-35',
                isToday && 'ring-2 ring-primary ring-offset-2 ring-offset-background',
              )}
            >
              <span
                className={cn(
                  'font-mono text-sm tabular-nums leading-none',
                  isToday ? 'font-bold text-primary' : 'text-foreground',
                  !c.inMonth && 'text-muted-foreground',
                )}
              >
                {c.date.getDate()}
              </span>

              {/* 訓練標記 */}
              {hasWorkout && (
                <span className="flex max-w-full flex-wrap items-center justify-center gap-0.5">
                  {entry!.types.map((t) => (
                    <span
                      key={t}
                      className="flex h-4 w-4 items-center justify-center rounded-md text-[9px] font-bold leading-none"
                      style={{
                        backgroundColor: `var(--${TYPE_MAP[t].color})`,
                        color: `var(--${TYPE_MAP[t].fg})`,
                      }}
                    >
                      {TYPE_MAP[t].short}
                    </span>
                  ))}
                </span>
              )}

              {/* 休息標記（未訓練的今天或過去日子自動顯示） */}
              {isRest && (
                <Moon className="h-4 w-4 text-muted-foreground/60" aria-label="休息日" />
              )}

              {/* 照片標記 */}
              {hasPhoto && (
                <Camera className="absolute right-1 top-1 h-2.5 w-2.5 text-muted-foreground" aria-label="有照片" />
              )}

              {/* 備註標記 */}
              {hasNote && (
                <span
                  className="absolute bottom-1 h-1.5 w-1.5 rounded-full"
                  style={{ backgroundColor: 'var(--note)' }}
                  aria-label="有備註"
                />
              )}
            </button>
          )
        })}
      </div>

      {/* 圖例 */}
      <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2">
        {WORKOUT_TYPES.map((t) => (
          <div key={t.key} className="flex items-center gap-1.5">
            <span
              className="h-3.5 w-3.5 rounded-md"
              style={{ backgroundColor: `var(--${t.color})` }}
            />
            <span className="text-xs text-muted-foreground">{t.label}</span>
          </div>
        ))}
        <div className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: 'var(--note)' }} />
          <span className="text-xs text-muted-foreground">備註</span>
        </div>
      </div>

      {/* 本月統計 */}
      <div className="mt-6 rounded-2xl border border-border bg-card p-4">
        <p className="mb-3 text-sm font-semibold">本月統計</p>
        <div className="grid grid-cols-5 gap-2">
          {WORKOUT_TYPES.map((t) => (
            <div key={t.key} className="flex flex-col items-center gap-1">
              <span
                className="font-mono text-xl font-bold tabular-nums"
                style={{ color: `var(--${t.color})` }}
              >
                {stats[t.key]}
              </span>
              <span className="text-[11px] text-muted-foreground">{t.label}</span>
            </div>
          ))}
          <div className="flex flex-col items-center gap-1">
            <span className="font-mono text-xl font-bold tabular-nums text-muted-foreground">
              {stats.rest}
            </span>
            <span className="text-[11px] text-muted-foreground">休息</span>
          </div>
        </div>
      </div>

      {/* 資料保存 */}
      <div className="mt-6 rounded-2xl border border-border bg-card p-4">
        <p className="text-sm font-semibold">資料保存</p>
        <p className="mt-1 text-xs text-muted-foreground">
          {mounted && isNativeApp()
            ? '紀錄與照片以檔案存在手機內存（App 資料夾），不會上傳；解除安裝 App 前記得先備份。'
            : '紀錄與照片都存在這支手機上，不會上傳。'}
          {persisted === true && mounted && !isNativeApp() && '已開啟持久保存，系統不會自動清除。'}
          {persisted === false && '建議把網頁「加到主畫面」，並定期備份。'}
        </p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button
            onClick={handleExport}
            className="flex items-center justify-center gap-1.5 rounded-xl border border-border py-2.5 text-sm font-medium transition-colors hover:bg-accent"
          >
            <Download className="h-4 w-4" />
            備份到手機
          </button>
          <button
            onClick={() => importRef.current?.click()}
            className="flex items-center justify-center gap-1.5 rounded-xl border border-border py-2.5 text-sm font-medium transition-colors hover:bg-accent"
          >
            <Upload className="h-4 w-4" />
            從備份還原
          </button>
        </div>
        <input
          ref={importRef}
          type="file"
          accept="application/json,.json"
          className="hidden"
          onChange={(e) => handleImport(e.target.files?.[0])}
        />
        {backupMsg && <p className="mt-2 text-xs text-muted-foreground">{backupMsg}</p>}
        {saveError && <p className="mt-2 text-xs text-destructive">{saveError}</p>}
      </div>

      <WorkoutPickerSheet
        date={activeDate}
        entry={activeDate && mounted ? log[toKey(activeDate)] : undefined}
        suggestion={activeDate && mounted ? suggestFor(log, activeDate) : null}
        history={activeDate && mounted ? recentHistory(log, activeDate) : []}
        onClose={() => setActiveDate(null)}
        onSave={handleSave}
      />
    </div>
  )
}
