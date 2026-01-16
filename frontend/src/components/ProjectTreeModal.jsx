// src/components/ProjectTreeModal.jsx
export default function ProjectTreeModal({ project, onClose }) {
  if (!project) return null

  const sortedMembers = [...project.members].sort(
    (a, b) => (b.years || 0) - (a.years || 0)
  )

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-3xl rounded-3xl bg-white/95 shadow-2xl p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-emerald-900">
            {project.name}
          </h2>
          <button
            onClick={onClose}
            className="text-xs px-3 py-1.5 rounded-xl border border-emerald-200 text-emerald-800 hover:bg-emerald-50"
          >
            Close
          </button>
        </div>

        {/* tech tags */}
        <div className="mb-4 flex flex-wrap gap-1">
          {project.technologies.slice(0, 12).map((t, i) => (
            <span
              key={i}
              className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[11px]"
            >
              {t}
            </span>
          ))}
        </div>

        {/* tree */}
        <div className="relative pl-4">
          {/* root line */}
          <div className="mb-3">
            <div className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 text-white px-3 py-2 text-sm font-semibold shadow">
              <span>Project</span>
              <span className="opacity-80 text-[11px]">
                {sortedMembers.length} member(s)
              </span>
            </div>
          </div>

          <div className="border-l border-emerald-200 pl-4 space-y-2">
            {sortedMembers.map((m, idx) => (
              <div key={m.id} className="relative">
                <div className="absolute -left-4 top-3 h-px w-4 bg-emerald-200" />
                <div className="inline-flex items-center gap-2 rounded-xl bg-emerald-50 px-3 py-2 text-[12px] text-emerald-900 shadow-sm">
                  <div className="font-semibold">
                    {m.name} (ID {m.id})
                  </div>
                  <div className="text-emerald-700 text-[11px]">
                    {m.role || "-"}
                  </div>
                  <div className="text-emerald-700 text-[11px]">
                    {(m.years ?? 0).toFixed(1)} yrs
                  </div>
                  {/* placeholder: requirement badge */}
                  {m.requirement && (
                    <span className="ml-2 px-2 py-0.5 rounded-full bg-red-100 text-red-700 text-[10px]">
                      Open requirement
                    </span>
                  )}
                </div>
              </div>
            ))}

            {/* future: requirement-only nodes */}
            {/* <div className="relative">
              <div className="absolute -left-4 top-3 h-px w-4 bg-rose-300" />
              <div className="inline-flex items-center gap-2 rounded-xl bg-rose-50 px-3 py-2 text-[12px] text-rose-900 shadow-sm">
                <span className="font-semibold">Senior DS needed</span>
                <span className="text-[11px]">
                  5+ yrs, Python + PyTorch, client X
                </span>
              </div>
            </div> */}
          </div>
        </div>
      </div>
    </div>
  )
}
