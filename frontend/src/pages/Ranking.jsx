import { useEffect, useState } from 'react'
import FinalReview from './FinalReview'
import { fetchJds, fetchCandidates, runScreening1, runScreening2, runScreening3, runScreening4 } from '../services/api'

const Ranking = () => {
  const [jds, setJds] = useState([])
  const [selectedJdId, setSelectedJdId] = useState(null)
  const [jd, setJd] = useState(null)
  const [candidates, setCandidates] = useState([])
  const [screen1, setScreen1] = useState([])
  const [screen2, setScreen2] = useState([])
  const [screen3, setScreen3] = useState([])
  const [screen4, setScreen4] = useState([])
  const [loading1, setLoading1] = useState(false)
  const [loading2, setLoading2] = useState(false)
  const [loading3, setLoading3] = useState(false)
  const [loading4, setLoading4] = useState(false)
  const [error, setError] = useState('')
  const [showFinalReview, setShowFinalReview] = useState(false)
  const [sessionId, setSessionId] = useState(null)

  useEffect(() => {
    const loadData = async () => {
      try {
        const [jdsData, cands] = await Promise.all([
          fetchJds(),
          fetchCandidates(),
        ])

        setJds(jdsData)
        
        if (jdsData.length > 0) {
          setSelectedJdId(jdsData[0].id)
          setJd(jdsData[0])
        }

        const mapped = (cands || []).map((c) => {
          const parsed = c.parsed || {}
          const sections = parsed.sections || {}

          return {
            id: c.id,
            full_name: c.full_name,
            email: c.email,
            phone: c.phone,
            raw_text: c.raw_text,
            skills: parsed.skills || sections.skills || [],
            roles: parsed.roles || sections.experience || [],
            summary: parsed.summary || '',
            ...parsed,
          }
        })
        setCandidates(mapped)
      } catch (err) {
        console.error(err)
        setError('Failed to load JD or candidates')
      }
    }

    loadData()
  }, [])

  const handleScreening1 = async () => {
    if (!jd || !candidates.length) {
      setError('Need at least one JD and one candidate')
      return
    }

    try {
      setLoading1(true)
      setError('')
      const data = await runScreening1(
        {
          required_skills: jd.required_skills || [],
          bonus_skills: jd.bonus_skills || [],
        },
        candidates,
      )
      setScreen1(data.results || [])
    } catch (err) {
      setError(err.message || 'Screening 1 failed')
    } finally {
      setLoading1(false)
    }
  }

  const handleScreening2 = async () => {
    if (!jd || !screen1.length) {
      setError('Run Screening 1 first')
      return
    }

    try {
      setLoading2(true)
      setError('')
      const top = screen1.slice(0, 10).map((r) => r.candidate)
      const data = await runScreening2(
        {
          title: jd.title,
          domain: jd.domain,
          required_skills: jd.required_skills || [],
        },
        top,
      )
      setScreen2(data.results || [])
    } catch (err) {
      setError(err.message || 'Screening 2 failed')
    } finally {
      setLoading2(false)
    }
  }

  const handleScreening3 = async () => {
    if (!jd || !screen2.length) {
      setError('Run Screening 2 first')
      return
    }

    try {
      setLoading3(true)
      setError('')
      const top = screen2.slice(0, 10).map((r) => r.candidate)
      const data = await runScreening3(
        {
          title: jd.title,
          domain: jd.domain,
          required_skills: jd.required_skills || [],
          bonus_skills: jd.bonus_skills || [],
        },
        top,
      )
      setScreen3(data.results || [])
    } catch (err) {
      setError(err.message || 'Screening 3 failed')
    } finally {
      setLoading3(false)
    }
  }

  const handleScreening4 = async () => {
    if (!jd || !screen3.length) {
      setError('Run Screening 3 first')
      return
    }

    try {
      setLoading4(true)
      setError('')
      const top = screen3.slice(0, 5).map((r) => ({
        ...r.candidate,
        matrix: r.matrix,
        matrix_score: r.matrix_score,
      }))
      const data = await runScreening4(
        {
          title: jd.title,
          domain: jd.domain,
          required_skills: jd.required_skills || [],
          bonus_skills: jd.bonus_skills || [],
        },
        top,
      )
      setScreen4(data.results || [])
      
      const sid = `session_${Date.now()}`
      setSessionId(sid)
      
      await fetch('http://localhost:5050/api/save-final-review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sid: sid,
          jd: jd,
          results: data.results || []
        })
      })
    } catch (err) {
      setError(err.message || 'Screening 4 failed')
    } finally {
      setLoading4(false)
    }
  }

  if (showFinalReview) {
    return (
      <div className="space-y-6 p-6">
        <button 
          onClick={() => setShowFinalReview(false)}
          className="px-5 py-3 bg-gradient-to-r from-gray-600 to-gray-700 text-white rounded-xl hover:from-gray-700 hover:to-gray-800 transition-all shadow-lg flex items-center gap-2 font-semibold"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Screenings
        </button>
        <FinalReview sessionId={sessionId} />
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-4xl font-extrabold tracking-tight text-emerald-900">Ranking</h1>
        <p className="text-sm text-emerald-700 mt-1">4-stage screening pipeline with AI audit</p>
      </div>

      {/* JD Selector */}
      <div className="p-6 rounded-3xl bg-white/60 backdrop-blur-xl border border-white/20 shadow-xl">
        <h2 className="text-lg font-bold text-gray-900 mb-3">📋 Select Job Description</h2>
        
        {jds.length === 0 ? (
          <div className="text-sm text-gray-600 bg-yellow-50 border border-yellow-200 rounded-xl p-4">
            ⚠️ No job descriptions found. Upload a JD first in the "JD Upload" tab.
          </div>
        ) : (
          <>
            <CustomDropdown
              jds={jds}
              selectedJdId={selectedJdId}
              onSelect={(id) => {
                setSelectedJdId(id)
                const selectedJd = jds.find(j => j.id === id)
                setJd(selectedJd)
                setScreen1([])
                setScreen2([])
                setScreen3([])
                setScreen4([])
                setError('')
              }}
            />

            {jd && (
              <div className="mt-4 p-5 bg-white/80 rounded-xl border border-gray-200">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4 pb-4 border-b border-gray-200">
                  <div>
                    <div className="text-xs text-gray-500 mb-1">Title</div>
                    <div className="font-semibold text-gray-900">{jd.title}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500 mb-1">Domain</div>
                    <div className="font-semibold text-gray-900">{jd.domain}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500 mb-1">Min Experience</div>
                    <div className="font-semibold text-gray-900">{jd.min_experience_years} years</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500 mb-1">Candidates</div>
                    <div className="font-semibold text-emerald-700">{candidates.length}</div>
                  </div>
                </div>

                <div className="mb-3">
                  <div className="text-xs font-semibold text-gray-700 mb-2">
                    Required Skills ({(jd.required_skills || []).length})
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {(jd.required_skills || []).map((skill, i) => (
                      <span
                        key={i}
                        className="px-2 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg text-xs font-medium"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>

                {jd.bonus_skills && jd.bonus_skills.length > 0 && (
                  <div>
                    <div className="text-xs font-semibold text-gray-700 mb-2">
                      Bonus Skills ({jd.bonus_skills.length})
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {jd.bonus_skills.map((skill, i) => (
                        <span
                          key={i}
                          className="px-2 py-1 bg-gray-50 text-gray-700 border border-gray-200 rounded-lg text-xs font-medium"
                        >
                          {skill}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* Screening Buttons */}
      <div className="grid grid-cols-4 gap-4">
        <button
          onClick={handleScreening1}
          disabled={loading1 || !candidates.length || !jd}
          className="px-4 py-3 bg-emerald-600 text-white rounded-xl font-semibold hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
        >
          {loading1 ? 'Running...' : 'Run Screening 1'}
        </button>

        <button
          onClick={handleScreening2}
          disabled={loading2 || !screen1.length}
          className="px-4 py-3 bg-emerald-600 text-white rounded-xl font-semibold hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
        >
          {loading2 ? 'Running...' : 'Run Screening 2'}
        </button>

        <button
          onClick={handleScreening3}
          disabled={loading3 || !screen2.length}
          className="px-4 py-3 bg-emerald-600 text-white rounded-xl font-semibold hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
        >
          {loading3 ? 'Running...' : 'Run Screening 3'}
        </button>

        <button
          onClick={handleScreening4}
          disabled={loading4 || !screen3.length}
          className="px-4 py-3 bg-emerald-600 text-white rounded-xl font-semibold hover:bg-pink-emerald disabled:opacity-40 disabled:cursor-not-allowed transition-all"
        >
          {loading4 ? 'Running...' : 'Run Screening 4'}
        </button>
      </div>

      {error && <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">{error}</div>}

      {/* Screening 1 Results */}
      {screen1.length > 0 && (
        <div className="p-6 bg-white rounded-xl shadow-lg border border-gray-200">
          <h2 className="text-xl font-semibold mb-4 text-gray-900">Screening 1 – Tech Stack</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b-2 border-gray-300">
                  <th className="py-3 px-4 text-left font-semibold text-gray-700">Candidate</th>
                  <th className="py-3 px-4 text-left font-semibold text-gray-700">Tech Score</th>
                  <th className="py-3 px-4 text-left font-semibold text-gray-700">Confidence</th>
                  <th className="py-3 px-4 text-left font-semibold text-gray-700">Matched</th>
                  <th className="py-3 px-4 text-left font-semibold text-gray-700">Missing</th>
                </tr>
              </thead>
              <tbody>
                {screen1.map((r, idx) => (
                  <tr key={idx} className="border-b border-gray-200 hover:bg-gray-50">
                    <td className="py-3 px-4">{r.candidate.full_name}</td>
                    <td className="py-3 px-4 font-bold">{r.tech_score}</td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                        r.confidence === 'high' ? 'bg-green-100 text-green-700' :
                        r.confidence === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                        'bg-red-100 text-red-700'
                      }`}>
                        {r.confidence}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs">{(r.matched_required || []).join(', ')}</td>
                    <td className="py-3 px-4 text-xs text-red-600">{(r.missing_required || []).join(', ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Screening 2 Results */}
      {screen2.length > 0 && (
        <div className="p-6 bg-white rounded-xl shadow-lg border border-gray-200">
          <h2 className="text-xl font-semibold mb-4 text-gray-900">Screening 2 – Experience & Stickiness</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b-2 border-gray-300">
                  <th className="py-3 px-4 text-left font-semibold text-gray-700">Candidate</th>
                  <th className="py-3 px-4 text-left font-semibold text-gray-700">Stickiness</th>
                  <th className="py-3 px-4 text-left font-semibold text-gray-700">Total Years</th>
                  <th className="py-3 px-4 text-left font-semibold text-gray-700">Avg Tenure</th>
                  <th className="py-3 px-4 text-left font-semibold text-gray-700">Hops</th>
                  <th className="py-3 px-4 text-left font-semibold text-gray-700">Role Match</th>
                  <th className="py-3 px-4 text-left font-semibold text-gray-700">Flags</th>
                  <th className="py-3 px-4 text-left font-semibold text-gray-700">Combined</th>
                </tr>
              </thead>
              <tbody>
                {screen2.map((r, idx) => (
                  <tr key={idx} className="border-b border-gray-200 hover:bg-gray-50">
                    <td className="py-3 px-4">{r.candidate.full_name}</td>
                    <td className="py-3 px-4">{r.experience.stickiness_score}</td>
                    <td className="py-3 px-4">{r.experience.total_years}</td>
                    <td className="py-3 px-4">{r.experience.avg_tenure}</td>
                    <td className="py-3 px-4">{r.experience.num_hops}</td>
                    <td className="py-3 px-4">{r.experience.role_relevance}</td>
                    <td className="py-3 px-4 text-red-600 text-xs">
                      {(r.experience.role_flags || []).join(', ') || '—'}
                    </td>
                    <td className="py-3 px-4 font-bold">{r.combined_score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Screening 3 Results */}
      {screen3.length > 0 && (
        <div className="p-6 bg-white rounded-xl shadow-lg border border-gray-200">
          <h2 className="text-xl font-semibold mb-4 text-gray-900">Screening 3 – JD-Resume Matrix</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b-2 border-gray-300">
                  <th className="py-3 px-4 text-left font-semibold text-gray-700">Candidate</th>
                  <th className="py-3 px-4 text-left font-semibold text-gray-700">Matrix Score</th>
                  <th className="py-3 px-4 text-left font-semibold text-gray-700">Role Score</th>
                  <th className="py-3 px-4 text-left font-semibold text-gray-700">Skill Score</th>
                </tr>
              </thead>
              <tbody>
                {screen3.map((r, idx) => (
                  <tr key={idx} className="border-b border-gray-200 hover:bg-gray-50">
                    <td className="py-3 px-4">{r.candidate.full_name}</td>
                    <td className="py-3 px-4 font-bold text-lg text-emerald-700">{r.matrix_score}</td>
                    <td className="py-3 px-4">{r.matrix.total_role_score}</td>
                    <td className="py-3 px-4">{r.matrix.total_skill_score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Screening 4 Results */}
{screen4.length > 0 && (
  <div className="p-6 bg-gradient-to-r from-emerald-50 to-blue-50 rounded-xl shadow-lg border-2 border-emerald-200">
    <h2 className="text-xl font-semibold mb-4 text-emerald-800">Screening 4 – AI-Powered Final Audit ⭐</h2>
    <div className="overflow-x-auto">
      <table className="min-w-full bg-white rounded-lg overflow-hidden">
        <thead>
          <tr className="border-b-2 border-emerald-300 bg-emerald-50">
            <th className="py-3 px-4 text-left font-semibold text-gray-700">Rank</th>
            <th className="py-3 px-4 text-left font-semibold text-gray-700">Candidate</th>
            <th className="py-3 px-4 text-left font-semibold text-gray-700">Matrix</th>
            <th className="py-3 px-4 text-left font-semibold text-gray-700">Bias</th>
            <th className="py-3 px-4 text-left font-semibold text-gray-700">LLM Adj</th>
            <th className="py-3 px-4 text-left font-semibold text-gray-700">Final</th>
            <th className="py-3 px-4 text-left font-semibold text-gray-700">Recommendation</th>
            <th className="py-3 px-4 text-center font-semibold text-gray-700">Details</th>
          </tr>
        </thead>
        <tbody>
          {screen4.map((r, idx) => (
            <ExpandableRow key={idx} candidate={r} index={idx} />
          ))}
        </tbody>
      </table>
    </div>
    
    <button 
      onClick={() => setShowFinalReview(true)}
      className="mt-6 w-full px-8 py-4 bg-gradient-to-r from-green-500 to-emerald-600 text-white text-lg font-bold rounded-xl hover:from-green-600 hover:to-emerald-700 transition-all shadow-2xl transform hover:scale-105 flex items-center justify-center gap-2"
    >
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
      📊 View Final Review Dashboard
    </button>
  </div>
)}

    </div>
  )
}

const CustomDropdown = ({ jds, selectedJdId, onSelect }) => {
  const [isOpen, setIsOpen] = useState(false)
  const selectedJd = jds.find(j => j.id === selectedJdId)

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 text-left text-sm font-medium bg-white border border-gray-200 rounded-xl hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all flex items-center justify-between"
      >
        <span className="text-gray-900">
          {selectedJd ? (
            <>{selectedJd.title} - {selectedJd.domain} ({selectedJd.required_skills?.length || 0} required skills)</>
          ) : (
            'Select a job description'
          )}
        </span>
        <svg
          className={`w-5 h-5 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setIsOpen(false)} />
          <div className="absolute z-20 w-full mt-2 bg-white border border-gray-200 rounded-xl shadow-2xl max-h-60 overflow-y-auto">
            {jds.map((jd) => (
              <button
                key={jd.id}
                onClick={() => {
                  onSelect(jd.id)
                  setIsOpen(false)
                }}
                className={`w-full px-4 py-3 text-left text-sm transition-colors ${
                  selectedJdId === jd.id
                    ? 'bg-emerald-50 text-emerald-900 font-medium'
                    : 'text-gray-700 hover:bg-gray-50'
                }`}
              >
                <div className="font-medium">{jd.title}</div>
                <div className="text-xs text-gray-500 mt-1">
                  {jd.domain} • {jd.required_skills?.length || 0} required skills
                </div>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
// Expandable Row Component for Screening 4
const ExpandableRow = ({ candidate, index }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const r = candidate;

  return (
    <>
      <tr 
        className="border-b border-gray-200 hover:bg-emerald-50 cursor-pointer transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <td className="py-3 px-4 font-bold text-lg">#{r.rank}</td>
        <td className="py-3 px-4 font-medium">{r.candidate.full_name}</td>
        <td className="py-3 px-4">{r.matrix_score}</td>
        <td className="py-3 px-4">
          {r.bias_penalty === 0 ? (
            <span className="text-green-600 font-semibold px-2 py-1 bg-green-100 rounded-full text-xs">
              Clean
            </span>
          ) : (
            <span className="text-red-600 font-semibold px-2 py-1 bg-red-100 rounded-full text-xs">
              {r.bias_penalty}
            </span>
          )}
        </td>
        <td className="py-3 px-4">
          <span className={`font-bold ${r.llm_adjustment > 0 ? 'text-green-600' : r.llm_adjustment < 0 ? 'text-emerald-600' : 'text-gray-500'}`}>
            {r.llm_adjustment > 0 ? '+' : ''}{r.llm_adjustment}
          </span>
        </td>
        <td className="py-3 px-4 font-bold text-2xl text-emerald-700">{r.final_score}</td>
        <td className="py-3 px-4">
          <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
            r.llm_recommendation === 'Strong Hire' ? 'bg-emerald-100 text-emerald-700' :
            r.llm_recommendation === 'Hire' ? 'bg-blue-100 text-blue-700' :
            r.llm_recommendation === 'Consider' ? 'bg-yellow-100 text-yellow-700' :
            'bg-gray-100 text-gray-700'
          }`}>
            {r.llm_recommendation}
          </span>
        </td>
        <td className="py-3 px-4 text-center">
          <button 
            className="inline-flex items-center gap-1 px-3 py-1 bg-emerald-100 text-emerald-700 rounded-lg hover:bg-emerald-200 transition-colors"
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(!isExpanded);
            }}
          >
            {isExpanded ? (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                </svg>
                Hide
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
                View
              </>
            )}
          </button>
        </td>
      </tr>
      
      {/* Expandable Details Row */}
      {isExpanded && (
        <tr className="bg-gradient-to-r from-emerald-50 to-yellow-50">
          <td colSpan="8" className="p-6">
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <div className="bg-orange-500 p-2 rounded-lg flex-shrink-0">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div className="flex-1">
                  <h4 className="font-bold text-gray-900 text-lg mb-2">AI Analysis</h4>
                  <p className="text-gray-700 leading-relaxed">{r.llm_analysis}</p>
                </div>
              </div>

              <div className="flex items-start gap-3 pt-4 border-t border-emerald-200">
                <div className="bg-emerald-500 p-2 rounded-lg flex-shrink-0">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <div className="flex-1">
                  <h4 className="font-bold text-gray-900 text-lg mb-2">Key Insight</h4>
                  <p className="text-emerald-700 font-medium">{r.key_insight}</p>
                </div>
              </div>

              {/* Stats Summary */}
              <div className="grid grid-cols-4 gap-4 pt-4 border-t border-emerald-200">
                <div className="bg-white rounded-lg p-4 shadow-sm border border-gray-200">
                  <div className="text-xs text-gray-500 mb-1">Matrix Score</div>
                  <div className="text-2xl font-bold text-gray-900">{r.matrix_score}</div>
                </div>
                <div className="bg-white rounded-lg p-4 shadow-sm border border-gray-200">
                  <div className="text-xs text-gray-500 mb-1">Bias Penalty</div>
                  <div className={`text-2xl font-bold ${r.bias_penalty === 0 ? 'text-green-600' : 'text-emerald-600'}`}>
                    {r.bias_penalty}
                  </div>
                </div>
                <div className="bg-white rounded-lg p-4 shadow-sm border border-gray-200">
                  <div className="text-xs text-gray-500 mb-1">LLM Adjustment</div>
                  <div className={`text-2xl font-bold ${r.llm_adjustment > 0 ? 'text-green-600' : r.llm_adjustment < 0 ? 'text-emerald-600' : 'text-gray-500'}`}>
                    {r.llm_adjustment > 0 ? '+' : ''}{r.llm_adjustment}
                  </div>
                </div>
                <div className="bg-white rounded-lg p-4 shadow-sm border border-gray-200">
                  <div className="text-xs text-gray-500 mb-1">Final Score</div>
                  <div className="text-2xl font-bold text-emerald-600">{r.final_score}</div>
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
};

export default Ranking
