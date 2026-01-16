// src/components/JdPage.jsx
import React from "react"

export default function JdPage({ jdText, setJdText, jdStatus, handleJdSave }) {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="max-w-xl w-full rounded-3xl bg-white/80 backdrop-blur-xl border border-white/40 shadow-2xl p-6">
        <h2 className="text-lg font-semibold text-emerald-900 mb-2">
          Upload / paste job description
        </h2>
        <textarea
          className="w-full h-40 rounded-2xl border border-emerald-200 p-3 text-sm text-emerald-900 mb-3 focus:outline-none focus:ring-2 focus:ring-emerald-400"
          placeholder="Paste your JD here..."
          value={jdText}
          onChange={(e) => setJdText(e.target.value)}
        />
        <button
          onClick={handleJdSave}
          className="rounded-2xl bg-emerald-500 hover:bg-emerald-400 text-white text-sm font-medium px-4 py-2 shadow-lg"
        >
          Save JD
        </button>
        {jdStatus && (
          <div className="mt-3 text-xs text-emerald-800">{jdStatus}</div>
        )}
      </div>
    </div>
  )
}
