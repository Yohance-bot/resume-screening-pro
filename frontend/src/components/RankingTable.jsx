import React from "react"

export default function RankingTable({ data }) {
  // Supports BOTH shapes:
  // 1) structured = { type:"ranking", role, total_candidates, rows:[...] }
  // 2) structured = { type:"ranking", { role, total_candidates, rows:[...] } }
  const normalized = data?.rows ? data : (data?.data || {})
  const rows = normalized?.rows || []
  const role = normalized?.role || ""
  const total = normalized?.total_candidates ?? rows.length

  if (!rows.length) {
    return (
      <div className="text-center py-8 text-gray-400">
        No ranked candidates
      </div>
    )
  }

  return (
    <div className="mt-4 overflow-x-auto rounded-xl border border-gray-200">
      <div className="p-4 bg-gradient-to-r from-emerald-50 to-blue-50 border-b border-gray-200">
        <div className="text-lg font-bold text-emerald-900">
          Top {role || "Candidates"}
        </div>
        <div className="text-sm text-gray-600">
          Showing {rows.length} of {total}
        </div>
      </div>

      <table className="w-full text-left text-sm text-gray-700">
        <thead className="bg-gray-100">
          <tr>
            <th className="px-4 py-3 font-semibold">Rank</th>
            <th className="px-4 py-3 font-semibold">Name</th>
            <th className="px-4 py-3 font-semibold">Score</th>
            <th className="px-4 py-3 font-semibold">Experience</th>
            <th className="px-4 py-3 font-semibold">Skills</th>
            <th className="px-4 py-3 font-semibold">Reason</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, idx) => (
            <tr
              key={idx}
              className="border-t border-gray-200 hover:bg-gray-50"
            >
              <td className="px-4 py-3">{r.rank ?? idx + 1}</td>
              <td className="px-4 py-3 font-medium">
                {r.name || r.full_name || "Unknown"}
              </td>
              <td className="px-4 py-3">{String(r.score ?? "")}</td>
              <td className="px-4 py-3">{r.experience || ""}</td>
              <td className="px-4 py-3">{r.skills || ""}</td>
              <td className="px-4 py-3">{r.reason || ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
