'use client'

import { useEffect, useRef, useState } from 'react'
import { Camera, Check, Loader2, Moon, Sparkles, Trash2, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  WORKOUT_TYPES,
  TYPE_MAP,
  WEEKDAYS,
  MONTH_NAMES,
  toKey,
  isPast,
  type AiJudgement,
  type DayEntry,
  type Suggestion,
  type WorkoutType,
} from '@/lib/workouts'
import { blobToBase64, compressImage, getPhoto } from '@/lib/photo-store'

interface WorkoutPickerSheetProps {
  date: Date | null
  entry: DayEntry | undefined
  suggestion: Suggestion | null
  history: { date: string; types: WorkoutType[]; note: string }[]
  onClose: () => void
  // photo：Blob = 新照片，null = 刪除照片，undefined = 照片沒變
  onSave: (entry: DayEntry | null, photo: Blob | null | undefined) => void
}

const NOTE_MAX = 500

const CONFIDENCE_LABEL: Record<AiJudgement['confidence'], string> = {
  high: '把握高',
  medium: '把握中',
  low: '把握低',
}

export function WorkoutPickerSheet({
  date,
  entry,
  suggestion,
  history,
  onClose,
  onSave,
}: WorkoutPickerSheetProps) {
  const [selected, setSelected] = useState<WorkoutType[]>([])
  const [rest, setRest] = useState(false)
  const [text, setText] = useState('')
  const [photo, setPhoto] = useState<Blob | null>(null)
  const [photoChanged, setPhotoChanged] = useState(false)
  const [photoUrl, setPhotoUrl] = useState<string | null>(null)
  const [ai, setAi] = useState<AiJudgement | undefined>(undefined)
  const [judging, setJudging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  // 打開面板時載入該日資料；沒有紀錄的日子：過去的預設休息，今天以後預選循環建議的部位
  useEffect(() => {
    if (!date) return
    const pastEmpty = !entry && isPast(date)
    setRest(entry ? !!entry.rest : pastEmpty)
    setSelected(entry ? entry.types : pastEmpty || !suggestion ? [] : [suggestion.type])
    setText(entry?.note ?? '')
    setAi(entry?.ai)
    setPhoto(null)
    setPhotoChanged(false)
    setError(null)
    let cancelled = false
    if (entry?.hasPhoto) {
      getPhoto(toKey(date))
        .then((b) => !cancelled && setPhoto(b ?? null))
        .catch(() => {})
    }
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [date])

  useEffect(() => {
    if (!photo) {
      setPhotoUrl(null)
      return
    }
    const url = URL.createObjectURL(photo)
    setPhotoUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [photo])

  // 鎖住背景捲動
  useEffect(() => {
    if (date) {
      document.body.style.overflow = 'hidden'
      return () => {
        document.body.style.overflow = ''
      }
    }
  }, [date])

  if (!date) return null

  const toggle = (t: WorkoutType) => {
    setRest(false)
    setSelected((prev) => (prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]))
  }

  const toggleRest = () => {
    setRest((r) => !r)
    setSelected([])
  }

  const handleFile = async (file: File | undefined) => {
    if (!file) return
    setError(null)
    try {
      setPhoto(await compressImage(file))
      setPhotoChanged(true)
      setAi(undefined)
    } catch {
      setError('無法讀取這張照片')
    }
  }

  const removePhoto = () => {
    setPhoto(null)
    setPhotoChanged(true)
    setAi(undefined)
    if (fileRef.current) fileRef.current.value = ''
  }

  const judge = async () => {
    if (!suggestion) return
    setJudging(true)
    setError(null)
    try {
      const res = await fetch('/api/judge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          date: toKey(date),
          note: text.trim(),
          selected,
          suggested: suggestion.type,
          imageBase64: photo ? await blobToBase64(photo) : undefined,
          history,
        }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.error ?? 'AI 判斷失敗')
      setAi(data as AiJudgement)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'AI 判斷失敗')
    } finally {
      setJudging(false)
    }
  }

  const save = () => {
    const note = text.trim()
    const hasPhoto = !!photo
    if (selected.length === 0 && note.length === 0 && !hasPhoto && !rest) {
      onSave(null, null)
      return
    }
    onSave(
      { types: selected, note, hasPhoto, ai, rest: rest && selected.length === 0 },
      photoChanged ? photo : undefined,
    )
  }

  const dateLabel = `${date.getFullYear()} 年 ${MONTH_NAMES[date.getMonth()]} ${date.getDate()} 日 · 週${WEEKDAYS[date.getDay()]}`
  const matchesRotation =
    suggestion && selected.length > 0 ? selected.includes(suggestion.type) : null

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
      {/* 遮罩 */}
      <button
        aria-label="關閉"
        onClick={onClose}
        className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-in fade-in"
      />

      {/* 面板 */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="記錄訓練"
        className="relative max-h-[92vh] w-full max-w-md overflow-y-auto rounded-t-2xl border border-border bg-popover p-5 pb-8 shadow-2xl animate-in slide-in-from-bottom duration-300 sm:rounded-2xl sm:pb-5"
      >
        <div className="mx-auto mb-4 h-1.5 w-10 rounded-full bg-border sm:hidden" />

        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <p className="text-sm text-muted-foreground">記錄訓練</p>
            <h2 className="mt-0.5 text-lg font-semibold text-pretty">{dateLabel}</h2>
          </div>
          <button
            onClick={onClose}
            aria-label="關閉"
            className="rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* 腿拉推循環建議 */}
        {suggestion && (
          <div className="mb-4 rounded-xl border border-border bg-card px-3 py-2.5 text-sm">
            <span className="text-muted-foreground">循環建議：</span>
            <span className="font-semibold" style={{ color: `var(--${TYPE_MAP[suggestion.type].color})` }}>
              {TYPE_MAP[suggestion.type].label}日
            </span>
            <p className="mt-0.5 text-xs text-muted-foreground">{suggestion.reason}</p>
            {matchesRotation === false && (
              <p className="mt-1 text-xs text-destructive">你選的部位和循環不同，循環會從你實際練的部位接續</p>
            )}
          </div>
        )}

        <p className="mb-3 text-xs text-muted-foreground">選擇訓練部位（可複選）</p>

        <div className="grid grid-cols-4 gap-2">
          {WORKOUT_TYPES.map((t) => {
            const active = selected.includes(t.key)
            return (
              <button
                key={t.key}
                onClick={() => toggle(t.key)}
                aria-pressed={active}
                className={cn(
                  'relative flex h-16 items-center justify-center rounded-xl border-2 text-xl font-bold transition-all',
                  active
                    ? 'scale-[0.98]'
                    : 'border-border bg-card text-foreground hover:border-muted-foreground/40',
                )}
                style={
                  active
                    ? {
                        backgroundColor: `var(--${t.color})`,
                        color: `var(--${t.fg})`,
                        borderColor: `var(--${t.color})`,
                      }
                    : undefined
                }
              >
                {active && (
                  <span className="absolute right-1.5 top-1.5">
                    <Check className="h-3.5 w-3.5" strokeWidth={3} />
                  </span>
                )}
                {t.label}
              </button>
            )
          })}
        </div>

        <button
          onClick={toggleRest}
          aria-pressed={rest}
          className={cn(
            'mt-2 flex h-11 w-full items-center justify-center gap-2 rounded-xl border-2 text-sm font-semibold transition-all',
            rest
              ? 'border-muted-foreground/50 bg-muted text-foreground'
              : 'border-border bg-card text-muted-foreground hover:border-muted-foreground/40',
          )}
        >
          <Moon className="h-4 w-4" />
          休息
          {rest && <Check className="h-3.5 w-3.5" strokeWidth={3} />}
        </button>

        {/* 今日做了什麼 */}
        <div className="mt-5">
          <div className="mb-2 flex items-center justify-between">
            <label htmlFor="day-note" className="text-xs font-medium text-muted-foreground">
              今天做了什麼
            </label>
            <span className="font-mono text-[11px] tabular-nums text-muted-foreground/70">
              {text.length}/{NOTE_MAX}
            </span>
          </div>
          <textarea
            id="day-note"
            value={text}
            onChange={(e) => setText(e.target.value.slice(0, NOTE_MAX))}
            placeholder={'例：深蹲 80kg 5x5\n腿推 4x12、腿彎舉 3x15'}
            rows={4}
            className="w-full resize-none rounded-xl border border-border bg-card px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 outline-none transition-colors focus:border-ring focus:ring-2 focus:ring-ring/30"
          />
        </div>

        {/* 今日照片 */}
        <div className="mt-4">
          <p className="mb-2 text-xs font-medium text-muted-foreground">今日照片</p>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
          {photoUrl ? (
            <div className="relative overflow-hidden rounded-xl border border-border">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={photoUrl} alt="今日照片" className="max-h-72 w-full object-cover" />
              <div className="absolute right-2 top-2 flex gap-2">
                <button
                  onClick={() => fileRef.current?.click()}
                  aria-label="更換照片"
                  className="rounded-full bg-black/60 p-2 text-white"
                >
                  <Camera className="h-4 w-4" />
                </button>
                <button
                  onClick={removePhoto}
                  aria-label="刪除照片"
                  className="rounded-full bg-black/60 p-2 text-white"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => fileRef.current?.click()}
              className="flex h-20 w-full items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border text-sm text-muted-foreground transition-colors hover:bg-accent"
            >
              <Camera className="h-5 w-5" />
              拍照或選擇照片
            </button>
          )}
        </div>

        {/* AI 判斷 */}
        <div className="mt-4">
          <button
            onClick={judge}
            disabled={judging || (!photo && text.trim().length === 0)}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-border bg-card py-2.5 text-sm font-medium transition-colors hover:bg-accent disabled:opacity-50"
          >
            {judging ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {judging ? '判斷中…' : 'AI 幫我判斷今天練了什麼'}
          </button>
          {error && <p className="mt-2 text-xs text-destructive">{error}</p>}
          {ai && (
            <div className="mt-3 rounded-xl border border-border bg-card p-3 text-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold">
                  {ai.types.length ? ai.types.map((t) => TYPE_MAP[t].label).join('＋') : '看不出來'}
                  <span className="ml-2 text-xs font-normal text-muted-foreground">
                    {CONFIDENCE_LABEL[ai.confidence]}
                  </span>
                </span>
                {ai.types.length > 0 && (
                  <button
                    onClick={() => {
                      setRest(false)
                      setSelected(ai.types)
                    }}
                    className="rounded-full bg-primary px-3 py-1 text-xs font-semibold text-primary-foreground"
                  >
                    套用
                  </button>
                )}
              </div>
              <p className="mt-1.5 text-muted-foreground">{ai.summary}</p>
              {ai.tips && <p className="mt-1.5">💡 {ai.tips}</p>}
            </div>
          )}
        </div>

        <div className="mt-5 flex gap-3">
          <button
            onClick={() => onSave(null, null)}
            className="flex-1 rounded-xl border border-border bg-card py-3 text-sm font-medium text-foreground transition-colors hover:bg-accent"
          >
            清除
          </button>
          <button
            onClick={save}
            className="flex-[1.6] rounded-xl bg-primary py-3 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
          >
            儲存
          </button>
        </div>
      </div>
    </div>
  )
}
