import React from "react"

export default function ActionPill({ icon, label, onClick }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/80 hover:bg-white border border-white/40 text-emerald-900 font-semibold text-sm"
    >
      <span className="text-lg">{icon}</span>
      <span>{label}</span>
    </button>
  )
}
