import Anthropic from '@anthropic-ai/sdk'
import { betaZodOutputFormat } from '@anthropic-ai/sdk/helpers/beta/zod'
import { z } from 'zod'

// 看今日照片＋備註，判斷今天練的是腿 / 拉 / 推 / 全身，並給一點建議
// 需要在部署環境設定 ANTHROPIC_API_KEY

export const runtime = 'nodejs'
export const maxDuration = 60

const WorkoutTypeSchema = z.enum(['legs', 'pull', 'push', 'full'])

const JudgementSchema = z.object({
  types: z.array(WorkoutTypeSchema),
  confidence: z.enum(['high', 'medium', 'low']),
  summary: z.string(),
  tips: z.string(),
})

const RequestSchema = z.object({
  date: z.string(),
  note: z.string().max(2000),
  selected: z.array(WorkoutTypeSchema),
  suggested: WorkoutTypeSchema,
  imageBase64: z.string().max(8_000_000).optional(),
  history: z
    .array(z.object({ date: z.string(), types: z.array(WorkoutTypeSchema), note: z.string() }))
    .max(14),
})

const SYSTEM = `你是使用者的健身紀錄助理。使用者採用「腿 → 拉 → 推」三分化循環。
根據今日照片（可能是健身器材、訓練中的自拍、運動 App 截圖或白板菜單）與文字備註，判斷今天練的部位：
- legs：深蹲、腿推、硬舉、弓箭步、腿彎舉/伸展、小腿等
- pull：引體向上、划船、滑輪下拉、二頭等（背、二頭、後三角）
- push：臥推、肩推、雙槓撐體、飛鳥、三頭等（胸、肩、三頭）
- full：明確涵蓋上下半身的全身訓練
可複選；若照片與備註都看不出來，types 回傳空陣列並把 confidence 設為 low。
summary：一句話說明你的判斷依據。tips：一到兩句具體建議（例如與循環是否吻合、恢復、下次可以加什麼）。
全部用繁體中文，語氣簡潔友善。`

const LABEL = { legs: '腿', pull: '拉', push: '推', full: '全身' } as const

export async function POST(req: Request) {
  if (!process.env.ANTHROPIC_API_KEY) {
    return Response.json(
      { error: '伺服器尚未設定 ANTHROPIC_API_KEY，無法使用 AI 判斷' },
      { status: 501 },
    )
  }

  const parsed = RequestSchema.safeParse(await req.json().catch(() => null))
  if (!parsed.success) {
    return Response.json({ error: '請求格式錯誤' }, { status: 400 })
  }
  const body = parsed.data

  const historyText = body.history.length
    ? body.history
        .map((h) => `${h.date}：${h.types.map((t) => LABEL[t]).join('＋')}${h.note ? `（${h.note}）` : ''}`)
        .join('\n')
    : '（無）'

  const text = `日期：${body.date}
依循環今天應該練：${LABEL[body.suggested]}
使用者目前勾選：${body.selected.map((t) => LABEL[t]).join('＋') || '（未勾選）'}
今日備註：${body.note || '（無）'}
最近紀錄：
${historyText}
${body.imageBase64 ? '附上今日照片。' : '沒有附照片，請只依備註判斷。'}`

  const content: Anthropic.Beta.BetaContentBlockParam[] = []
  if (body.imageBase64) {
    content.push({
      type: 'image',
      source: { type: 'base64', media_type: 'image/jpeg', data: body.imageBase64 },
    })
  }
  content.push({ type: 'text', text })

  const client = new Anthropic()
  try {
    const response = await client.beta.messages.parse({
      model: 'claude-opus-5-5',
      max_tokens: 4000,
      system: SYSTEM,
      messages: [{ role: 'user', content }],
      output_config: { effort: 'low', format: betaZodOutputFormat(JudgementSchema) },
      // 被安全機制拒絕時由伺服器自動改用建議的備援模型
      betas: ['server-side-fallback-2026-07-01'],
      fallbacks: 'default',
    })

    if (response.stop_reason === 'refusal' || !response.parsed_output) {
      return Response.json({ error: 'AI 無法判斷這張照片，請改用手動選擇' }, { status: 422 })
    }
    return Response.json(response.parsed_output)
  } catch (err) {
    if (err instanceof Anthropic.RateLimitError) {
      return Response.json({ error: 'AI 使用量過高，請稍後再試' }, { status: 429 })
    }
    if (err instanceof Anthropic.APIError) {
      console.error('Claude API error', err.status, err.message)
      return Response.json({ error: 'AI 判斷失敗，請稍後再試' }, { status: 502 })
    }
    throw err
  }
}
