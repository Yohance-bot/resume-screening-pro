import { useState } from 'react'
import { extractPdf, parseResume, saveCandidate } from '../services/api'

const ResumeUpload = () => {
  const [singleFile, setSingleFile] = useState(null)
  const [singleResult, setSingleResult] = useState(null)

  const [batchFiles, setBatchFiles] = useState([])
  const [consolidatedFile, setConsolidatedFile] = useState(null)

  const [loading, setLoading] = useState(false)
  const [parsed, setParsed] = useState([])
  const [error, setError] = useState('')
  const [progress, setProgress] = useState('')

  // ---- Single resume -> /api/upload-resume (RAG pipeline) ----
  const handleSingleUpload = async () => {
    if (!singleFile) return

    try {
      setLoading(true)
      setError('')
      setParsed([])
      setSingleResult(null)
      setProgress('Uploading and processing resume...')

      const formData = new FormData()
      formData.append('file', singleFile)

      const res = await fetch('http://localhost:5050/api/upload-resume', {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.error || `Upload failed: ${res.status}`)
      }

      const data = await res.json()
      console.log('Single upload response:', data)   // add this
      setSingleResult(data) 
      alert('SingleResult set')
      setSingleResult(data)
      setProgress('')
      setSingleFile(null)
    } catch (err) {
      setError(err.message || 'Single upload failed')
      setProgress('')
    } finally {
      setLoading(false)
    }
  }

  // ---- Batch upload -> /api/batch_upload (existing API) ----
  const handleBatchUpload = async () => {
    if (!batchFiles.length) return

    try {
      setLoading(true)
      setError('')
      setParsed([])
      setSingleResult(null)

      const formData = new FormData()
      Array.from(batchFiles).forEach((f) => formData.append('files', f))

      setProgress(`Uploading ${batchFiles.length} files...`)

      const res = await fetch('http://localhost:5050/api/batch_upload', {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) throw new Error('Batch upload failed')
      const data = await res.json()

      console.log('Backend response:', data)
      setParsed(data.results || [])
      setBatchFiles([])
      setProgress('')
    } catch (err) {
      setError(err.message || 'Batch upload failed')
      setProgress('')
    } finally {
      setLoading(false)
    }
  }

  // ---- Consolidated PDF -> extractPdf + parseResume + saveCandidate ----
  const handleConsolidatedUpload = async () => {
    if (!consolidatedFile) return

    try {
      setLoading(true)
      setError('')
      setParsed([])
      setSingleResult(null)

      setProgress('Extracting text from consolidated PDF...')

      const { text } = await extractPdf(consolidatedFile)

      setProgress('Splitting into individual resumes...')

      const chunks = text.split(/\n{3,}|\f/).filter((chunk) => {
        const cleaned = chunk.trim()
        return (
          cleaned.length > 200 &&
          (cleaned.match(/@/) ||
            cleaned.match(/\d{3}[-.\s]?\d{3}[-.\s]?\d{4}/))
        )
      })

      setProgress(`Found ${chunks.length} potential resumes, parsing...`)

      const results = []
      for (let i = 0; i < chunks.length; i++) {
        setProgress(`Parsing resume ${i + 1}/${chunks.length}...`)
        try {
          const structured = await parseResume(chunks[i])
          await saveCandidate(chunks[i], structured)
          results.push(structured)
        } catch (err) {
          console.error(`Failed to parse chunk ${i + 1}:`, err)
        }
      }

      setParsed(results)
      setConsolidatedFile(null)
      setProgress('')
    } catch (err) {
      setError(err.message || 'Consolidated upload failed')
      setProgress('')
    } finally {
      setLoading(false)
    }
  }

  // ---- Helpers for old parsed format (batch / consolidated) ----
  const getTotalExperience = (roles) => {
    if (!roles || !roles.length) return 0
    const total = roles.reduce((sum, r) => {
      const years = parseFloat(r.duration?.replace(/[^\d.]/g, '') || 0)
      return sum + years
    }, 0)
    return Math.round(total * 10) / 10
  }

  const getLatestRole = (roles) => {
    if (!roles || !roles.length) return '—'
    return roles[0]?.title || '—'
  }

  const getEducation = (education) => {
    if (!education || !education.length) return '—'
    const latest = education[0]
    return `${latest.degree || '—'} ${
      latest.field ? `in ${latest.field}` : ''
    }`
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-extrabold tracking-tight text-yellow-500">
          Resume Upload
        </h1>
        <p className="text-sm text-yellow-300 mt-1">
          Upload a single resume into the RAG pipeline, multiple PDFs, or one
          consolidated PDF with many resumes.
        </p>
      </div>

      {/* Upload Cards */}
      <div className="grid grid-cols-1 md:grid-cols-1 gap-6">
        {/* Single Resume (RAG) */}
        <div className="p-6 rounded-3xl bg-white/60 backdrop-blur-xl border border-white/20 shadow-xl shadow-black/5 hover:bg-white/70 transition-all">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-3xl">🎯</span>
            <div>
              <h3 className="text-lg font-bold text-gray-900">
                Single Resume (RAG)
              </h3>
              <p className="text-xs text-gray-600">
                Parse and store one resume using Groq + vector DB
              </p>
            </div>
          </div>

          <input
            type="file"
            accept=".pdf,.docx"
            onChange={(e) => setSingleFile(e.target.files?.[0] || null)}
            className="block w-full text-sm text-gray-600 mb-4
                     file:mr-4 file:py-2 file:px-4 file:rounded-xl
                     file:border-0 file:text-sm file:font-semibold
                     file:bg-emerald-50 file:text-emerald-700
                     hover:file:bg-emerald-100 file:cursor-pointer"
          />

          {singleFile && (
            <div className="mb-3 text-xs text-gray-600 bg-emerald-50 px-3 py-2 rounded-lg">
              ✅ {singleFile.name}
            </div>
          )}

          <button
            onClick={handleSingleUpload}
            disabled={!singleFile || loading}
            className="w-full btn-primary px-6 py-3 rounded-xl font-semibold disabled:opacity-50"
          >
            {loading && progress.includes('processing')
              ? 'Processing...'
              : 'Upload & Process'}
          </button>
        </div>

        {/* 
        <div className="p-6 rounded-3xl bg-white/60 backdrop-blur-xl border border-white/20 shadow-xl shadow-black/5 hover:bg-white/70 transition-all">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-3xl">📚</span>
            <div>
              <h3 className="text-lg font-bold text-gray-900">Multiple PDFs</h3>
              <p className="text-xs text-gray-600">One resume per file</p>
            </div>
          </div>

          <input
            type="file"
            accept=".pdf"
            multiple
            onChange={(e) => setBatchFiles(e.target.files || [])}
            className="block w-full text-sm text-gray-600 mb-4
                     file:mr-4 file:py-2 file:px-4 file:rounded-xl
                     file:border-0 file:text-sm file:font-semibold
                     file:bg-emerald-50 file:text-emerald-700
                     hover:file:bg-emerald-100 file:cursor-pointer"
          />

          {batchFiles.length > 0 && (
            <div className="mb-3 text-xs text-gray-600 bg-emerald-50 px-3 py-2 rounded-lg">
              ✅ {batchFiles.length} file
              {batchFiles.length !== 1 ? 's' : ''} selected
            </div>
          )}

          <button
            onClick={handleBatchUpload}
            disabled={batchFiles.length === 0 || loading}
            className="w-full btn-primary px-6 py-3 rounded-xl font-semibold disabled:opacity-50"
          >
            {loading && progress.includes('Uploading')
              ? progress
              : `Upload ${batchFiles.length || ''} PDFs`}
          </button>
        </div>
        */}

        {/* 
        <div className="p-6 rounded-3xl bg-white/60 backdrop-blur-xl border border-white/20 shadow-xl shadow-black/5 hover:bg-white/70 transition-all">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-3xl">📄</span>
            <div>
              <h3 className="text-lg font-bold text-gray-900">
                Consolidated PDF
              </h3>
              <p className="text-xs text-gray-600">Many resumes in one file</p>
            </div>
          </div>

          <input
            type="file"
            accept=".pdf"
            onChange={(e) =>
              setConsolidatedFile(e.target.files?.[0] || null)
            }
            className="block w-full text-sm text-gray-600 mb-4
                     file:mr-4 file:py-2 file:px-4 file:rounded-xl
                     file:border-0 file:text-sm file:font-semibold
                     file:bg-blue-50 file:text-blue-700
                     hover:file:bg-blue-100 file:cursor-pointer"
          />

          {consolidatedFile && (
            <div className="mb-3 text-xs text-gray-600 bg-blue-50 px-3 py-2 rounded-lg">
              ✅ {consolidatedFile.name}
            </div>
          )}

          <button
            onClick={handleConsolidatedUpload}
            disabled={!consolidatedFile || loading}
            className="w-full px-6 py-3 rounded-xl font-semibold bg-blue-600 hover:bg-blue-700 text-white shadow-lg disabled:opacity-50 transition-all"
          >
            {loading && progress.includes('Extracting')
              ? 'Processing...'
              : 'Upload & Split'}
          </button>
        </div>
        */}
      </div>

      {/* Progress */}
      {progress && (
        <div className="p-4 rounded-2xl bg-blue-50 border border-blue-200 text-blue-700 text-sm flex items-center gap-2">
          <div className="animate-spin h-4 w-4 border-2 border-blue-600 border-t-transparent rounded-full" />
          {progress}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="p-4 rounded-2xl bg-red-50 border border-red-200 text-red-700 text-sm">
          ⚠️ {error}
        </div>
      )}

      {singleResult && (
        <div className="max-w-4xl mt-6 rounded-3xl bg-white/70 backdrop-blur-2xl border border-white/20 shadow-2xl shadow-black/5 overflow-hidden">
          {/* Header */}
          <div className="px-6 py-4 border-b border-white/20 bg-gradient-to-r from-emerald-50/80 to-blue-50/80 flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-emerald-900">
                ✅ Parsed: {singleResult.candidate_name || "Unknown"}
              </h2>
              <p className="text-xs text-gray-600 mt-1">
                {singleResult.message || "Resume processed successfully"}
              </p>
            </div>
            <div className="text-xs text-gray-600 text-right">
              <div>
                Experience:{" "}
                <span className="font-semibold">
                  {singleResult.stats?.total_experience_years ?? "—"} yrs
                </span>
              </div>
              <div>
                Jobs:{" "}
                <span className="font-semibold">
                  {singleResult.stats?.total_jobs ?? 0}
                </span>{" "}
                · Skills:{" "}
                <span className="font-semibold">
                  {singleResult.stats?.skills_count ?? 0}
                </span>
              </div>
            </div>
          </div>

          {/* Summary table */}
          <div className="px-6 py-4">
            <div className="overflow-x-auto">
              <table className="min-w-full text-xs text-left">
                <thead>
                  <tr className="text-gray-500 uppercase tracking-wide">
                    <th className="py-2 pr-4">Job #</th>
                    <th className="py-2 pr-4">Company</th>
                    <th className="py-2 pr-4">Title</th>
                    <th className="py-2 pr-4 text-right">Responsibilities</th>
                  </tr>
                </thead>
                <tbody>
                  {singleResult.stats?.jobs_breakdown?.map((job, idx) => (
                    <tr
                      key={idx}
                      className="border-t border-gray-100 hover:bg-gray-50/60 transition-colors"
                    >
                      <td className="py-2 pr-4 text-emerald-700 font-semibold">
                        {idx + 1}
                      </td>
                      <td className="py-2 pr-4 text-gray-800">{job.company}</td>
                      <td className="py-2 pr-4 text-gray-700">{job.title}</td>
                      <td className="py-2 pr-4 text-right text-gray-700">
                        {job.responsibilities_count}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Expand / collapse full JSON */}
            <details className="mt-4">
              <summary className="cursor-pointer text-xs text-emerald-700 font-semibold flex items-center gap-1">
                <span>Show full parsed data</span>
                <span className="text-[10px] text-gray-500">(JSON)</span>
              </summary>
              <pre className="mt-2 text-[11px] bg-gray-50 border border-gray-200 rounded-xl p-3 overflow-x-auto max-h-80">
                {JSON.stringify(singleResult, null, 2)}
              </pre>
            </details>
          </div>
        </div>
      )}

      {/* Parsed Results Table (old batch / consolidated flow) */}
      {parsed.length > 0 && (
        <div className="rounded-3xl bg-white/70 backdrop-blur-2xl border border-white/20 shadow-2xl shadow-black/5 overflow-hidden">
          <div className="px-6 py-5 border-b border-white/20 bg-gradient-to-r from-emerald-50/80 to-blue-50/80">
            <h2 className="text-2xl font-bold text-emerald-900">
              📊 Parsed Candidates ({parsed.length})
            </h2>
            <p className="text-xs text-gray-600 mt-1">
              Successfully extracted and saved to database
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left bg-white/40">
                  <th className="py-3 px-4 font-bold text-gray-700">#</th>
                  <th className="py-3 px-4 font-bold text-gray-700">Name</th>
                  <th className="py-3 px-4 font-bold text-gray-700">Contact</th>
                  <th className="py-3 px-4 font-bold text-gray-700">
                    Experience
                  </th>
                  <th className="py-3 px-4 font-bold text-gray-700">
                    Latest Role
                  </th>
                  <th className="py-3 px-4 font-bold text-gray-700">
                    Education
                  </th>
                  <th className="py-3 px-4 font-bold text-gray-700">
                    Top Skills
                  </th>
                  <th className="py-3 px-4 font-bold text-gray-700">
                    Summary
                  </th>
                </tr>
              </thead>
              <tbody>
                {parsed.map((candidate, idx) => {
                  const sections = candidate.sections || {}
                  const skills = candidate.skills || sections.skills || []
                  const roles = candidate.roles || sections.experience || []
                  const education =
                    candidate.education || sections.education || []
                  const summary = candidate.summary || ''

                  return (
                    <tr
                      key={idx}
                      className="border-b border-white/10 hover:bg-white/50 transition-colors"
                    >
                      <td className="py-4 px-4 font-semibold text-emerald-700">
                        {idx + 1}
                      </td>

                      <td className="py-4 px-4">
                        <div className="font-semibold text-gray-900">
                          {candidate.full_name || 'Unknown'}
                        </div>
                      </td>

                      <td className="py-4 px-4">
                        <div className="text-xs space-y-1">
                          <div className="flex items-center gap-1">
                            <span className="text-gray-500">✉️</span>
                            <span className="text-blue-600 truncate max-w-[150px]">
                              {candidate.email || '—'}
                            </span>
                          </div>
                          <div className="flex items-center gap-1">
                            <span className="text-gray-500">📞</span>
                            <span className="text-gray-700">
                              {candidate.phone || '—'}
                            </span>
                          </div>
                        </div>
                      </td>

                      <td className="py-4 px-4">
                        <div className="font-bold text-emerald-700 text-lg">
                          {getTotalExperience(roles)} yrs
                        </div>
                        <div className="text-[10px] text-gray-500">
                          {roles.length} role
                          {roles.length !== 1 ? 's' : ''}
                        </div>
                      </td>

                      <td className="py-4 px-4">
                        <div className="font-medium text-gray-800 max-w-[180px]">
                          {getLatestRole(roles)}
                        </div>
                        {roles[0]?.company && (
                          <div className="text-[10px] text-gray-500">
                            @ {roles[0].company}
                          </div>
                        )}
                      </td>

                      <td className="py-4 px-4">
                        <div className="text-xs text-gray-700 max-w-[200px]">
                          {getEducation(education)}
                        </div>
                      </td>

                      <td className="py-4 px-4">
                        <div className="flex flex-wrap gap-1 max-w-[250px]">
                          {skills.slice(0, 8).map((skill, i) => (
                            <span
                              key={i}
                              className="px-2 py-1 bg-emerald-100 text-emerald-700 rounded-full text-[10px] font-semibold"
                            >
                              {skill}
                            </span>
                          ))}
                          {skills.length > 8 && (
                            <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded-full text-[10px] font-semibold">
                              +{skills.length - 8}
                            </span>
                          )}
                        </div>
                      </td>

                      <td className="py-4 px-4">
                        <div className="text-xs text-gray-600 max-w-[300px] line-clamp-3 italic">
                          {summary.slice(0, 150)}
                          {summary.length > 150 && '...'}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="px-6 py-4 bg-white/40 border-t border-white/20 text-xs text-gray-600">
            💡 <strong>{parsed.length} candidates</strong> parsed and ready for
            screening
          </div>
        </div>
      )}
    </div>
  )
}

export default ResumeUpload
