import React, { useEffect, useMemo, useState } from "react"

const FIELD_OPTIONS = [
  { value: "work_experience_years", label: "Work experience" },
  { value: "skill", label: "Skills" },
  { value: "project", label: "Projects" },
  { value: "bucket", label: "Bucket" },
  { value: "role", label: "Role" },
  { value: "bench", label: "Bench" },
  { value: "certification", label: "Certifications" },
]

const PROFICIENCY_OPTIONS = [
  { value: "", label: "Any" },
  { value: "BASIC", label: "Basic" },
  { value: "INTERMEDIATE", label: "Intermediate" },
  { value: "ADVANCED", label: "Advanced" },
]

const WORK_EXP_OPERATORS = [
  { value: ">=", label: ">=" },
  { value: "<=", label: "<=" },
  { value: "between", label: "between" },
]

function defaultRow() {
  return {
    field: "skill",
    operator: "contains",
    value: "",
    value2: "",
    proficiency: "",
  }
}

function SearchableInput({ value, onChange, placeholder, options, listId }) {
  return (
    <>
      <input
        list={listId}
        className="w-full rounded-xl border-2 border-emerald-200 bg-white px-4 py-3 text-sm font-medium transition-all hover:border-emerald-300 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 text-gray-900 placeholder:text-gray-400 caret-emerald-900"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
      <datalist id={listId}>
        {(options || []).map((o) => (
          <option key={o} value={o} />
        ))}
      </datalist>
    </>
  )
}

function buildFilter(row) {
  if (!row?.field) return null

  if (row.field === "work_experience_years") {
    const op = row.operator || ">="
    const v = String(row.value || "").trim()
    const v2 = String(row.value2 || "").trim()
    if (!v) return null
    if (op === "between" && !v2) return null
    return {
      field: "work_experience_years",
      operator: op,
      value: Number(v),
      value2: op === "between" ? Number(v2) : null,
    }
  }

  if (row.field === "bench") {
    if (row.value === "") return null
    return {
      field: "bench",
      operator: "equals",
      value: row.value === "true",
    }
  }

  if (row.field === "bucket" || row.field === "role") {
    if (!row.value) return null
    return {
      field: row.field,
      operator: "equals",
      value: row.value,
    }
  }

  if (row.field === "skill") {
    if (!row.value) return null
    const obj = {
      field: "skill",
      operator: "contains",
      value: row.value,
    }
    if (row.proficiency) obj.proficiency = row.proficiency
    return obj
  }

  if (row.field === "project") {
    if (!row.value) return null
    return {
      field: "project",
      operator: "contains",
      value: row.value,
    }
  }

  if (row.field === "certification") {
    if (!row.value) return null
    return {
      field: "certification",
      operator: "contains",
      value: row.value,
    }
  }

  return null
}

function previewClause(f) {
  if (!f) return ""
  if (f.field === "work_experience_years") {
    if (f.operator === "between") return `work experience between ${f.value} and ${f.value2} years`
    return `work experience ${f.operator} ${f.value} years`
  }
  if (f.field === "bench") return `bench equals ${f.value ? "Yes" : "No"}`
  if (f.field === "skill") {
    const prof = f.proficiency ? ` (proficiency: ${String(f.proficiency).charAt(0)}${String(f.proficiency).slice(1).toLowerCase()})` : ""
    return `skill equals "${f.value}"${prof}`
  }
  if (f.operator === "equals") return `${f.field} equals "${f.value}"`
  return `${f.field} ${f.operator} "${f.value}"`
}

