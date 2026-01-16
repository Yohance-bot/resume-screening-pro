import { useState, useEffect } from 'react'
import { fetchDashboardStats } from '../services/api'
import { MagnifyingGlassIcon, SparklesIcon } from '@heroicons/react/24/outline'

const Home = () => {
  const [stats, setStats] = useState({ total_resumes: 0, total_jds: 0, pending: 0 })
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [explanation, setExplanation] = useState('')
  const [filtersApplied, setFiltersApplied] = useState({})
  const [searchMode, setSearchMode] = useState('smart') // 'smart' or 'basic'

  // 1) dashboard stats
  useEffect(() => {
    const loadStats = async () => {
      try {
        const data = await fetchDashboardStats()
        setStats(data)
      } catch (err) {
        console.error('Failed:', err)
      } finally {
        setLoading(false)
      }
    }
    loadStats()
  }, [])

  // 2) load all employees on mount
  useEffect(() => {
    const loadEmployees = async () => {
      try {
        const res = await fetch('http://localhost:5050/api/employees')
        const data = await res.json()
        if (res.ok) {
          setSearchResults(data.results || [])
          setHasSearched(true)
          setExplanation(
            `Showing all ${data.total ?? (data.results?.length || 0)} employees`
          )
          setFiltersApplied({})
        }
      } catch (err) {
        console.error('Failed to load employees:', err)
      } finally {
        setSearching(false)
      }
    }

    loadEmployees()
  }, [])

  const handleSmartSearch = async (e) => {
    e.preventDefault()
    if (!searchQuery.trim() || searchQuery.length < 3) return
    try {
      setSearching(true)
      const res = await fetch('http://localhost:5050/api/smart-search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchQuery }),
      })
      const data = await res.json()
      if (data.error) {
        console.error('Search error:', data.error)
        setSearchResults([])
        setExplanation('Search failed. Please try again.')
      } else {
        setSearchResults(data.results || [])
        setExplanation(data.explanation || '')
        setFiltersApplied(data.filters_applied || {})
      }
      setHasSearched(true)
    } catch (err) {
      console.error('Smart search failed:', err)
      setSearchResults([])
      setExplanation('Network error. Please try again.')
      setHasSearched(true)
    } finally {
      setSearching(false)
    }
  }

  const handleBasicSearch = async (e) => {
    e.preventDefault()
    if (!searchQuery.trim() || searchQuery.length < 2) return
    try {
      setSearching(true)
      const res = await fetch(
        `http://localhost:5050/api/search?q=${encodeURIComponent(searchQuery)}`
      )
      const data = await res.json()
      setSearchResults(data.results || [])
      setExplanation(`Found ${data.total || 0} matches for "${searchQuery}"`)
      setFiltersApplied({})
      setHasSearched(true)
    } catch (err) {
      console.error('Basic search failed:', err)
    } finally {
      setSearching(false)
    }
  }

  const clearSearch = () => {
    setSearchQuery('')
    setSearchResults([])
    setHasSearched(false)
    setExplanation('')
    setFiltersApplied({})
  }

  const exampleQueries = [
    "who's on bench in Chennai",
    'AWS certified developers',
    'Python engineers with 5+ years',
    'senior React developers in Bangalore',
    'data scientists with PhD',
  ]

  return (
    <div className="space-y-6">
      {/* TODO: stats cards using `stats` and `loading` */}

      {/* Top Bar */}
      <div className="px-6 pt-6 pb-3 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-emerald-50">
            AI‑Powered Smart Search
          </h1>
          <p className="text-xs text-emerald-100/80 mt-1">
            Find the right person on bench by skill, location, and experience.
          </p>
        </div>
        <div className="hidden md:flex items-center gap-2 text-xs text-emerald-100/80">
          <span
            onClick={() => setSearchMode('smart')}
            className={`px-2 py-1 rounded-full cursor-pointer border ${
              searchMode === 'smart'
                ? 'bg-emerald-400/30 border-emerald-300/60 text-emerald-50'
                : 'bg-emerald-900/40 border-emerald-700/60'
            }`}
          >
            Smart
          </span>
          <span
            onClick={() => setSearchMode('basic')}
            className={`px-2 py-1 rounded-full cursor-pointer border ${
              searchMode === 'basic'
                ? 'bg-emerald-400/30 border-emerald-300/60 text-emerald-50'
                : 'bg-emerald-900/40 border-emerald-700/60'
            }`}
          >
            Basic
          </span>
        </div>
      </div>

      {/* Search Card */}
      <div className="px-6 pb-4">
        <form
          onSubmit={searchMode === 'smart' ? handleSmartSearch : handleBasicSearch}
          className="rounded-2xl bg-emerald-950/40 border border-emerald-500/20 backdrop-blur-xl px-4 py-3 flex flex-wrap items-center gap-3"
        >
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="flex-1 bg-transparent outline-none text-sm text-emerald-50 placeholder:text-emerald-200/60"
            placeholder={
              searchMode === 'smart'
                ? 'Try: “who’s on bench in Chennai with AWS and 3+ years”'
                : 'Search by name, skill, or keyword'
            }
          />
          <button
            type="submit"
            disabled={searching}
            className="px-4 py-2 rounded-xl text-sm font-medium bg-emerald-400 text-emerald-950 shadow-lg shadow-emerald-900/60 disabled:opacity-60"
          >
            {searching ? 'Searching…' : 'Search'}
          </button>
          {hasSearched && (
            <button
              type="button"
              onClick={clearSearch}
              className="px-3 py-2 rounded-xl text-xs border border-emerald-400/50 text-emerald-100/90 hover:bg-emerald-400/10"
            >
              Clear
            </button>
          )}
        </form>

        {explanation && hasSearched && (
          <div className="mt-3 rounded-xl bg-white/10 border border-white/20 backdrop-blur-xl px-4 py-3 text-sm text-emerald-50/90">
            🤖 {explanation}
          </div>
        )}
      </div>

      {/* Search Results */}
      {hasSearched && (
        <div className="rounded-3xl bg-white/70 backdrop-blur-2xl border shadow-2xl overflow-hidden">
          {searchResults.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-lg font-semibold mb-2">No results found</p>
            </div>
          ) : (
            <SearchResultsTable results={searchResults} searchQuery={searchQuery} />
          )}
        </div>
      )}
    </div>
  )
}

