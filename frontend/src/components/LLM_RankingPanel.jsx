// LLM_RankingPanel.jsx - COMPLETE FIXED VERSION
import React, { useState, useEffect } from 'react'
import { XMarkIcon, ChartBarIcon } from '@heroicons/react/24/outline'

const LLM_RankingPanel = ({ onClose, jdsList = [], sendMessage }) => {
  console.log('🎯 LLM_RankingPanel loaded with candidate-first ranking support')
  
  const [filters, setFilters] = useState({ bucket: 'all', bench_status: 'all' })
  const [selectedSid, setSelectedSid] = useState('')
  const [selectedCandidateId, setSelectedCandidateId] = useState('')
  const [rankingMode, setRankingMode] = useState('jd-first') // 'jd-first' or 'candidate-first'
  const [candidatesList, setCandidatesList] = useState([])
  const [loading, setLoading] = useState(false)

  const [jdSearch, setJdSearch] = useState('')
  const [candidateSearch, setCandidateSearch] = useState('')

  // Fetch candidates on mount
  useEffect(() => {
    const fetchCandidates = async () => {
      try {
        const res = await fetch('http://localhost:5050/api/candidates')
        if (!res.ok) {
          console.error('Failed to fetch candidates:', res.status)
          setCandidatesList([])
          return
        }
        const data = await res.json()
        const candidates = Array.isArray(data.candidates) ? data.candidates : []
        setCandidatesList(candidates)
        console.log(`✅ Loaded ${candidates.length} candidates`)
      } catch (err) {
        console.error('Failed to fetch candidates:', err)
        setCandidatesList([])
      }
    }
    fetchCandidates()
  }, [])

  const handleSubmit = async () => {
    if (loading) return

    if (rankingMode === 'jd-first' && !selectedSid) {
      alert('Select JD first!')
      return
    }
    if (rankingMode === 'candidate-first' && !selectedCandidateId) {
      alert('Select candidate first!')
      return
    }

    let message
    if (rankingMode === 'jd-first') {
      message = `AIRANK sid:${selectedSid} bucket:${filters.bucket} bench_status:${filters.bench_status}`
    } else {
      message = `CANDIDATERANK candidate:${selectedCandidateId} bucket:${filters.bucket}`
    }

    setLoading(true)
    try {
      if (typeof sendMessage === 'function') {
        await sendMessage(message)
      }
      onClose()
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white max-w-4xl w-full max-h-[90vh] rounded-3xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-emerald-600 to-teal-600 p-6 text-white">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <ChartBarIcon className="w-8 h-8" />
              <h2 className="text-2xl font-black tracking-tight">🤖 AI Ranking Panel</h2>
            </div>
            <button 
              onClick={onClose} 
              className="p-2 hover:bg-white/20 rounded-xl transition-all hover:scale-110"
            >
              <XMarkIcon className="w-6 h-6" />
            </button>
          </div>
        </div>

        <div className="p-8 max-h-[70vh] overflow-auto space-y-6">
          {/* Ranking Mode Toggle */}
          <div className="bg-gradient-to-r from-emerald-50 to-blue-50 p-6 rounded-2xl border border-emerald-200/50">
            <label className="block text-sm font-bold text-gray-700 mb-4">🔄 Ranking Mode</label>
            <div className="grid grid-cols-2 gap-4">
              <button
                onClick={() => setRankingMode('jd-first')}
                className={`p-4 rounded-xl font-semibold transition-all ${
                  rankingMode === 'jd-first'
                    ? 'bg-emerald-500 text-white shadow-lg'
                    : 'bg-white text-gray-700 border border-gray-300 hover:border-emerald-400'
                }`}
              >
                📋 JD First
                <div className="text-xs mt-1 opacity-80">Rank candidates for a JD</div>
              </button>
              <button
                onClick={() => setRankingMode('candidate-first')}
                className={`p-4 rounded-xl font-semibold transition-all ${
                  rankingMode === 'candidate-first'
                    ? 'bg-blue-500 text-white shadow-lg'
                    : 'bg-white text-gray-700 border border-gray-300 hover:border-blue-400'
                }`}
              >
                👤 Candidate First
                <div className="text-xs mt-1 opacity-80">Find best JDs for a candidate</div>
              </button>
            </div>
          </div>

          {/* Filters */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 bg-gray-50/50 p-6 rounded-2xl border border-gray-200">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">📂 Bucket</label>
              <select 
                value={filters.bucket} 
                onChange={(e) => setFilters(prev => ({...prev, bucket: e.target.value}))}
                className="w-full p-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
              >
                <option value="all">All Buckets</option>
                <option value="data_scientist">Data Scientist</option>
                <option value="data_practice">Data Practice</option>
              </select>
            </div>
            
            {rankingMode === 'jd-first' && (
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">🪑 Bench Status</label>
                <select 
                  value={filters.bench_status} 
                  onChange={(e) => setFilters(prev => ({...prev, bench_status: e.target.value}))}
                  className="w-full p-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
                >
                  <option value="all">All</option>
                  <option value="on">On Bench</option>
                  <option value="off">Off Bench</option>
                </select>
              </div>
            )}
            
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                {rankingMode === 'jd-first' ? '📋 Target JD' : '👤 Target Candidate'}
              </label>
              {rankingMode === 'jd-first' ? (
                <div>
                  <input
                    value={jdSearch}
                    onChange={(e) => {
                      const v = e.target.value
                      setJdSearch(v)
                      setSelectedSid(v.trim())
                    }}
                    placeholder="Type SID (e.g. 52810) or pick from list"
                    list="jd-sid-options"
                    className="w-full p-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
                  />
                  <datalist id="jd-sid-options">
                    {(Array.isArray(jdsList) ? jdsList : []).map((jd) => (
                      <option
                        key={jd.sid}
                        value={String(jd.sid)}
                      >
                        {jd.sid} - {jd.title || 'Untitled'}
                      </option>
                    ))}
                  </datalist>
                  <div className="text-xs text-gray-500 mt-2">
                    Current SID: <span className="font-semibold">{selectedSid || '-'}</span>
                  </div>
                </div>
              ) : (
                <div>
                  <input
                    value={candidateSearch}
                    onChange={(e) => {
                      const v = e.target.value
                      setCandidateSearch(v)
                      // allow typing numeric id directly
                      setSelectedCandidateId(v.trim())
                    }}
                    placeholder="Type candidate ID (e.g. 10) or pick by name"
                    list="candidate-options"
                    className="w-full p-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                  />
                  <datalist id="candidate-options">
                    {(Array.isArray(candidatesList) ? candidatesList : []).map((candidate) => (
                      <option
                        key={candidate.id}
                        value={String(candidate.id)}
                      >
                        {candidate.full_name || `Candidate ${candidate.id}`}
                      </option>
                    ))}
                  </datalist>
                  <div className="text-xs text-gray-500 mt-2">
                    Current Candidate ID: <span className="font-semibold">{selectedCandidateId || '-'}</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* RANK Button */}
          <button
            onClick={handleSubmit}
            disabled={(!selectedSid && rankingMode === 'jd-first') || (!selectedCandidateId && rankingMode === 'candidate-first') || loading}
            className={`w-full font-black py-6 px-8 rounded-2xl shadow-2xl text-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3 mx-auto max-w-md group hover:shadow-3xl hover:scale-[1.02] ${
              rankingMode === 'jd-first' 
                ? 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 disabled:from-gray-400 disabled:to-gray-500 text-white'
                : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 disabled:from-gray-400 disabled:to-gray-500 text-white'
            }`}
          >
            {loading ? (
              <>
                <div className="w-6 h-6 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                {rankingMode === 'jd-first' ? 'Ranking Candidates...' : 'Finding Best JDs...'}
              </>
            ) : (
              <>
                🚀 {rankingMode === 'jd-first' ? 'RANK CANDIDATES' : 'FIND BEST JDS'}
                <span className="text-sm opacity-90 group-hover:translate-x-1 transition-all">
                  {rankingMode === 'jd-first' ? 'for this JD' : 'for this candidate'}
                </span>
              </>
            )}
          </button>

          {/* Panel is a helper only; results render in chat. */}
        </div>
      </div>
    </div>
  )
}

export default LLM_RankingPanel
