"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { ArrowLeft, Check } from "lucide-react"

const ICONS = [
  {
    id: "dumbbell",
    src: "/icon-options/option-1-dumbbell.png",
    name: "啞鈴",
    desc: "活力綠漸層，與 App 主色一致",
  },
  {
    id: "calendar",
    src: "/icon-options/option-2-calendar.png",
    name: "訓練日曆",
    desc: "月曆格子加上訓練標記",
  },
  {
    id: "flex",
    src: "/icon-options/option-3-flex.png",
    name: "手臂肌肉",
    desc: "橘紅漸層，充滿能量",
  },
  {
    id: "monogram",
    src: "/icon-options/option-4-monogram.png",
    name: "幾何字標",
    desc: "深藍質感，低調高級",
  },
]

export default function ChooseIconPage() {
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    setSelected(localStorage.getItem("app-icon-choice"))
  }, [])

  function choose(id: string) {
    setSelected(id)
    localStorage.setItem("app-icon-choice", id)
  }

  return (
    <main className="mx-auto flex min-h-svh max-w-md flex-col gap-6 px-4 py-6">
      <header className="flex items-center gap-3">
        <Link
          href="/"
          className="flex size-9 items-center justify-center rounded-full border border-border text-foreground transition-colors hover:bg-secondary"
          aria-label="返回"
        >
          <ArrowLeft className="size-5" />
        </Link>
        <div>
          <h1 className="text-xl font-bold text-balance">選擇 App 圖標</h1>
          <p className="text-sm text-muted-foreground">點一款你喜歡的圖標</p>
        </div>
      </header>

      <div className="grid grid-cols-2 gap-4">
        {ICONS.map((icon) => {
          const isSelected = selected === icon.id
          return (
            <button
              key={icon.id}
              type="button"
              onClick={() => choose(icon.id)}
              className={`relative flex flex-col items-center gap-3 rounded-2xl border-2 p-4 text-center transition-all ${
                isSelected
                  ? "border-primary bg-primary/5"
                  : "border-border bg-card hover:border-muted-foreground/40"
              }`}
              aria-pressed={isSelected}
            >
              {isSelected && (
                <span className="absolute right-2 top-2 flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground">
                  <Check className="size-4" />
                </span>
              )}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={icon.src || "/placeholder.svg"}
                alt={icon.name}
                className="size-24 rounded-2xl object-cover shadow-sm"
              />
              <div>
                <p className="font-semibold text-foreground">{icon.name}</p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground text-pretty">{icon.desc}</p>
              </div>
            </button>
          )
        })}
      </div>

      {selected && (
        <div className="rounded-xl border border-border bg-secondary/50 p-4 text-center text-sm text-secondary-foreground">
          已選擇「{ICONS.find((i) => i.id === selected)?.name}」。跟我說你選的這款，我就把它設定成 App 圖標並完成安裝設定。
        </div>
      )}
    </main>
  )
}