const SearchResultsTable = ({ results, searchQuery }) => {
  const [expandedId, setExpandedId] = useState(null)
  const [candidates, setCandidates] = useState([])
  useEffect(() => {
    setCandidates(results || [])
  }, [results])
  const [statusFilter, setStatusFilter] = useState('all')

  const deleteCandidate = async (candidateId, candidateName) => {
    const ok = window.confirm(
      `Delete ${candidateName || 'this candidate'} (ID: ${candidateId})? This will permanently remove them from the database.`
    )
    if (!ok) return

    try {
      const res = await fetch(`http://localhost:5050/api/candidates/${candidateId}`, {
        method: 'DELETE',
      })
      if (res.ok) {
        setCandidates((prev) => prev.filter((c) => (c.id ?? c.candidate_id) !== candidateId))
        setExpandedId((prev) => (prev === candidateId ? null : prev))
      } else {
        const data = await res.json().catch(() => ({}))
        alert(data?.error || 'Failed to delete candidate')
      }
    } catch (err) {
      console.error('Failed to delete candidate:', err)
      alert('Failed to delete candidate')
    }
  }

  const toggleRow = (id) => {
    setExpandedId(expandedId === id ? null : id)
  }

  const updateStatus = async (candidateId, newStatus) => {
    try {
      const res = await fetch(
        `http://localhost:5050/api/candidate/${candidateId}/status`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: newStatus }),
        }
      )
      if (res.ok) {
        setCandidates(
          candidates.map((c) =>
            (c.id ?? c.candidate_id) === candidateId ? { ...c, status: newStatus } : c
          )
        )
      }
    } catch (err) {
      console.error('Failed to update status:', err)
    }
  }

  const filteredCandidates =
    statusFilter === 'all'
      ? candidates
      : candidates.filter((c) => (c.status || 'on_bench') === statusFilter)

  const getStatusBadge = (status) => {
    const styles = {
      on_bench: 'bg-green-100 text-green-700 border-green-300',
      allocated: 'bg-blue-100 text-blue-700 border-blue-300',
      unavailable: 'bg-gray-100 text-gray-700 border-gray-300',
    }
    const labels = {
      on_bench: '🟢 On Bench',
      allocated: '🔵 Allocated',
      unavailable: '⚪ Unavailable',
    }
    return { style: styles[status] || styles.on_bench, label: labels[status] || labels[status] }
  }

  return (
    <>
      <div className="px-6 py-3 bg-white/40 border-b border-white/20 flex items-center gap-2">
        <span className="text-xs font-semibold text-gray-600">Filter:</span>
        <button
          onClick={() => setStatusFilter('all')}
          className={`px-3 py-1 rounded-full text-xs font-semibold transition-all ${
            statusFilter === 'all'
              ? 'bg-emerald-600 text-white'
              : 'bg-white/60 text-gray-700 hover:bg-white/80'
          }`}
        >
          All ({candidates.length})
        </button>
        <button
          onClick={() => setStatusFilter('on_bench')}
          className={`px-3 py-1 rounded-full text-xs font-semibold transition-all ${
            statusFilter === 'on_bench'
              ? 'bg-green-600 text-white'
              : 'bg-white/60 text-gray-700 hover:bg-white/80'
          }`}
        >
          On Bench (
          {candidates.filter((c) => (c.status || 'on_bench') === 'on_bench').length})
        </button>
        <button
          onClick={() => setStatusFilter('allocated')}
          className={`px-3 py-1 rounded-full text-xs font-semibold transition-all ${
            statusFilter === 'allocated'
              ? 'bg-blue-600 text-white'
              : 'bg-white/60 text-gray-700 hover:bg-white/80'
          }`}
        >
          Allocated (
          {candidates.filter((c) => (c.status || 'on_bench') === 'allocated').length})
        </button>
      </div>

      {/* table body exactly as you pasted */}
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-xs uppercase tracking-wide text-emerald-100/60">
            <tr>
              <th className="w-8" />
              <th className="py-2 px-4 text-left">Name</th>
              <th className="py-2 px-4 text-left">Status</th>
              <th className="py-2 px-4 text-left">Contact</th>
              <th className="py-2 px-4 text-left">Top Skills</th>
              <th className="py-2 px-4 text-left">Latest Role</th>
              <th className="py-2 px-4 text-left">Total Exp</th>
              <th className="py-2 px-4 text-left">Certifications</th>
              <th className="py-2 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredCandidates.map((candidate) => {
              const normalized = {
                id: candidate.id ?? candidate.candidate_id,
                full_name:
                  candidate.full_name ||
                  candidate.name ||
                  candidate.candidate_name ||
                  '—',
                email: candidate.email || candidate.contact?.email || '',
                phone: candidate.phone || candidate.contact?.phone || '',
                skills: Array.isArray(candidate.skills)
                  ? candidate.skills
                  : typeof candidate.skills === 'string'
                  ? candidate.skills.split(',').map(s => s.trim())
                  : [],
                roles: candidate.roles || candidate.experience || [],
                education: candidate.education || [],
                certifications: candidate.certifications || [],
                summary: candidate.summary || candidate.profile_summary || '',
                status: candidate.status || 'on_bench',
                total_years_exp: candidate.total_years_exp ?? candidate.total_experience_years ?? 0,
              }
              const status = normalized.status
              const statusBadge = getStatusBadge(status)

              return (
                <>
                  <tr
                    key={normalized.id}
                    className="border-b border-white/10 hover:bg-emerald-50/5 transition-all cursor-pointer"
                    onClick={() => toggleRow(normalized.id)}
                  >
                    <td className="py-4 px-4 text-center">
                      <span className="text-emerald-600 font-bold text-lg">
                        {expandedId === normalized.id ? '−' : '+'}
                      </span>
                    </td>
                    <td className="py-4 px-4">
                      <div className="font-semibold text-gray-900">
                        {normalized.full_name}
                      </div>
                      <div className="text-xs text-gray-500">
                        ID: {normalized.id}
                      </div>
                    </td>

                    <td className="py-4 px-4">
                      <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium
    bg-emerald-400/10 text-emerald-700 border border-emerald-400/30">
                        <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.9)]" />
                        {statusBadge.label.replace(/^[^ ]+ /, '')}
                      </span>
                    </td>

                    <td className="py-4 px-4">
                      <div className="text-xs space-y-1">
                        {normalized.email && (
                          <div className="flex items-center gap-1">
                            <span className="text-gray-500">✉️</span>
                            <span className="text-blue-600 truncate max-w-[150px]">
                              {normalized.email}
                            </span>
                          </div>
                        )}
                        {normalized.phone && (
                          <div className="flex items-center gap-1">
                            <span className="text-gray-500">📞</span>
                            <span className="text-gray-700">
                              {normalized.phone}
                            </span>
                          </div>
                        )}
                      </div>
                    </td>

                    <td className="py-4 px-4">
                      <div className="flex flex-wrap gap-1">
                        {normalized.skills.slice(0, 4).map((skill, i) => (
                          <span
                            key={i}
                            className={`px-2 py-1 rounded-full text-[10px] font-semibold ${
                              skill
                                .toLowerCase()
                                .includes(searchQuery.toLowerCase())
                                ? 'bg-emerald-200 text-emerald-800'
                                : 'bg-gray-100 text-gray-700'
                            }`}
                          >
                            {skill}
                          </span>
                        ))}
                        {normalized.skills.length > 4 && (
                          <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded-full text-[10px] font-semibold">
                            +{normalized.skills.length - 4}
                          </span>
                        )}
                      </div>
                    </td>

                    <td className="py-4 px-4">
                      {normalized.roles.length > 0 ? (
                        <div>
                          <div className="font-medium text-gray-800 text-sm">
                            {normalized.roles[0].title || 'N/A'}
                          </div>
                          {normalized.roles[0].company && (
                            <div className="text-xs text-gray-500">
                              @ {normalized.roles[0].company}
                            </div>
                          )}
                        </div>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="py-4 px-4 text-xs text-emerald-900/90">
                      {(normalized.total_years_exp ?? 0).toFixed(1)} yrs
                    </td>
                    <td className="py-4 px-4 text-xs text-emerald-900/90">
                      {normalized.certifications.length > 0
                        ? (normalized.certifications[0].name ||
                           normalized.certifications[0].title ||
                           normalized.certifications[0].degree)
                        : '—'}
                    </td>

                    <td className="py-4 px-4 text-right">
                      <button
                        type="button"
                        className="px-3 py-1 rounded-lg text-xs font-semibold border border-red-300 text-red-700 bg-red-50 hover:bg-red-100"
                        onClick={(e) => {
                          e.stopPropagation()
                          deleteCandidate(normalized.id, normalized.full_name)
                        }}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>

                  {expandedId === normalized.id && (
                    <tr className="bg-gradient-to-r from-emerald-50/50 to-teal-50/50">
                      <td colSpan="9" className="py-6 px-8">
                        <div className="mt-3 rounded-lg bg-white shadow-sm border border-gray-200 p-4">

                          {/* Basic info */}
                          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                            <div>
                              <div className="text-gray-500">Email</div>
                              <div className="font-medium">{normalized.email || '—'}</div>
                            </div>
                            <div>
                              <div className="text-gray-500">Phone</div>
                              <div className="font-medium">{normalized.phone || '—'}</div>
                            </div>
                            <div>
                              <div className="text-gray-500">Total Experience</div>
                              <div className="font-medium">
                                {(normalized.total_years_exp ?? 0).toFixed(2)} yrs
                              </div>
                            </div>
                          </div>

                          {/* Skills */}
                          <div className="mt-4">
                            <div className="text-gray-500 text-sm mb-1">Top Skills</div>
                            <div className="flex flex-wrap gap-2">
                              {(normalized.skills || []).slice(0, 8).map((skill, i) => (
                                <span
                                  key={i}
                                  className="px-2 py-1 text-xs rounded-full bg-emerald-50 text-emerald-700"
                                >
                                  {skill}
                                </span>
                              ))}
                              {(!normalized.skills || normalized.skills.length === 0) && (
                                <span className="text-sm text-gray-400">
                                  No skills extracted
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Latest roles */}
                          <div className="mt-4">
                            <div className="text-gray-500 text-sm mb-2">Latest Roles</div>
                            <div className="space-y-2">
                              {(normalized.roles || []).slice(0, 3).map((role, idx) => (
                                <div
                                  key={idx}
                                  className="border border-gray-100 rounded-md p-2 text-sm"
                                >
                                  <div className="font-medium">
                                    {role.title || role.job_title || 'Role'}
                                    {(role.company || role.company_name) && (
                                      <span className="text-gray-500">
                                        {' '}
                                        @ {role.company || role.company_name}
                                      </span>
                                    )}
                                  </div>
                                  {role.technologies_used?.length > 0 && (
                                    <div className="mt-1 text-xs text-gray-600">
                                      Tech: {role.technologies_used.slice(0, 6).join(', ')}
                                    </div>
                                  )}
                                  {role.responsibilities?.length > 0 && (
                                    <div className="mt-1 text-xs text-gray-600">
                                      {role.responsibilities[0]}
                                    </div>
                                  )}
                                </div>
                              ))}
                              {(!normalized.roles || normalized.roles.length === 0) && (
                                <span className="text-sm text-gray-400">No roles parsed</span>
                              )}
                            </div>
                          </div>

                          {/* Education */}
                          <div className="mt-4">
                            <div className="text-gray-500 text-sm mb-2">Education</div>
                            <div className="space-y-1 text-sm">
                              {(normalized.education || []).slice(0, 3).map((edu, idx) => (
                                <div key={idx}>
                                  <span className="font-medium">
                                    {edu.degree || edu.title || '—'}
                                  </span>
                                  {edu.institution && (
                                    <span className="text-gray-500">
                                      {' '}
                                      · {edu.institution}
                                    </span>
                                  )}
                                  {edu.field_of_study && (
                                    <span className="text-gray-500">
                                      {' '}
                                      · {edu.field_of_study}
                                    </span>
                                  )}
                                </div>
                              ))}
                              {(!normalized.education || normalized.education.length === 0) && (
                                <span className="text-sm text-gray-400">
                                  No education parsed
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Certifications */}
                          <div className="mt-4">
                            <div className="text-gray-500 text-sm mb-2">Certifications</div>
                            <div className="space-y-1 text-sm">
                              {normalized.certifications.slice(0, 5).map((cert, idx) => (
                                <div key={idx}>
                                  <span className="font-medium">
                                    {cert.name || cert.title || cert.degree || 'Certification'}
                                  </span>
                                  {cert.issuing_organization && (
                                    <span className="text-gray-500">
                                      {' '}
                                      · {cert.issuing_organization}
                                    </span>
                                  )}
                                  {cert.date_obtained && (
                                    <span className="text-gray-500">
                                      {' '}
                                      · {cert.date_obtained}
                                    </span>
                                  )}
                                </div>
                              ))}
                              {normalized.certifications.length === 0 && (
                                <span className="text-sm text-gray-400">
                                  No certifications parsed
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Projects */}
                          <div className="mt-4">
                            <div className="text-gray-500 text-sm mb-2">Projects</div>
                            <div className="space-y-2 text-sm">
                              {(candidate.projects || []).slice(0, 3).map((project, idx) => (
                                <div
                                  key={idx}
                                  className="border border-gray-100/60 rounded-md p-2 bg-emerald-50/5"
                                >
                                  <div className="font-medium">
                                    {project.name || 'Project'}
                                  </div>
                                  {project.technologies_used &&
                                    project.technologies_used.length > 0 && (
                                      <div className="mt-1 text-xs text-gray-600">
                                        Tech:{' '}
                                        {project.technologies_used
                                          .slice(0, 6)
                                          .join(', ')}
                                      </div>
                                    )}
                                  {project.description && (
                                    <div className="mt-1 text-xs text-gray-600">
                                      {project.description}
                                    </div>
                                  )}
                                </div>
                              ))}
                              {(!candidate.projects ||
                                candidate.projects.length === 0) && (
                                <span className="text-sm text-gray-400">
                                  No projects parsed
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Summary */}
                          <div className="mt-4">
                            <div className="text-gray-500 text-sm mb-1">Summary</div>
                            <p className="text-sm text-gray-700">
                              {normalized.summary || 'No summary available.'}
                            </p>
                          </div>

                        </div>
                      </td>
                    </tr>
                  )}
                </>
              )
            })}
          </tbody>
        </table>
      </div>
    </>
  )
}

export default Home
