import React, { useMemo } from "react"
import RankingTable from "./RankingTable"
import SkillsCategorizedDisplay from "./SkillsCategorizedDisplay"

export default function MessageBubble({ message }) {
  const role = message?.role
  const content = message?.content ?? ""
  const structured = message?.structured ?? null

  // Debug (safe + non-crashy)
  console.log("🎉 MessageBubble loaded", {
    role,
    structured_type: structured?.type ?? null,
    rows_len: Array.isArray(structured?.rows) ? structured.rows.length : null,
    structured_keys: structured ? Object.keys(structured) : null,
  })

  // USER bubble
  if (role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-3xl rounded-2xl px-5 py-3 bg-emerald-600 text-white shadow">
          <pre className="whitespace-pre-wrap font-sans">{content}</pre>
        </div>
      </div>
    )
  }

  // ASSISTANT: skills display (supports either type or legacy shape)
  const isSkills =
    structured?.type === "skills_display" ||
    Boolean(structured?.data?.skills_by_category)

  if (isSkills) {
    const skillsData = structured?.data ?? structured
    return (
      <div className="flex justify-start">
        <div className="max-w-4xl bg-white/95 rounded-2xl p-5 shadow">
          <SkillsCategorizedDisplay data={skillsData} />
        </div>
      </div>
    )
  }

  // ASSISTANT: ranking
  if (structured?.type === "ranking") {
    const rankingData = normalizeRanking(structured)

    return (
      <div className="flex justify-start">
        <div className="max-w-5xl bg-white/95 rounded-2xl p-5 shadow">
          <FormattedMessage content={content} />
          <RankingTable data={rankingData} />
        </div>
      </div>
    )
  }

  // Default assistant bubble
  return (
    <div className="flex justify-start">
      <div className="max-w-3xl bg-white/95 rounded-2xl px-5 py-3 text-gray-800 shadow">
        <FormattedMessage content={content} />
      </div>
    </div>
  )
}

/**
 * Accepts any of these shapes:
 * - { type:"ranking", rows:[...], columns:[...] }
 * - { type:"ranking", { rows:[...], columns:[...] } }
 * - { type:"ranking", { ... } } (already normalized)
 */
function normalizeRanking(structured) {
  // Prefer rows at top-level, else fall back to structured.data
  if (Array.isArray(structured?.rows) && structured.rows.length > 0) {
    return structured
  }
  if (structured?.data) return structured.data
  return structured
}

function FormattedMessage({ content }) {
  const lines = useMemo(() => {
    if (!content) return []
    return String(content).split("\n")
  }, [content])

  if (!content) return null

  return (
    <div className="space-y-2">
      {lines.map((line, idx) => {
        // bold: **text**
        if (line.includes("**")) {
          const formatted = line.replace(
            /\*\*(.*?)\*\*/g,
            '<strong class="font-bold text-gray-900">$1</strong>'
          )
          return (
            <p
              key={idx}
              className="text-gray-800"
              dangerouslySetInnerHTML={{ __html: formatted }}
            />
          )
        }

        // bullets: • or -
        const trimmed = line.trim()
        if (trimmed.startsWith("•") || trimmed.startsWith("-")) {
          const cleaned = trimmed.replace(/^[-•]\s*/, "")
          return (
            <div key={idx} className="flex items-start gap-2 ml-4">
              <span className="text-emerald-600 font-bold">•</span>
              <span className="text-gray-700">{cleaned}</span>
            </div>
          )
        }

        // blank line spacer
        if (!trimmed) return <div key={idx} className="h-1" />

        return (
          <p key={idx} className="text-gray-700">
            {line}
          </p>
        )
      })}
    </div>
  )
}
