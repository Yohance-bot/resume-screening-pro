import React from 'react'  // FIXED
import { useRef, useState, useEffect } from 'react'
import { ChartBarIcon, EyeIcon, ChevronDownIcon } from '@heroicons/react/24/outline'
import { uploadJdsCsv } from '../services/api'

const JDUpload = () => {
  const fileInputRef = useRef(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [jdsList, setJdsList] = useState([])
  const [expandedSids, setExpandedSids] = useState(new Set())  // Multiple expands

  const [editingCell, setEditingCell] = useState(null) // { sid, field }
  const [editingValue, setEditingValue] = useState('')
  const [savingCell, setSavingCell] = useState(null) // { sid, field }
  const [cellError, setCellError] = useState(null) // { sid, field, message }

  const [showAddModal, setShowAddModal] = useState(false)
  const [addSaving, setAddSaving] = useState(false)
  const [addError, setAddError] = useState('')
  const [addForm, setAddForm] = useState({
    sid: '',
    designation: '',
    competency: '',
    probability: '',
    billability: '',
    location_type: '',
    ctc_rate: '',
    skills: '',
    description: '',
    urgent: false,

    comments: '',
    sub_bu: '',
    account: '',
    project: '',
    sub_practice_name: '',
    billing_type: '',
    billed_pct: '',
    project_type: '',
    governance_category: '',
    customer_interview: '',
    position_type: '',
    base_location_country: '',
    base_location_city: '',
    facility: '',
    fulfilment_type: '',
    approval_status: '',
    sid_status: '',
    identified_empid: '',
    identified_empname: '',
    original_billable_date: '',
    updated_billable_date: '',
    billing_end_date: '',
    requirement_expiry_date: '',
    resource_required_date: '',
    requirement_initiated_date: '',
    month: '',
    request_initiated_by: '',
    dm: '',
    bdm: '',
    remarks: '',
    reason_for_cancel: '',
    reason_for_lost: '',
    replacement_employee: '',
    customer_reference_id: '',
    billing_loss_status: '',
    aging: '',
    action_items: '',
  })

  const fetchJds = async () => {
    try {
      const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5050'
      const res = await fetch(`${API_BASE}/api/jds`)
      if (res.ok) {
        const data = await res.json()
        setJdsList(data)
      }
    } catch (err) {
      console.error('Failed to fetch JDs:', err)
    }
  }

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      setLoading(true)
      setError('')
      setResult(null)
      setExpandedSids(new Set())
      const data = await uploadJdsCsv(file)
      setResult(data)
      setTimeout(fetchJds, 1500)
    } catch (err) {
      setError(err.message || 'CSV upload failed')
    } finally {
      setLoading(false)
    }
  }

  const handleButtonClick = () => {
    fileInputRef.current?.click()
  }

  const toggleExpand = (sid) => {
    const newSet = new Set(expandedSids)
    if (newSet.has(sid)) {
      newSet.delete(sid)
    } else {
      newSet.add(sid)
    }
    setExpandedSids(newSet)
  }

  const beginEdit = (sid, field, currentValue) => {
    setCellError(null)
    setEditingCell({ sid, field })
    setEditingValue(currentValue ?? '')
  }

  const cancelEdit = () => {
    setEditingCell(null)
    setEditingValue('')
  }

  const commitEdit = async () => {
    if (!editingCell) return

    const { sid, field } = editingCell
    const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5050'
    const newValue = editingValue

    const patch = { [field]: newValue }
    if (field === 'probability') patch[field] = newValue === '' ? 0 : Number(newValue)
    if (field === 'skills') patch[field] = newValue
    if (field === 'sid') patch[field] = String(newValue).trim()

    const prev = jdsList
    const next = prev.map((j) => {
      if (j.sid !== sid) return j
      if (field === 'sid') return { ...j, sid: String(newValue).trim() }
      if (field === 'skills') return { ...j, skills: String(newValue).split(',').map(s => s.trim()).filter(Boolean) }
      return { ...j, [field]: newValue }
    })
    setJdsList(next)

    setSavingCell({ sid, field })
    setEditingCell(null)

    try {
      const res = await fetch(`${API_BASE}/api/jds/${encodeURIComponent(sid)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.error || `Update failed (${res.status})`)
      }
      const updated = await res.json()
      setJdsList(updated)

      if (field === 'sid') {
        const newSid = String(newValue).trim()
        setExpandedSids((old) => {
          const s = new Set(old)
          if (s.has(sid)) {
            s.delete(sid)
            if (newSid) s.add(newSid)
          }
          return s
        })
      }
    } catch (e) {
      setJdsList(prev)
      setCellError({ sid, field, message: e.message })
    } finally {
      setSavingCell(null)
    }
  }

  const handleCellKeyDown = async (e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      await commitEdit()
    }
    if (e.key === 'Escape') {
      e.preventDefault()
      cancelEdit()
    }
  }

  const openAddModal = () => {
    setAddError('')
    setShowAddModal(true)
  }

  const closeAddModal = () => {
    if (addSaving) return
    setShowAddModal(false)
  }

  const updateAddForm = (key, value) => {
    setAddForm((prev) => ({ ...prev, [key]: value }))
  }

  const submitAddJd = async () => {
    const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5050'
    setAddSaving(true)
    setAddError('')
    try {
      const res = await fetch(`${API_BASE}/api/jds`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(addForm),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.error || `Create failed (${res.status})`)
      }
      const updated = await res.json()
      setJdsList(updated)
      setShowAddModal(false)
      setAddForm((prev) => ({ ...prev, sid: '', designation: '', competency: '', probability: '', billability: '', location_type: '', ctc_rate: '', skills: '', description: '' }))
    } catch (e) {
      setAddError(e.message)
    } finally {
      setAddSaving(false)
    }
  }

  const EditableCell = ({ jd, field, className = '', display, getValue }) => {
    const isEditing = editingCell?.sid === jd.sid && editingCell?.field === field
    const isSaving = savingCell?.sid === jd.sid && savingCell?.field === field
    const errorMsg = cellError?.sid === jd.sid && cellError?.field === field ? cellError?.message : ''

    const currentValue = getValue ? getValue(jd) : (jd[field] ?? '')
    const showText = display != null ? display : (currentValue ?? '—')

    return (
      <td
        className={`p-4 border-b align-top cursor-text ${className} ${errorMsg ? 'ring-2 ring-red-300' : ''}`}
        title={errorMsg || ''}
        onClick={() => {
          if (field === 'skills') {
            const v = Array.isArray(jd.skills) ? jd.skills.join(', ') : (jd.skills || '')
            beginEdit(jd.sid, field, v)
            return
          }
          if (field === 'probability') {
            beginEdit(jd.sid, field, String(jd.probability ?? ''))
            return
          }
          beginEdit(jd.sid, field, currentValue)
        }}
      >
        {isEditing ? (
          <input
            autoFocus
            value={editingValue}
            onChange={(e) => setEditingValue(e.target.value)}
            onBlur={commitEdit}
            onKeyDown={handleCellKeyDown}
            className="w-full rounded-lg border border-emerald-200 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-300"
          />
        ) : (
          <div className="flex items-center gap-2">
            <div className="min-w-0 flex-1 truncate">{showText || '—'}</div>
            {isSaving && <div className="text-xs text-emerald-600 font-bold">Saving…</div>}
          </div>
        )}
      </td>
    )
  }

  useEffect(() => {
    fetchJds()
  }, [])

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-emerald-50 py-8 px-4">
      <div className="max-w-7xl mx-auto space-y-6">

        {/* ✨ CandidatesPage-style header */}
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-emerald-500 to-yellow-500 p-8 shadow-xl">
          <div className="absolute inset-0 bg-white/5 backdrop-blur-sm"></div>
          <div className="relative flex items-center justify-between">
            <div>
              <h2 className="text-3xl font-semibold text-white mb-1 tracking-tight">
                JD Dashboard
              </h2>
              <p className="text-white/85 text-sm font-medium">
                {jdsList.length} JDs
              </p>
            </div>

            <div className="flex items-center gap-3">
              <input type="file" ref={fileInputRef} onChange={handleFileChange} className="hidden" accept=".csv" />
              <button
                onClick={handleButtonClick}
                disabled={loading}
                className="px-5 py-2.5 bg-white/10 backdrop-blur-xl border border-white/20 text-white rounded-xl hover:bg-white/20 transition-all duration-300 font-medium hover:scale-105 active:scale-95"
              >
                {loading ? '⏳ Uploading…' : '⬆ Upload CSV'}
              </button>

              <button
                onClick={openAddModal}
                className="px-5 py-2.5 bg-white/10 backdrop-blur-xl border border-white/20 text-white rounded-xl hover:bg-white/20 transition-all duration-300 font-medium hover:scale-105 active:scale-95"
              >
                ➕ Add JD
              </button>

              <button
                onClick={fetchJds}
                className="px-5 py-2.5 bg-white/10 backdrop-blur-xl border border-white/20 text-white rounded-xl hover:bg-white/20 transition-all duration-300 font-medium hover:scale-105 active:scale-95"
              >
                <span className="mr-2 inline-block transition-transform duration-500 hover:rotate-180">↻</span>
                Refresh
              </button>
            </div>
          </div>

          {(error || result) && (
            <div className="relative mt-6">
              {error && (
                <div className="p-4 bg-red-500/15 border border-red-400/30 rounded-2xl text-white font-semibold">
                  {error}
                </div>
              )}
              {result && (
                <div className="mt-3 p-4 bg-white/10 border border-white/20 rounded-2xl text-white">
                  <div className="text-sm font-black">✅ Upload complete</div>
                  <div className="mt-2 grid grid-cols-3 gap-3 text-sm font-bold">
                    <div>{result.created} Created</div>
                    <div>{result.skipped} Skipped</div>
                    <div>{result.total_rows} Total</div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ✨ Clean table card (no vertical height limit) */}
        <div className="rounded-3xl overflow-hidden shadow-xl border border-gray-200 bg-white">
          <div className="overflow-auto max-h-[calc(100vh-187px)] jd-table-scroll" style={{
            scrollbarWidth: 'thin',
            scrollbarColor: '#10b981 #f1f5f9'
          }}>
            <table className="w-full">
              <thead className="bg-gray-50 sticky top-0 z-10">
                <tr>
                  <th className="p-4 w-20 text-left font-bold border-b bg-gray-50">SID</th>
                  <th className="p-4 w-44 text-left font-bold border-b bg-gray-50">Designation</th>
                  <th className="p-4 w-28 text-left font-bold border-b bg-gray-50">Competency</th>
                  <th className="p-4 w-20 text-center font-bold border-b bg-gray-50">Prob.</th>
                  <th className="p-4 w-24 text-left font-bold border-b bg-gray-50">Billability</th>
                  <th className="p-4 w-28 text-left font-bold border-b bg-gray-50">Location</th>
                  <th className="p-4 w-24 text-right font-bold border-b bg-gray-50">CTC</th>
                  <th className="p-4 w-36 text-left font-bold border-b bg-gray-50">Skills</th>
                </tr>
              </thead>
              <tbody>
                {jdsList.map((jd) => (
                  <React.Fragment key={jd.sid}>
                    {/* SUMMARY ROW */}
                    <tr className="hover:bg-emerald-50 border-b transition-colors group">
                      <td className="p-4 border-b" onClick={() => beginEdit(jd.sid, 'sid', jd.sid)}>
                        <div className="flex items-center gap-2">
                          {editingCell?.sid === jd.sid && editingCell?.field === 'sid' ? (
                            <input
                              autoFocus
                              value={editingValue}
                              onChange={(e) => setEditingValue(e.target.value)}
                              onBlur={commitEdit}
                              onKeyDown={handleCellKeyDown}
                              className="w-full rounded-lg border border-emerald-200 bg-white px-3 py-2 text-sm font-bold outline-none focus:ring-2 focus:ring-emerald-300"
                            />
                          ) : (
                            <code className="bg-emerald-100 text-emerald-800 px-3 py-1 rounded-lg text-sm font-bold">
                              {jd.sid}
                            </code>
                          )}
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              toggleExpand(jd.sid)
                            }}
                            className="p-2 -m-2 rounded-lg hover:bg-emerald-200 hover:text-emerald-700 transition-all group-hover:scale-110"
                            title="Toggle full details"
                          >
                            <EyeIcon className="w-5 h-5" />
                          </button>
                        </div>
                        {savingCell?.sid === jd.sid && savingCell?.field === 'sid' && (
                          <div className="mt-1 text-xs font-bold text-emerald-600">Saving…</div>
                        )}
                      </td>

                      <EditableCell
                        jd={jd}
                        field="designation"
                        className="font-semibold max-w-[200px]"
                        display={jd.title || jd.designation || 'Unnamed'}
                        getValue={(j) => j.designation || j.title || ''}
                      />

                      <EditableCell jd={jd} field="competency" display={jd.competency || '—'} />

                      <EditableCell
                        jd={jd}
                        field="probability"
                        className="text-center"
                        display={`${Number(jd.probability ?? 0)}%`}
                        getValue={(j) => j.probability ?? 0}
                      />

                      <EditableCell jd={jd} field="billability" display={jd.billability || '—'} />

                      <EditableCell jd={jd} field="location_type" display={jd.location_type || '—'} />

                      <EditableCell
                        jd={jd}
                        field="ctc_rate"
                        className="text-right"
                        display={jd.ctc_rate ? `₹${jd.ctc_rate}` : '—'}
                        getValue={(j) => j.ctc_rate || ''}
                      />

                      <EditableCell
                        jd={jd}
                        field="skills"
                        display={Array.isArray(jd.skills) && jd.skills.length ? jd.skills.slice(0, 5).join(', ') : 'No skills'}
                        getValue={(j) => (Array.isArray(j.skills) ? j.skills.join(', ') : (j.skills || ''))}
                      />
                    </tr>

                    {/* EXPANDABLE FULL DETAILS */}
                    {expandedSids.has(jd.sid) && (
                      <tr className="bg-gradient-to-r from-emerald-50 to-teal-50 animate-fadeIn">
                        <td colSpan="8" className="p-0">
                          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-6 gap-4 p-8">
                            <div className="space-y-1 border-r pr-4 lg:border-emerald-200">
                              <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Project</span>
                              <p className="font-semibold text-gray-900 break-words">{jd.project || '—'}</p>
                            </div>
                            <div className="space-y-1">
                              <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Sub BU</span>
                              <p className="font-semibold text-gray-900">{jd.sub_bu || '—'}</p>
                            </div>
                            <div className="space-y-1">
                              <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Facility</span>
                              <p className="font-semibold text-gray-900">{jd.facility || '—'}</p>
                            </div>
                            <div className="space-y-1">
                              <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">DM</span>
                              <p className="font-semibold text-gray-900">{jd.dm || '—'}</p>
                            </div>
                            <div className="space-y-1">
                              <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Expiry</span>
                              <p className="text-sm font-mono text-orange-600 font-bold">{jd.requirement_expiry_date || '—'}</p>
                            </div>
                            <div className="space-y-1">
                              <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Aging</span>
                              <p className={`text-xl font-black ${jd.days_aging > 30 ? 'text-red-600' : 'text-orange-600'}`}>
                                {jd.days_aging?.toFixed(0) || 0}d
                              </p>
                            </div>
                            <div className="space-y-1">
                              <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Urgent</span>
                              <div className={`px-3 py-1 rounded-full text-sm font-bold ${
                                jd.is_urgent ? 'bg-red-100 text-red-800 ring-2 ring-red-200' : 'bg-green-100 text-green-800'
                              }`}>
                                {jd.is_urgent ? '🔥 YES' : '✅ No'}
                              </div>
                            </div>
                            <div className="space-y-1 lg:col-span-2 xl:col-span-1">
                              <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Action Items</span>
                              <p className="text-sm text-gray-700 italic max-w-sm" title={jd.action_items}>
                                {jd.action_items ? jd.action_items.slice(0, 80) + '...' : 'None'}
                              </p>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>

          {jdsList.length === 0 && (
            <div className="text-center py-20">
              <ChartBarIcon className="w-24 h-24 text-gray-300 mx-auto mb-6" />
              <h3 className="text-2xl font-bold text-gray-500 mb-2">No JDs Yet</h3>
              <p className="text-gray-400">Upload your CSV to get started</p>
            </div>
          )}
        </div>

        {showAddModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
            <div className="w-full max-w-5xl rounded-3xl bg-white shadow-2xl border border-emerald-100 overflow-hidden">
              <div className="bg-gradient-to-r from-emerald-600 to-teal-600 p-6 text-white flex items-center justify-between">
                <div className="text-2xl font-black">➕ Add New JD</div>
                <button onClick={closeAddModal} className="rounded-xl bg-white/20 hover:bg-white/30 px-4 py-2 font-bold">
                  Close
                </button>
              </div>

              <div className="max-h-[70vh] overflow-auto p-6">
                {addError && (
                  <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-red-800 font-semibold">
                    {addError}
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-bold text-gray-700">SID *</label>
                    <input value={addForm.sid} onChange={(e) => updateAddForm('sid', e.target.value)} className="mt-1 w-full rounded-xl border border-gray-200 px-4 py-3" />
                  </div>
                  <div>
                    <label className="text-sm font-bold text-gray-700">Designation</label>
                    <input value={addForm.designation} onChange={(e) => updateAddForm('designation', e.target.value)} className="mt-1 w-full rounded-xl border border-gray-200 px-4 py-3" />
                  </div>

                  <div>
                    <label className="text-sm font-bold text-gray-700">Competency</label>
                    <input value={addForm.competency} onChange={(e) => updateAddForm('competency', e.target.value)} className="mt-1 w-full rounded-xl border border-gray-200 px-4 py-3" />
                  </div>
                  <div>
                    <label className="text-sm font-bold text-gray-700">Probability</label>
                    <input value={addForm.probability} onChange={(e) => updateAddForm('probability', e.target.value)} className="mt-1 w-full rounded-xl border border-gray-200 px-4 py-3" placeholder="0-100" />
                  </div>

                  <div>
                    <label className="text-sm font-bold text-gray-700">Billability</label>
                    <input value={addForm.billability} onChange={(e) => updateAddForm('billability', e.target.value)} className="mt-1 w-full rounded-xl border border-gray-200 px-4 py-3" />
                  </div>
                  <div>
                    <label className="text-sm font-bold text-gray-700">Location Type</label>
                    <input value={addForm.location_type} onChange={(e) => updateAddForm('location_type', e.target.value)} className="mt-1 w-full rounded-xl border border-gray-200 px-4 py-3" />
                  </div>

                  <div>
                    <label className="text-sm font-bold text-gray-700">CTC / Rate</label>
                    <input value={addForm.ctc_rate} onChange={(e) => updateAddForm('ctc_rate', e.target.value)} className="mt-1 w-full rounded-xl border border-gray-200 px-4 py-3" />
                  </div>
                  <div>
                    <label className="text-sm font-bold text-gray-700">Skills (comma separated)</label>
                    <input value={addForm.skills} onChange={(e) => updateAddForm('skills', e.target.value)} className="mt-1 w-full rounded-xl border border-gray-200 px-4 py-3" />
                  </div>

                  <div className="md:col-span-2">
                    <label className="text-sm font-bold text-gray-700">Description</label>
                    <textarea value={addForm.description} onChange={(e) => updateAddForm('description', e.target.value)} className="mt-1 w-full rounded-xl border border-gray-200 px-4 py-3 min-h-[120px]" />
                  </div>

                  <div className="md:col-span-2">
                    <div className="flex items-center gap-3">
                      <input type="checkbox" checked={Boolean(addForm.urgent)} onChange={(e) => updateAddForm('urgent', e.target.checked)} />
                      <label className="text-sm font-bold text-gray-700">Urgent</label>
                    </div>
                  </div>
                </div>

                <div className="mt-6 rounded-2xl border border-gray-200 bg-white p-4">
                  <div className="text-sm font-black text-gray-900 mb-3">All Fields</div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {Object.keys(addForm).filter((k) => !['sid','designation','competency','probability','billability','location_type','ctc_rate','skills','description','urgent'].includes(k)).map((key) => {
                      const val = addForm[key]
                      const placeholder = key.replace(/_/g, ' ')
                      const isLong = key.includes('reason') || key.includes('remarks') || key.includes('comments')
                      if (typeof val === 'boolean') {
                        return (
                          <label key={key} className="flex items-center gap-3 rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
                            <input type="checkbox" checked={Boolean(val)} onChange={(e) => updateAddForm(key, e.target.checked)} />
                            <span className="text-sm font-bold text-gray-700">{placeholder}</span>
                          </label>
                        )
                      }
                      if (isLong) {
                        return (
                          <textarea key={key} value={val} onChange={(e) => updateAddForm(key, e.target.value)} className="w-full rounded-xl border border-gray-200 px-4 py-3 min-h-[90px] md:col-span-2" placeholder={placeholder} />
                        )
                      }
                      return (
                        <input key={key} value={val} onChange={(e) => updateAddForm(key, e.target.value)} className="w-full rounded-xl border border-gray-200 px-4 py-3" placeholder={placeholder} />
                      )
                    })}
                  </div>
                </div>
              </div>

              <div className="border-t border-gray-100 p-6 flex items-center justify-end gap-3">
                <button onClick={closeAddModal} className="rounded-xl border border-gray-200 px-5 py-3 font-bold text-gray-700 hover:bg-gray-50" disabled={addSaving}>
                  Cancel
                </button>
                <button onClick={submitAddJd} className="rounded-xl bg-emerald-600 hover:bg-emerald-700 px-6 py-3 font-black text-white" disabled={addSaving}>
                  {addSaving ? 'Saving…' : 'Create JD'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default JDUpload

// Add custom scrollbar styles
if (typeof document !== 'undefined') {
  const styleSheet = document.createElement("style")
  styleSheet.type = "text/css"
  styleSheet.innerText = `
    .jd-table-scroll::-webkit-scrollbar {
      width: 10px;
      height: 10px;
    }
    .jd-table-scroll::-webkit-scrollbar-track {
      background: #f1f5f9;
      border-radius: 10px;
    }
    .jd-table-scroll::-webkit-scrollbar-thumb {
      background: #10b981;
      border-radius: 10px;
    }
    .jd-table-scroll::-webkit-scrollbar-thumb:hover {
      background: #059669;
    }
  `
  if (!document.head.querySelector('style[data-jd-scrollbar]')) {
    styleSheet.setAttribute('data-jd-scrollbar', 'true')
    document.head.appendChild(styleSheet)
  }
}
