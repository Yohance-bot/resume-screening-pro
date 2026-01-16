import React, { useState } from 'react'

// 🎯 Bench Toggle Component
const BenchToggle = ({ candidateId, initialValue, onUpdate }) => {
  const [isOnBench, setIsOnBench] = useState(initialValue)
  const [isUpdating, setIsUpdating] = useState(false)

  const handleToggle = async () => {
    const newValue = !isOnBench
    setIsUpdating(true)

    try {
      const response = await fetch(`http://localhost:5050/api/candidates/${candidateId}/bench`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ on_bench: newValue }),
      })

      if (response.ok) {
        setIsOnBench(newValue)
        onUpdate && onUpdate(candidateId, newValue)
        console.log(`✅ Updated candidate ${candidateId} bench status to: ${newValue}`)
      } else {
        console.error('Failed to update bench status')
        setIsOnBench(isOnBench) // Revert
      }
    } catch (error) {
      console.error('Error updating bench status:', error)
      setIsOnBench(isOnBench) // Revert
    } finally {
      setIsUpdating(false)
    }
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={(e) => {
          e.stopPropagation() // Prevent row expansion
          handleToggle()
        }}
        disabled={isUpdating}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-offset-2 ${
          isOnBench
            ? 'bg-emerald-500 focus:ring-emerald-500 shadow-md'
            : 'bg-gray-300 focus:ring-gray-400'
        } ${isUpdating ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:scale-105'}`}
        title={isOnBench ? 'On Bench (Available)' : 'Off Bench (Busy)'}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform duration-300 ${
            isOnBench ? 'translate-x-6' : 'translate-x-1'
          }`}
        />
      </button>
      <span className={`text-xs font-medium transition-colors duration-300 ${
        isOnBench ? 'text-emerald-600' : 'text-gray-500'
      }`}>
        {isOnBench ? 'Available' : 'Busy'}
      </span>
    </div>
  )
}

export default function CandidatesPage({ 
  candidates, 
  expandedId, 
  setExpandedId,
  onRefresh 
}) {
  const [bucketFilter, setBucketFilter] = useState('all') // 'all', 'data_scientist', 'data_practice'

  const computeSkillProficiency = (parsed) => {
    const projects = (parsed && parsed.projects) || []

    const counts = new Map() // key -> { name, count }
    const norm = (s) => String(s || '').trim().toLowerCase()

    const addSkill = (raw) => {
      if (!raw) return
      const key = norm(raw)
      if (!key) return
      const prev = counts.get(key)
      if (prev) {
        prev.count += 1
      } else {
        counts.set(key, { name: String(raw).trim(), count: 1 })
      }
    }

    for (const p of projects) {
      if (!p || typeof p !== 'object') continue
      const arr =
        p.technical_tools ||
        p.technologies_used ||
        p.skills ||
        p.tools ||
        []

      if (Array.isArray(arr)) {
        for (const s of arr) addSkill(s)
      } else if (typeof arr === 'string') {
        // handle "Python, SQL" style
        for (const s of arr.split(',').map((x) => x.trim())) addSkill(s)
      }
    }

    const items = Array.from(counts.values()).sort((a, b) => b.count - a.count)

    // Simple, explainable thresholds:
    // - advanced: used in 4+ projects
    // - intermediate: used in 2-3 projects
    // - beginner: used once
    const advanced = []
    const intermediate = []
    const beginner = []
    for (const it of items) {
      if (it.count >= 4) advanced.push(it)
      else if (it.count >= 2) intermediate.push(it)
      else beginner.push(it)
    }

    return { advanced, intermediate, beginner }
  }

  const renderSkillChips = (items, style) => {
    const max = 2
    const shown = items.slice(0, max)
    const hidden = items.length - shown.length
    return (
      <div className="flex flex-wrap gap-1.5">
        {shown.map((it, idx) => (
          <span
            key={idx}
            title={`${it.name} • ${it.count} project(s)`}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium border whitespace-nowrap ${style}`}
          >
            {it.name}
          </span>
        ))}
        {hidden > 0 && (
          <span className="px-2.5 py-1 rounded-lg text-xs font-medium bg-gray-100 text-gray-700 border border-gray-200 whitespace-nowrap">
            +{hidden}
          </span>
        )}
      </div>
    )
  }

  const deleteCandidate = async (candidateId, candidateName) => {
    const ok = window.confirm(
      `Delete ${candidateName || 'this candidate'} (ID: ${candidateId})? This will permanently remove them from the database.`
    )
    if (!ok) return

    try {
      const res = await fetch(`http://localhost:5050/api/candidates/${candidateId}`, {
        method: 'DELETE',
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        alert(data?.error || 'Failed to delete candidate')
        return
      }
      onRefresh && onRefresh()
      if (expandedId === candidateId) setExpandedId(null)
    } catch (err) {
      console.error('Failed to delete candidate:', err)
      alert('Failed to delete candidate')
    }
  }

  // Filter candidates by bucket
  const filteredCandidates = candidates.filter(c => {
    if (bucketFilter === 'all') return true
    return c.role_bucket === bucketFilter
  })

  const dsCount = candidates.filter(c => c.role_bucket === 'data_scientist').length
  const dpCount = candidates.filter(c => c.role_bucket === 'data_practice').length

  if (!candidates || candidates.length === 0) {
    return (
      <div className="min-h-[400px] flex items-center justify-center animate-fade-in">
        <div className="text-center">
          <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-gradient-to-br from-emerald-500 to-yellow-500 flex items-center justify-center shadow-xl animate-bounce-slow">
            <span className="text-3xl">📋</span>
          </div>
          <p className="text-gray-600 text-lg mb-4">No candidates found</p>
          <button
            onClick={onRefresh}
            className="px-6 py-2.5 bg-gradient-to-r from-emerald-500 to-yellow-500 text-white rounded-2xl hover:shadow-lg font-medium transition-all duration-300 hover:scale-105"
          >
            Refresh Database
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 pb-20 animate-fade-in">
      {/* ✨ Apple-Style Header with Reset Button */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-emerald-500 to-yellow-500 p-8 shadow-xl transform transition-all duration-500 hover:shadow-2xl hover:scale-[1.01]">
        <div className="absolute inset-0 bg-white/5 backdrop-blur-sm"></div>
        <div className="relative flex items-center justify-between">
          <div className="animate-slide-in-left">
            <h2 className="text-3xl font-semibold text-white mb-1 tracking-tight">
              Candidate Database
            </h2>
            <p className="text-white/80 text-sm font-medium">
              {candidates.length} {candidates.length === 1 ? 'professional' : 'professionals'} • {dsCount} Data Scientists • {dpCount} Data Practice
            </p>
          </div>
          <div className="flex items-center gap-3 animate-slide-in-right">
            <button
              onClick={onRefresh}
              className="px-5 py-2.5 bg-white/10 backdrop-blur-xl border border-white/20 text-white rounded-xl hover:bg-white/20 transition-all duration-300 font-medium hover:scale-105 active:scale-95"
            >
              <span className="mr-2 inline-block transition-transform duration-500 hover:rotate-180">↻</span>
              Refresh
            </button>
            <button
              onClick={() => {
                if (window.confirm('⚠️ This will delete ALL candidates and vector database entries. Are you sure?')) {
                  fetch('http://localhost:5050/api/reset-candidates', { method: 'POST' })
                    .then(res => res.json())
                    .then(data => {
                      alert('✅ Database reset successfully!')
                      onRefresh()
                    })
                    .catch(err => alert('❌ Reset failed: ' + err.message))
                }
              }}
              className="px-5 py-2.5 bg-red-500/90 backdrop-blur-xl border border-red-400/30 text-white rounded-xl hover:bg-red-600 transition-all duration-300 font-medium hover:scale-105 active:scale-95 shadow-lg hover:shadow-red-500/50"
            >
              <span className="mr-2">🗑️</span>
              Reset DB
            </button>
          </div>
        </div>
      </div>

      {/* ✨ Clean Apple-Style Table - FIXED SCROLLING */}
      <div className="rounded-3xl overflow-hidden shadow-xl border border-gray-200 bg-white animate-slide-up">
        {/* Filter bar aligned with table */}
        <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm font-semibold text-gray-700">Filter by Role:</span>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setBucketFilter('all')}
                className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all duration-300 ${
                  bucketFilter === 'all'
                    ? 'bg-gradient-to-r from-emerald-500 to-yellow-500 text-white shadow-lg'
                    : 'bg-white text-gray-700 border border-gray-200 hover:bg-gray-100'
                }`}
              >
                All ({candidates.length})
              </button>
              <button
                type="button"
                onClick={() => setBucketFilter('data_scientist')}
                className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all duration-300 ${
                  bucketFilter === 'data_scientist'
                    ? 'bg-blue-500 text-white shadow-lg'
                    : 'bg-blue-50 text-blue-700 border border-blue-100 hover:bg-blue-100'
                }`}
              >
                Data Scientists ({dsCount})
              </button>
              <button
                type="button"
                onClick={() => setBucketFilter('data_practice')}
                className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all duration-300 ${
                  bucketFilter === 'data_practice'
                    ? 'bg-emerald-500 text-white shadow-lg'
                    : 'bg-emerald-50 text-emerald-700 border border-emerald-100 hover:bg-emerald-100'
                }`}
              >
                Data Practice ({dpCount})
              </button>
            </div>
          </div>
        </div>

        {/* ✅ SCROLLABLE CONTAINER */}
        <div
          className="overflow-y-auto overflow-x-auto"
          style={{ maxHeight: 'calc(100vh - 215px)' }}
        >
          <table className="min-w-full text-sm">
            {/* ✨ Sticky Header */}
            <thead className="bg-gray-50 sticky top-0 z-30 shadow-sm">
              <tr>
                <th className="px-6 py-4 text-left font-semibold text-gray-700 text-xs uppercase tracking-wide">
                  ID
                </th>
                <th className="px-6 py-4 text-left font-semibold text-gray-700 text-xs uppercase tracking-wide">
                  Name
                </th>
                <th className="px-6 py-4 text-left font-semibold text-gray-700 text-xs uppercase tracking-wide">
                  Role
                </th>
                <th className="px-6 py-4 text-left font-semibold text-gray-700 text-xs uppercase tracking-wide">
                  Bucket
                </th>
                <th className="px-6 py-4 text-left font-semibold text-gray-700 text-xs uppercase tracking-wide">
                  Experience
                </th>
                <th className="px-6 py-4 text-left font-semibold text-gray-700 text-xs uppercase tracking-wide">
                  Top Skills
                </th>
                <th className="px-6 py-4 text-left font-semibold text-gray-700 text-xs uppercase tracking-wide">
                  Email
                </th>
                {/* 👇 NEW COLUMN */}
                <th className="px-6 py-4 text-left font-semibold text-gray-700 text-xs uppercase tracking-wide">
                  Bench Status
                </th>
                <th className="px-6 py-4 text-left font-semibold text-gray-700 text-xs uppercase tracking-wide">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filteredCandidates.map((c, index) => {
                const parsed = c.parsed || {}
                const isExpanded = expandedId === c.id
                const bucket = c.role_bucket || 'data_practice'
                const prof = computeSkillProficiency(parsed)

                return (
                  <React.Fragment key={c.id}>
                    {/* ✨ Animated Row */}
                    <tr
                      className="group cursor-pointer transition-all duration-300 hover:bg-gray-50 animate-fade-in"
                      style={{ animationDelay: `${index * 50}ms` }}
                      onClick={() => setExpandedId(isExpanded ? null : c.id)}
                    >
                      <td className="px-6 py-4">
                        {/* ✅ Pure Emerald ID Badge */}
                        <div className="w-8 h-8 rounded-lg bg-emerald-500 flex items-center justify-center text-white font-semibold text-xs shadow-md group-hover:shadow-lg group-hover:scale-110 transition-all duration-300">
                          {c.id}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="font-semibold text-gray-900 group-hover:text-emerald-600 transition-colors duration-300">
                          {c.full_name || parsed.candidate_name || 'Unknown'}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-gray-600 text-sm group-hover:text-gray-900 transition-colors duration-300">
                          {c.primary_role || parsed.primary_role || '—'}
                        </span>
                      </td>
                      {/* ✨ NEW: Bucket Column */}
                      <td className="px-6 py-4">
                        {bucket === 'data_scientist' ? (
                          <span className="px-3 py-1.5 bg-blue-100 text-blue-700 rounded-lg text-xs font-semibold border border-blue-200 whitespace-nowrap transition-all duration-300 hover:bg-blue-200 hover:scale-105">
                            Data Scientist
                          </span>
                        ) : (
                          <span className="px-3 py-1.5 bg-emerald-100 text-emerald-700 rounded-lg text-xs font-semibold border border-emerald-200 whitespace-nowrap transition-all duration-300 hover:bg-emerald-200 hover:scale-105">
                            Data Practice
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></div>
                          <span className="font-medium text-gray-700 text-sm">
                            {c.total_experience_years || parsed.total_experience_years || 0} years
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="space-y-2">
                          {prof.advanced.length > 0 ? (
                            <div>
                              <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
                                Advanced
                              </div>
                              {renderSkillChips(
                                prof.advanced,
                                'bg-emerald-50 text-emerald-700 border-emerald-200'
                              )}
                            </div>
                          ) : null}

                          {prof.intermediate.length > 0 ? (
                            <div>
                              <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
                                Intermediate
                              </div>
                              {renderSkillChips(
                                prof.intermediate,
                                'bg-yellow-50 text-yellow-800 border-yellow-200'
                              )}
                            </div>
                          ) : null}

                          {prof.advanced.length === 0 && prof.intermediate.length === 0 ? (
                            <div>
                              <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
                                Skills
                              </div>
                              {renderSkillChips(
                                (parsed.primary_skills || []).map((s) => ({ name: s, count: 1 })),
                                'bg-gray-50 text-gray-700 border-gray-200'
                              )}
                            </div>
                          ) : null}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-gray-500 text-sm">
                        {c.email || parsed.email || '—'}
                      </td>
                      {/* 👇 NEW: Bench Toggle Cell */}
                      <td className="px-6 py-4">
                        <BenchToggle
                          candidateId={c.id}
                          initialValue={c.on_bench ?? true}
                          onUpdate={(id, newValue) => {
                            console.log(`Bench status updated for candidate ${id}: ${newValue}`)
                          }}
                        />
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              setExpandedId(isExpanded ? null : c.id)
                            }}
                            className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all duration-300 transform hover:scale-105 active:scale-95 ${
                              isExpanded
                                ? 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                : 'bg-gradient-to-r from-emerald-500 to-yellow-500 text-white hover:shadow-lg hover:from-emerald-600 hover:to-yellow-600'
                            }`}
                          >
                            {isExpanded ? (
                              <span className="flex items-center gap-1">
                                Hide <span className="inline-block transition-transform duration-300 rotate-180">▼</span>
                              </span>
                            ) : (
                              <span className="flex items-center gap-1">
                                View <span className="inline-block transition-transform duration-300">▼</span>
                              </span>
                            )}
                          </button>

                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              deleteCandidate(c.id, c.full_name || parsed.candidate_name)
                            }}
                            className="px-4 py-2 rounded-xl text-xs font-semibold transition-all duration-300 transform hover:scale-105 active:scale-95 bg-red-50 text-red-700 border border-red-200 hover:bg-red-100"
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>

                    {/* ✨ Animated Expanded Section - FULLY SCROLLABLE */}
                    {isExpanded && (
                      <tr className="bg-gray-50 animate-expand-down">
                        <td colSpan="9" className="px-0 py-0">
                          <div className="px-8 py-8 animate-fade-in">
                            <div className="space-y-6 w-full">

                              {/* Skill Proficiency (from projects) */}
                              {(prof.advanced.length > 0 || prof.intermediate.length > 0 || prof.beginner.length > 0) && (
                                <div
                                  className="rounded-2xl bg-white p-6 shadow-sm border border-gray-200 transition-all duration-300 hover:shadow-md hover:border-emerald-200 animate-slide-up"
                                  style={{ animationDelay: '150ms' }}
                                >
                                  <h4 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                                    <span className="w-1 h-4 bg-gradient-to-b from-emerald-500 to-yellow-500 rounded-full"></span>
                                    Skill Proficiency (derived from projects)
                                  </h4>

                                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                    <div className="rounded-xl border border-emerald-100 bg-emerald-50/40 p-4">
                                      <div className="text-xs font-semibold text-emerald-800 mb-2">
                                        Advanced ({prof.advanced.length})
                                      </div>
                                      {prof.advanced.length ? (
                                        <div className="flex flex-wrap gap-2">
                                          {prof.advanced.slice(0, 12).map((it, idx) => (
                                            <span
                                              key={idx}
                                              title={`${it.name} • ${it.count} project(s)`}
                                              className="px-3 py-1.5 bg-white text-emerald-800 rounded-xl text-xs font-medium border border-emerald-200"
                                            >
                                              {it.name}
                                            </span>
                                          ))}
                                        </div>
                                      ) : (
                                        <div className="text-xs text-emerald-700/70">No skills reached the advanced threshold yet.</div>
                                      )}
                                    </div>

                                    <div className="rounded-xl border border-yellow-100 bg-yellow-50/40 p-4">
                                      <div className="text-xs font-semibold text-yellow-800 mb-2">
                                        Intermediate ({prof.intermediate.length})
                                      </div>
                                      {prof.intermediate.length ? (
                                        <div className="flex flex-wrap gap-2">
                                          {prof.intermediate.slice(0, 12).map((it, idx) => (
                                            <span
                                              key={idx}
                                              title={`${it.name} • ${it.count} project(s)`}
                                              className="px-3 py-1.5 bg-white text-yellow-800 rounded-xl text-xs font-medium border border-yellow-200"
                                            >
                                              {it.name}
                                            </span>
                                          ))}
                                        </div>
                                      ) : (
                                        <div className="text-xs text-yellow-700/70">No intermediate skills found.</div>
                                      )}
                                    </div>

                                    <div className="rounded-xl border border-gray-200 bg-gray-50/40 p-4">
                                      <div className="text-xs font-semibold text-gray-700 mb-2">
                                        Beginner ({prof.beginner.length})
                                      </div>
                                      {prof.beginner.length ? (
                                        <div className="flex flex-wrap gap-2">
                                          {prof.beginner.slice(0, 12).map((it, idx) => (
                                            <span
                                              key={idx}
                                              title={`${it.name} • ${it.count} project(s)`}
                                              className="px-3 py-1.5 bg-white text-gray-700 rounded-xl text-xs font-medium border border-gray-200"
                                            >
                                              {it.name}
                                            </span>
                                          ))}
                                        </div>
                                      ) : (
                                        <div className="text-xs text-gray-500">No beginner skills found.</div>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              )}

                              {/* Experience Summary */}
                              {(parsed.experience_summary || parsed.professional_summary) && (
                                <div className="rounded-2xl bg-white p-6 shadow-sm border border-gray-200 transition-all duration-300 hover:shadow-md hover:border-emerald-200 animate-slide-up" style={{ animationDelay: '100ms' }}>
                                  <h4 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
                                    <span className="w-1 h-4 bg-gradient-to-b from-emerald-500 to-yellow-500 rounded-full"></span>
                                    Professional Summary
                                  </h4>
                                  <p className="text-sm text-gray-600 leading-relaxed">
                                    {parsed.experience_summary || parsed.professional_summary}
                                  </p>
                                </div>
                              )}

                              {/* Primary Skills */}
                              {parsed.primary_skills && parsed.primary_skills.length > 0 && (
                                <div className="rounded-2xl bg-white p-6 shadow-sm border border-gray-200 transition-all duration-300 hover:shadow-md hover:border-emerald-200 animate-slide-up" style={{ animationDelay: '200ms' }}>
                                  <h4 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                                    <span className="w-1 h-4 bg-gradient-to-b from-emerald-500 to-yellow-500 rounded-full"></span>
                                    Primary Skills
                                  </h4>
                                  <div className="flex flex-wrap gap-2">
                                    {parsed.primary_skills.map((skill, idx) => (
                                      <span
                                        key={idx}
                                        className="px-4 py-2 bg-gradient-to-r from-emerald-500 to-yellow-500 text-white rounded-xl text-sm font-medium transition-all duration-300 hover:shadow-lg hover:scale-105 animate-fade-in"
                                        style={{ animationDelay: `${300 + idx * 50}ms` }}
                                      >
                                        {skill}
                                      </span>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {/* Projects */}
                              {parsed.projects && parsed.projects.length > 0 && (
                                <div className="rounded-2xl bg-white p-6 shadow-sm border border-gray-200 transition-all duration-300 hover:shadow-md hover:border-emerald-200 animate-slide-up" style={{ animationDelay: '300ms' }}>
                                  <h4 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                                    <span className="w-1 h-4 bg-gradient-to-b from-emerald-500 to-yellow-500 rounded-full"></span>
                                    Projects ({parsed.projects.length})
                                  </h4>
                                  <div className="space-y-6">
                                    {parsed.projects.map((proj, idx) => (
                                      <div 
                                        key={idx} 
                                        className="pb-6 border-b border-gray-100 last:border-b-0 transition-all duration-300 hover:bg-gray-50 hover:px-4 hover:py-3 rounded-xl animate-fade-in"
                                        style={{ animationDelay: `${400 + idx * 100}ms` }}
                                      >
                                        <div className="flex items-start justify-between mb-3">
                                          <h5 className="font-semibold text-gray-900 text-base">
                                            {proj.name || `Project ${idx + 1}`}
                                          </h5>
                                          {proj.role && (
                                            <span className="px-3 py-1 bg-emerald-100 text-emerald-700 rounded-lg text-xs font-medium transition-all duration-300 hover:bg-emerald-200 whitespace-nowrap ml-3">
                                              {proj.role}
                                            </span>
                                          )}
                                        </div>
                                        
                                        {proj.description && (
                                          <p className="text-sm text-gray-600 mb-4">
                                            {proj.description}
                                          </p>
                                        )}
                                        
                                        {proj.responsibilities && proj.responsibilities.length > 0 && (
                                          <div className="mb-4">
                                            <div className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">
                                              Key Responsibilities
                                            </div>
                                            <ul className="space-y-2 text-sm text-gray-600">
                                              {proj.responsibilities.map((resp, rIdx) => (
                                                <li key={rIdx} className="flex items-start gap-2 transition-all duration-300 hover:translate-x-1">
                                                  <span className="text-emerald-500 mt-1">•</span>
                                                  <span>{resp}</span>
                                                </li>
                                              ))}
                                            </ul>
                                          </div>
                                        )}
                                        
                                        {(proj.technical_tools || proj.technologies_used) && 
                                         (proj.technical_tools || proj.technologies_used).length > 0 && (
                                          <div>
                                            <div className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">
                                              Technologies Used
                                            </div>
                                            <div className="flex flex-wrap gap-2">
                                              {(proj.technical_tools || proj.technologies_used).map((tool, tIdx) => (
                                                <span
                                                  key={tIdx}
                                                  className="px-3 py-1 bg-gray-100 text-gray-700 rounded-lg text-xs font-medium transition-all duration-300 hover:bg-emerald-100 hover:text-emerald-700 hover:scale-105"
                                                >
                                                  {tool}
                                                </span>
                                              ))}
                                            </div>
                                          </div>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {/* Hierarchical Skills */}
                              {parsed.skill_categories && parsed.skill_categories.length > 0 && (
                                <div className="rounded-2xl bg-white p-6 shadow-sm border border-gray-200 transition-all duration-300 hover:shadow-md hover:border-emerald-200 animate-slide-up" style={{ animationDelay: '400ms' }}>
                                  <h4 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                                    <span className="w-1 h-4 bg-gradient-to-b from-emerald-500 to-yellow-500 rounded-full"></span>
                                    Technical Skills
                                  </h4>
                                  <div className="space-y-4">
                                    {parsed.skill_categories.map((cat, idx) => (
                                      <div key={idx} className="animate-fade-in" style={{ animationDelay: `${500 + idx * 100}ms` }}>
                                        <div className="text-xs font-semibold text-gray-700 mb-2">
                                          {cat.category}
                                        </div>
                                        <div className="flex flex-wrap gap-2">
                                          {(cat.skills || []).map((skill, sIdx) => (
                                            <span
                                              key={sIdx}
                                              className="px-3 py-1 bg-gray-50 text-gray-600 rounded-lg text-xs font-medium border border-gray-200 transition-all duration-300 hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-700 hover:scale-105"
                                            >
                                              {skill}
                                            </span>
                                          ))}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {/* Work Experience */}
                              {parsed.work_experiences && parsed.work_experiences.length > 0 && (
                                <div className="rounded-2xl bg-white p-6 shadow-sm border border-gray-200 transition-all duration-300 hover:shadow-md hover:border-emerald-200 animate-slide-up" style={{ animationDelay: '500ms' }}>
                                  <h4 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                                    <span className="w-1 h-4 bg-gradient-to-b from-emerald-500 to-yellow-500 rounded-full"></span>
                                    Work Experience
                                  </h4>
                                  <div className="space-y-5">
                                    {parsed.work_experiences.map((exp, idx) => (
                                      <div key={idx} className="pb-5 border-b border-gray-100 last:border-b-0 transition-all duration-300 hover:bg-gray-50 hover:px-3 hover:py-2 rounded-xl animate-fade-in" style={{ animationDelay: `${600 + idx * 100}ms` }}>
                                        <div className="font-semibold text-gray-900">
                                          {exp.job_title || 'Position'}
                                        </div>
                                        <div className="text-sm text-gray-500 mt-1">
                                          {exp.company_name || 'Company'} • {exp.start_date || '?'} - {exp.end_date || 'Present'}
                                        </div>
                                        {exp.responsibilities && exp.responsibilities.length > 0 && (
                                          <ul className="mt-3 space-y-1.5 text-sm text-gray-600">
                                            {exp.responsibilities.slice(0, 5).map((resp, rIdx) => (
                                              <li key={rIdx} className="flex items-start gap-2 transition-all duration-300 hover:translate-x-1">
                                                <span className="text-emerald-500 mt-1">•</span>
                                                <span>{resp}</span>
                                              </li>
                                            ))}
                                          </ul>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {/* Certifications */}
                              {parsed.certifications && parsed.certifications.length > 0 && (
                                <div className="rounded-2xl bg-white p-6 shadow-sm border border-gray-200 transition-all duration-300 hover:shadow-md hover:border-emerald-200 animate-slide-up" style={{ animationDelay: '600ms' }}>
                                  <h4 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                                    <span className="w-1 h-4 bg-gradient-to-b from-emerald-500 to-yellow-500 rounded-full"></span>
                                    Certifications & Training
                                  </h4>
                                  <div className="space-y-4">
                                    {parsed.certifications.map((cert, idx) => (
                                      <div key={idx} className="flex items-start gap-4 pb-4 border-b border-gray-100 last:border-b-0 transition-all duration-300 hover:bg-gray-50 hover:px-3 hover:py-2 rounded-xl animate-fade-in" style={{ animationDelay: `${700 + idx * 100}ms` }}>
                                        <div className="w-10 h-10 rounded-full bg-emerald-500 flex items-center justify-center text-white font-semibold text-sm flex-shrink-0 shadow-md transition-all duration-300 hover:shadow-lg hover:scale-110">
                                          {idx + 1}
                                        </div>
                                        <div className="flex-1">
                                          <div className="font-semibold text-gray-900 text-sm">
                                            {cert.name}
                                          </div>
                                          {cert.issued_by && (
                                            <div className="text-xs text-gray-500 mt-1">
                                              {cert.issued_by}
                                            </div>
                                          )}
                                          {cert.issued_date && (
                                            <div className="text-xs text-gray-400 mt-0.5">
                                              {cert.issued_date}
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {/* Education */}
                              {parsed.education && parsed.education.length > 0 && (
                                <div className="rounded-2xl bg-white p-6 shadow-sm border border-gray-200 transition-all duration-300 hover:shadow-md hover:border-emerald-200 animate-slide-up" style={{ animationDelay: '700ms' }}>
                                  <h4 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                                    <span className="w-1 h-4 bg-gradient-to-b from-emerald-500 to-yellow-500 rounded-full"></span>
                                    Education
                                  </h4>
                                  <div className="space-y-3">
                                    {parsed.education.map((edu, idx) => (
                                      <div key={idx} className="transition-all duration-300 hover:bg-gray-50 hover:px-3 hover:py-2 rounded-xl animate-fade-in" style={{ animationDelay: `${800 + idx * 100}ms` }}>
                                        <div className="font-semibold text-gray-900 text-sm">
                                          {edu.degree || edu.qualification} in {edu.field_of_study || edu.field}
                                        </div>
                                        <div className="text-sm text-gray-500 mt-1">
                                          {edu.institution} • {edu.graduation_year || edu.year}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ✨ Custom CSS for Animations */}
      <style>{`
        @keyframes fade-in {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        
        @keyframes slide-up {
          from { 
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        
        @keyframes slide-in-left {
          from {
            opacity: 0;
            transform: translateX(-30px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }
        
        @keyframes slide-in-right {
          from {
            opacity: 0;
            transform: translateX(30px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }
        
        @keyframes expand-down {
          from {
            opacity: 0;
            max-height: 0;
          }
          to {
            opacity: 1;
            max-height: 5000px;
          }
        }
        
        @keyframes bounce-slow {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-10px); }
        }
        
        .animate-fade-in {
          animation: fade-in 0.5s ease-out forwards;
        }
        
        .animate-slide-up {
          animation: slide-up 0.6s ease-out forwards;
        }
        
        .animate-slide-in-left {
          animation: slide-in-left 0.6s ease-out forwards;
        }
        
        .animate-slide-in-right {
          animation: slide-in-right 0.6s ease-out forwards;
        }
        
        .animate-expand-down {
          animation: expand-down 0.4s ease-out forwards;
        }
        
        .animate-bounce-slow {
          animation: bounce-slow 2s ease-in-out infinite;
        }
        
        /* Smooth scrollbar */
        ::-webkit-scrollbar {
          width: 8px;
          height: 8px;
        }
        
        ::-webkit-scrollbar-track {
          background: #f1f1f1;
          border-radius: 10px;
        }
        
        ::-webkit-scrollbar-thumb {
          background: #10b981;
          border-radius: 10px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
          background: #059669;
        }
      `}</style>
    </div>
  )
}
