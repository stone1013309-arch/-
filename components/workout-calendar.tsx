'use client'

import { useEffect, useMemo, useState } from 'react'
import { Camera, ChevronLeft, ChevronRight, Moon, Sun } from 'lucide-react'
import { cn } from '@/lib/utils'
import { WorkoutPickerSheet } from '@/components/workout-picker-sheet'
import {
  WORKOUT_TYPES,
  TYPE_MAP,
  WEEKDAYS,
  MONTH_NAMES,
  buildMonthGrid,
  loadLog,
  saveLog,
  toKey,
  isSameDay,
  isTodayOrPast,
  suggestFor,
  recentHistory,
  type DayEntry,
  type WorkoutLog,
} from '@/lib/workouts'
import { deletePhoto, putPhoto } from '@/lib/photo-store'

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

  useEffect(() => {
    setLog(loadLog())
    setMounted(true)
  }, [])

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
      // IndexedDB 不可用（例如部分隱私模式），照片不保存
      if (saved) saved = { ...saved, hasPhoto: false }
    }
    setLog((prev) => {
      const next = { ...prev }
      if (!saved) {
        delete next[key] // 清空紀錄
      } else {
        next[key] = saved
      }
      saveLog(next)
      return next
    })
    setActiveDate(null)
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
      } else if (isTodayOrPast(c.date)) {
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
          <span
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-xl font-bold"
            style={{
              backgroundColor: `var(--${TYPE_MAP[todaySuggestion.type].color})`,
              color: `var(--${TYPE_MAP[todaySuggestion.type].fg})`,
            }}
          >
            {TYPE_MAP[todaySuggestion.type].short}
          </span>
          <span className="min-w-0">
            <span className="block text-sm font-semibold">
              {todayEntry?.types.length
                ? `今天已記錄：${todayEntry.types.map((t) => TYPE_MAP[t].label).join('＋')}`
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
          const isRest = mounted && c.inMonth && !hasWorkout && isTodayOrPast(c.date)

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