export default function FilterHelper({ setMessages }) {
  const [open, setOpen] = useState(false)
  const [op, setOp] = useState("AND")
  const [rowA, setRowA] = useState(defaultRow())
  const [rowB, setRowB] = useState(defaultRow())
  const [prompt, setPrompt] = useState("")
  const [loading, setLoading] = useState(false)

  const [projects, setProjects] = useState([])
  const [skills, setSkills] = useState([])
  const [certifications, setCertifications] = useState([])
  const [buckets, setBuckets] = useState([])
  const [roles, setRoles] = useState([])

  useEffect(() => {
    if (!open) return

    const load = async () => {
      try {
        const [p, s, c, b, r] = await Promise.all([
          fetch("http://localhost:5050/api/filter-options/projects").then((x) => x.json()),
          fetch("http://localhost:5050/api/filter-options/skills").then((x) => x.json()),
          fetch("http://localhost:5050/api/filter-options/certifications").then((x) => x.json()),
          fetch("http://localhost:5050/api/filter-options/buckets").then((x) => x.json()),
          fetch("http://localhost:5050/api/filter-options/roles").then((x) => x.json()),
        ])

        setProjects(Array.isArray(p) ? p : [])
        setSkills(Array.isArray(s) ? s : [])
        setCertifications(Array.isArray(c) ? c : [])
        setBuckets(Array.isArray(b) ? b : [])
        setRoles(Array.isArray(r) ? r : [])
      } catch (e) {
        setProjects([])
        setSkills([])
        setCertifications([])
        setBuckets([])
        setRoles([])
      }
    }

    load()
  }, [open])

  const builtA = useMemo(() => buildFilter(rowA), [rowA])
  const builtB = useMemo(() => buildFilter(rowB), [rowB])
  const canRun = useMemo(() => {
    const filters = [builtA, builtB].filter(Boolean)
    return filters.length > 0 && !loading
  }, [builtA, builtB, loading])

  const generatePrompt = () => {
    const clauses = [previewClause(builtA), previewClause(builtB)].filter(Boolean)
    if (!clauses.length) {
      setPrompt("Show candidates where <add at least one filter>.")
      return
    }
    const joiner = op === "OR" ? " OR " : " AND "
    setPrompt(`Show candidates where ${clauses.join(joiner)}.`)
  }

  const clearAll = () => {
    setRowA(defaultRow())
    setRowB(defaultRow())
    setOp("AND")
    setPrompt("")
  }

  const run = async () => {
    const filters = [builtA, builtB].filter(Boolean)
    if (!filters.length || loading) {
      if (typeof setMessages === "function") {
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 10,
            role: "assistant",
            content:
              "Please select at least one valid filter value (Row A and/or Row B) before clicking Run.",
          },
        ])
      }
      return
    }

    setLoading(true)
    try {
      console.log("[FilterHelper] Running structured filter", { op, filters })

      // Close the helper immediately so the user can see the chat output.
      setOpen(false)

      // Add a user-style message so the chat always visibly updates.
      const joiner = op === "OR" ? " OR " : " AND "
      const summary = [previewClause(builtA), previewClause(builtB)].filter(Boolean).join(joiner)
      if (typeof setMessages === "function") {
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            role: "user",
            content: prompt || `Show candidates where ${summary}.`,
          },
        ])
      }

      const res = await fetch("http://localhost:5050/api/candidates/filter", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ op, filters }),
      })

      const data = await res.json()
      if (!res.ok) throw new Error(data.error || "Filter failed")

      console.log("[FilterHelper] Response", data)

      const assistantMsg = {
        id: Date.now(),
        role: "assistant",
        content: data.message || "Results",
        structured: data.structured || null,
      }

      setMessages((prev) => [...prev, assistantMsg])
    } catch (e) {
      console.error("[FilterHelper] Failed", e)
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: "assistant",
          content: "Failed to run structured filter. Check backend /api/candidates/filter.",
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const renderValueInput = (row, setRow) => {
    if (row.field === "project") {
      return (
        <SearchableInput
          listId="fh-projects"
          value={row.value}
          onChange={(v) => setRow({ ...row, value: v })}
          placeholder="Type to search projects..."
          options={projects}
        />
      )
    }

    if (row.field === "skill") {
      return (
        <div className="grid gap-3 md:grid-cols-2">
          <SearchableInput
            listId="fh-skills"
            value={row.value}
            onChange={(v) => setRow({ ...row, value: v })}
            placeholder="Type to search skills..."
            options={skills}
          />
          <select
            className="w-full rounded-xl border-2 border-emerald-200 bg-white px-4 py-3 text-sm text-emerald-900 font-medium focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition-all hover:border-emerald-300"
            value={row.proficiency}
            onChange={(e) => setRow({ ...row, proficiency: e.target.value })}
          >
            {PROFICIENCY_OPTIONS.map((p) => (
              <option key={p.value || "any"} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
      )
    }

    if (row.field === "certification") {
      return (
        <SearchableInput
          listId="fh-certs"
          value={row.value}
          onChange={(v) => setRow({ ...row, value: v })}
          placeholder="Type to search certifications..."
          options={certifications}
        />
      )
    }

    if (row.field === "bucket") {
      return (
        <SearchableInput
          listId="fh-buckets"
          value={row.value}
          onChange={(v) => setRow({ ...row, value: v })}
          placeholder="Type to search buckets..."
          options={buckets}
        />
      )
    }

    if (row.field === "role") {
      return (
        <SearchableInput
          listId="fh-roles"
          value={row.value}
          onChange={(v) => setRow({ ...row, value: v })}
          placeholder="Type to search roles..."
          options={roles}
        />
      )
    }

    if (row.field === "bench") {
      return (
        <select
          className="w-full rounded-xl border-2 border-emerald-200 bg-white px-4 py-3 text-sm text-emerald-900 font-medium focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition-all hover:border-emerald-300"
          value={row.value}
          onChange={(e) => setRow({ ...row, value: e.target.value })}
        >
          <option value="">Select...</option>
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>
      )
    }

    if (row.field === "work_experience_years") {
      return (
        <div className="grid gap-3 md:grid-cols-3">
          <select
            className="w-full rounded-xl border-2 border-emerald-200 bg-white px-4 py-3 text-sm text-emerald-900 font-medium focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition-all hover:border-emerald-300"
            value={row.operator}
            onChange={(e) => setRow({ ...row, operator: e.target.value })}
          >
            {WORK_EXP_OPERATORS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <input
            type="number"
            className="w-full rounded-xl border-2 border-emerald-200 bg-white px-4 py-3 text-sm text-emerald-900 font-medium focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition-all hover:border-emerald-300"
            value={row.value}
            onChange={(e) => setRow({ ...row, value: e.target.value })}
            placeholder="Years"
          />
          {row.operator === "between" ? (
            <input
              type="number"
              className="w-full rounded-xl border-2 border-emerald-200 bg-white px-4 py-3 text-sm text-emerald-900 font-medium focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition-all hover:border-emerald-300"
              value={row.value2}
              onChange={(e) => setRow({ ...row, value2: e.target.value })}
              placeholder="And"
            />
          ) : (
            <div />
          )}
        </div>
      )
    }

    return (
      <input
        className="w-full rounded-xl border-2 border-emerald-200 bg-white px-4 py-3 text-sm text-emerald-900 font-medium focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition-all hover:border-emerald-300"
        value={row.value}
        onChange={(e) => setRow({ ...row, value: e.target.value })}
      />
    )
  }

  const renderRow = (label, row, setRow) => (
    <div className="rounded-2xl border border-emerald-200 bg-white/90 p-4">
      <div className="text-xs font-bold text-emerald-900 mb-3 uppercase tracking-wide">
        {label}
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        <div>
          <label className="block text-xs font-bold text-emerald-900 mb-2 uppercase tracking-wide">Field</label>
          <select
            className="w-full rounded-xl border-2 border-emerald-200 bg-white px-4 py-3 text-sm text-emerald-900 font-medium focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition-all hover:border-emerald-300"
            value={row.field}
            onChange={(e) => {
              const nextField = e.target.value
              setRow({
                field: nextField,
                operator: nextField === "work_experience_years" ? ">=" : nextField === "skill" ? "contains" : "contains",
                value: "",
                value2: "",
                proficiency: "",
              })
            }}
          >
            {FIELD_OPTIONS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </div>

        <div className="md:col-span-2">
          <label className="block text-xs font-bold text-emerald-900 mb-2 uppercase tracking-wide">Value</label>
          {renderValueInput(row, setRow)}
        </div>
      </div>
    </div>
  )

  return (
    <>
      <button
        onClick={() => setOpen((v) => !v)}
        className="group flex items-center gap-2 px-4 py-2.5 bg-white/80 hover:bg-white rounded-xl shadow-lg hover:shadow-emerald-500/25 border border-white/50 text-emerald-900 font-semibold text-sm transition-all duration-300 hover:scale-105 active:scale-95"
      >
        <span className="text-lg transition-transform duration-300 group-hover:scale-125">🧰</span>
        <span>Filter</span>
      </button>

      {open && (
        <div className="mb-4 rounded-2xl bg-white/95 shadow-[0_8px_30px_rgb(0,0,0,0.2)] border border-white/50 px-6 py-5 backdrop-blur-xl animate-[slideDown_0.3s_ease-out]">
          <div className="flex justify-between items-center mb-4">
            <div className="flex items-center gap-2">
              <span className="text-2xl">🧰</span>
              <h3 className="text-base font-bold text-emerald-900 uppercase tracking-wide">Filter Helper</h3>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="text-sm text-emerald-700 hover:text-emerald-900 font-medium transition-colors hover:scale-110 active:scale-95"
            >
              ✕ Close
            </button>
          </div>

          <div className="grid gap-4">
            {renderRow("Row A", rowA, setRowA)}

            <div className="flex items-center justify-center">
              <div className="flex items-center gap-3 rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-2">
                <span className="text-xs font-bold text-emerald-800 uppercase tracking-wide">Combine</span>
                <select
                  className="rounded-lg border border-emerald-200 bg-white px-3 py-2 text-sm text-emerald-900 font-semibold"
                  value={op}
                  onChange={(e) => setOp(e.target.value)}
                >
                  <option value="AND">AND</option>
                  <option value="OR">OR</option>
                </select>
              </div>
            </div>

            {renderRow("Row B", rowB, setRowB)}

            <div>
              <label className="block text-xs font-bold text-emerald-900 mb-2 uppercase tracking-wide">Prompt Preview</label>
              <textarea
                value={prompt}
                readOnly
                rows={2}
                className="w-full rounded-xl border-2 border-emerald-200 bg-white px-4 py-3 text-sm text-emerald-900 focus:outline-none"
                placeholder='Click "Generate Prompt"'
              />
            </div>

            <div className="flex justify-end gap-3">
              <button
                onClick={clearAll}
                className="px-5 py-2.5 rounded-xl border-2 border-emerald-200 text-emerald-800 hover:bg-emerald-50 font-semibold text-sm transition-all hover:scale-105 active:scale-95 hover:border-emerald-300"
              >
                Clear
              </button>
              <button
                onClick={generatePrompt}
                className="px-5 py-2.5 rounded-xl border-2 border-emerald-200 text-emerald-900 hover:bg-emerald-100 font-bold text-sm transition-all hover:scale-105 active:scale-95"
              >
                Generate Prompt
              </button>
              <button
                disabled={!canRun}
                onClick={run}
                className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 text-white font-bold text-sm shadow-lg disabled:opacity-40 hover:from-emerald-600 hover:to-emerald-700 transition-all hover:scale-105 active:scale-95 disabled:hover:scale-100 disabled:cursor-not-allowed hover:shadow-xl"
              >
                {loading ? "Running..." : "Run"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
