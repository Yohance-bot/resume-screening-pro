import React, { useEffect, useState, useRef } from "react"
import TeamManagementPanel from "./TeamManagementPanel"
import RankingTable from "./RankingTable"
import SkillsCategorizedDisplay from "./SkillsCategorizedDisplay"
import FilterHelper from "./FilterHelper"

import LLM_RankingPanel from "./LLM_RankingPanel"

export default function ChatView({
  messages,
  loading,
  bottomRef,
  input,
  setInput,
  sendMessage,
  startNewChat,
  showEditPanel,
  setShowEditPanel,
  candidates,
  editCandidateId,
  setEditCandidateId,
  editField,
  setEditField,
  editAction,
  setEditAction,
  editValue,
  setEditValue,
  showRankPanel,
  setShowRankPanel,
  fileInputRef,
  setMessages,
  showTeamPanel,
  setShowTeamPanel,
  projects,
  selectedProject,
  setSelectedProject,
  selectedCandidate,
  setSelectedCandidate,
  fetchProjects,
  fetchCandidates,
}) {
  const [showLlmRanking, setShowLlmRanking] = useState(false)
  const [jdsList, setJdsList] = useState([])
  const [showJdPanel, setShowJdPanel] = useState(false);
  const [currentJd, setCurrentJd] = useState(null); 

  const openRankPanel = async () => {
    try {
      if (!Array.isArray(jdsList) || jdsList.length === 0) {
        const res = await fetch("http://localhost:5050/api/jds")
        const data = await res.json()
        setJdsList(data)
      }
    } catch (err) {
      console.error("Failed to fetch JDs for ranking", err)
    }

    setShowRankPanel(true)
  }

  // 🔍 Direct "rank #52810" → call /api/llm-rank and render table in chat
  const handleDirectRankIfNeeded = async (text) => {
    const query = (text || "").trim()
    const match = query.match(/^rank\b.*?#\s*([0-9]+)/i)
    if (!match) return false

    const sid = match[1]
    try {
      const res = await fetch("http://localhost:5050/api/llm-rank", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sid,
          bucket: "all",
          bench_status: "all",
        }),
      })

      const data = await res.json()
      if (!res.ok || data.success === false || data.error) {
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            role: "assistant",
            content:
              data.error ||
              `Failed to rank candidates for JD #${sid}.`,
          },
        ])
        return true
      }

      const rows =
        (data.rankings || []).map((r, idx) => ({
          rank: r.rank ?? idx + 1,
          name: r.candidate_name,
          score: r.score,
          experience: "",
          skills: "",
          reason: r.reasoning,
        })) || []

      const assistantMsg = {
        id: Date.now() + 2,
        role: "assistant",
        content: `AI-ranked top ${rows.length} candidates for JD #${sid}.`,
        structured: {
          type: "ranking",
          rows,
          role: data.jd?.title || "",
          total_candidates: data.total_candidates ?? rows.length,
        },
      }

      setMessages((prev) => [...prev, assistantMsg])
    } catch (err) {
      console.error("Direct rank failed", err)
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 3,
          role: "assistant",
          content:
            "Failed to call /api/llm-rank. Check if backend is running.",
        },
      ])
    }

    return true
  }
  const handleChatResponse = async (assistantMsg) => {
    console.log("🎯 FULL RESPONSE:", assistantMsg?.structured) // DEBUG

    // ✅ JD DETAILS (safe-guarded)
    if (assistantMsg?.structured?.type === "jd_details") {
      console.log("🎯 JD DETAILS PANEL:", assistantMsg.structured)
      if (typeof setShowJdPanel === "function") setShowJdPanel(true)
      if (typeof setCurrentJd === "function")
        setCurrentJd(assistantMsg.structured.jd_json)
      return
    }

    // ✅ Existing LLM ranking trigger (lower priority fallback)
    if (
      assistantMsg?.structured?.action === "open_llm_ranking" ||
      assistantMsg?.content?.toUpperCase().includes("LLM RANK")
    ) {
      try {
        const res = await fetch("http://localhost:5050/api/jds")
        const data = await res.json()
        setJdsList(data)
        setShowLlmRanking(true)
      } catch (err) {
        console.error("Failed to fetch JDs for LLM ranking", err)
      }
    }
  }

  // ✅ Auto-fetch candidates when edit panel opens
  useEffect(() => {
    if (showEditPanel && (!candidates || candidates.length === 0)) {
      console.log("🔄 Edit panel opened - fetching candidates...")
      fetchCandidates()
    }
  }, [showEditPanel, candidates, fetchCandidates])

  // ✅ Auto-fetch projects when team panel opens
  useEffect(() => {
    if (showTeamPanel && (!projects || projects.length === 0)) {
      console.log("🔄 Team panel opened - fetching projects...")
      fetchProjects()
    }
  }, [showTeamPanel, projects, fetchProjects])

  return (
    <div className="flex flex-col h-full">
      {/* ✨ Messages Container - Scrollable */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden">
        {showJdPanel && currentJd && (
          <div className="jd-panel p-6 bg-gradient-to-br from-blue-500/10 to-emerald-500/10 rounded-3xl border border-blue-200/50 mb-6 mx-8 mt-6">
            <div className="flex items-center gap-3 mb-4 justify-between">
              <h3 className="text-2xl font-black text-white drop-shadow-lg">
                📄 JD #{currentJd.sid}
              </h3>
              <button
                onClick={() => setShowJdPanel(false)}
                className="text-white/80 hover:text-white transition-transform hover:scale-110 active:scale-95"
              >
                ✕
              </button>
            </div>

            <div className="grid md:grid-cols-2 gap-6 text-sm">
              <div>
                <strong className="text-emerald-100 block mb-1">
                  Role:
                </strong>
                <span className="inline-block bg-white/10 px-3 py-1 rounded-xl text-white/90">
                  {currentJd.designation}
                </span>
              </div>

              <div>
                <strong className="text-emerald-100 block mb-1">
                  Description:
                </strong>
                <p className="text-white/90 leading-relaxed">
                  {currentJd.job_description}
                </p>
              </div>
            </div>
          </div>
        )}
        
        {/* ✨ Premium Header - Scrolls with content */}
        <div className="relative px-8 pt-8 pb-6 border-b border-white/20 overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-r from-emerald-500/10 via-blue-500/10 to-purple-500/10 
                        animate-[gradientShift_8s_ease-in-out_infinite]" />
          
          <div className="absolute inset-0 overflow-hidden">
            <div className="absolute top-1/4 left-1/4 w-32 h-32 bg-emerald-400/20 rounded-full blur-3xl 
                          animate-[float_6s_ease-in-out_infinite]" />
            <div className="absolute top-1/3 right-1/4 w-40 h-40 bg-blue-400/20 rounded-full blur-3xl 
                          animate-[float_8s_ease-in-out_infinite_reverse]" />
          </div>

          <div className="relative flex justify-between items-center">
            <div className="flex items-center gap-4">
              <div className="relative group">
                <div className="absolute inset-0 bg-gradient-to-br from-emerald-400 to-blue-500 
                              rounded-2xl blur-xl opacity-50 group-hover:opacity-75 
                              transition-opacity duration-500" />
                <div className="relative bg-gradient-to-br from-emerald-500 to-blue-600 
                              rounded-2xl p-3 shadow-2xl
                              transform group-hover:scale-110 transition-transform duration-300">
                  <span className="text-4xl filter drop-shadow-lg">💬</span>
                </div>
              </div>

              <div>
                <h1 className="text-4xl font-black text-transparent bg-clip-text 
                             bg-gradient-to-r from-white via-emerald-100 to-blue-100
                             drop-shadow-[0_2px_10px_rgba(255,255,255,0.3)]
                             tracking-tight">
                  CHAT
                </h1>
                <div className="flex items-center gap-2 mt-1.5">
                  <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse shadow-lg 
                                shadow-emerald-400/50" />
                  <p className="text-white/70 text-sm font-medium tracking-wide">
                    Ask questions about your candidates
                  </p>
                </div>
              </div>
            </div>

            <button
              onClick={startNewChat}
              className="group relative rounded-2xl bg-white/10 hover:bg-white/20 backdrop-blur-xl 
                       text-white text-sm font-bold px-6 py-3.5 
                       shadow-[0_8px_30px_rgb(0,0,0,0.12)] 
                       hover:shadow-[0_8px_40px_rgb(16,185,129,0.4)]
                       border border-white/20 hover:border-emerald-400/50
                       transition-all duration-300 ease-out
                       hover:scale-105 active:scale-95
                       overflow-hidden"
            >
              <div className="absolute inset-0 -translate-x-full group-hover:translate-x-full 
                            transition-transform duration-1000 ease-out
                            bg-gradient-to-r from-transparent via-white/30 to-transparent" />
              
              <div className="absolute inset-0 opacity-0 group-hover:opacity-100 
                            transition-opacity duration-300
                            bg-gradient-to-r from-emerald-400/20 to-blue-400/20 blur-xl" />
              
              <span className="relative flex items-center gap-2.5">
                <span className="text-lg transition-transform duration-300 
                               group-hover:rotate-90 group-hover:scale-110">
                  ✨
                </span>
                <span className="tracking-wide">New Chat</span>
              </span>
            </button>
          </div>

          <div className="absolute bottom-0 left-0 right-0 h-px 
                        bg-gradient-to-r from-transparent via-emerald-400/50 to-transparent" />
        </div>

        {/* Messages */}
        <div className="px-8 py-6 space-y-6 scroll-smooth">
          {messages.map((message, index) => (
            <MessageBubble key={`${message.id}-${index}`} message={message} index={index} />
          ))}

          
          {/* 🐢 FORCED TURTLE LOADER */}
          {loading === true && (
            <div className="flex justify-center py-10">
              <div className="flex items-center gap-4 animate-pulse">
                <div className="relative w-24 h-24 animate-spin-slow">
                  {/* Shell */}
                  <div className="absolute inset-0 bg-gradient-to-br from-amber-400 to-orange-400 rounded-full shadow-lg"></div>
                  {/* Body */}
                  <div className="absolute inset-2 bg-emerald-400 rounded-full"></div>
                  {/* Head */}
                  <div className="absolute -top-2 -left-2 w-8 h-8 bg-emerald-500 rounded-full shadow-md animate-bounce [animation-delay:0.1s]"></div>
                  {/* Legs */}
                  <div className="absolute -bottom-1 left-1 w-3 h-3 bg-emerald-500 rounded-full animate-bounce"></div>
                  <div className="absolute -bottom-1 right-1 w-3 h-3 bg-emerald-500 rounded-full animate-bounce [animation-delay:0.2s]"></div>
                </div>
                <div className="text-emerald-300 font-semibold text-lg tracking-wide">
                  🧠 Thinking...
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* ✨ Fixed Input Section at Bottom */}
      <div className="flex-shrink-0 px-8 pb-8 pt-4 
                    bg-gradient-to-t from-emerald-900/80 via-emerald-900/40 to-transparent 
                    backdrop-blur-xl border-t border-white/10">
        
        {/* ✏️ EDIT PANEL - Improved with loading state */}
        {showEditPanel && (
          <div className="mb-4 rounded-2xl bg-white/95 shadow-[0_8px_30px_rgb(0,0,0,0.2)] 
                        border border-white/50 px-6 py-5 backdrop-blur-xl 
                        animate-[slideDown_0.3s_ease-out]">
            <div className="flex justify-between items-center mb-4">
              <div className="flex items-center gap-2">
                <span className="text-2xl">✏️</span>
                <h3 className="text-base font-bold text-emerald-900 uppercase tracking-wide">
                  Edit Candidate
                </h3>
              </div>
              <button
                onClick={() => setShowEditPanel(false)}
                className="text-sm text-emerald-700 hover:text-emerald-900 font-medium
                         transition-colors hover:scale-110 active:scale-95"
              >
                ✕ Close
              </button>
            </div>

            {/* Loading state if no candidates */}
            {(!candidates || candidates.length === 0) ? (
              <div className="text-center py-8">
                <div className="inline-block animate-spin rounded-full h-10 w-10 border-3 border-emerald-200 border-t-emerald-600 mb-4"></div>
                <p className="text-emerald-700 text-sm font-semibold mb-1">Loading candidates...</p>
                <p className="text-emerald-600 text-xs">
                  Please wait while we fetch candidate data
                </p>
              </div>
            ) : (
              <>
                <div className="grid gap-4 md:grid-cols-3">
                  {/* Candidate Selector */}
                  <div>
                    <label className="block text-xs font-bold text-emerald-900 mb-2 uppercase tracking-wide">
                      Candidate
                    </label>
                    <select
                      className="w-full rounded-xl border-2 border-emerald-200 bg-white 
                               px-4 py-3 text-sm text-emerald-900 font-medium
                               focus:outline-none focus:ring-2 focus:ring-emerald-500 
                               focus:border-emerald-500 transition-all
                               hover:border-emerald-300"
                      value={editCandidateId}
                      onChange={(e) => setEditCandidateId(e.target.value)}
                    >
                      <option value="">Select candidate...</option>
                      {candidates.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.full_name || c.name || 'Unnamed'} (ID {c.id})
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Field Selector */}
                  <div>
                    <label className="block text-xs font-bold text-emerald-900 mb-2 uppercase tracking-wide">
                      Field
                    </label>
                    <select
                      className="w-full rounded-xl border-2 border-emerald-200 bg-white 
                               px-4 py-3 text-sm text-emerald-900 font-medium
                               focus:outline-none focus:ring-2 focus:ring-emerald-500 
                               focus:border-emerald-500 transition-all
                               hover:border-emerald-300"
                      value={editField}
                      onChange={(e) => setEditField(e.target.value)}
                    >
                      <option value="technical_skills">📊 Technical Skills</option>
                      <option value="skills">🎯 Skills</option>
                      <option value="projects">📁 Projects</option>
                      <option value="work_experiences">💼 Work Experience</option>
                      <option value="email">📧 Email</option>
                      <option value="phone">📱 Phone</option>
                      <option value="primary_role">👔 Primary Role</option>
                    </select>
                  </div>

                  {/* Action Selector */}
                  <div>
                    <label className="block text-xs font-bold text-emerald-900 mb-2 uppercase tracking-wide">
                      Action
                    </label>
                    <select
                      className="w-full rounded-xl border-2 border-emerald-200 bg-white 
                               px-4 py-3 text-sm text-emerald-900 font-medium
                               focus:outline-none focus:ring-2 focus:ring-emerald-500 
                               focus:border-emerald-500 transition-all
                               hover:border-emerald-300"
                      value={editAction}
                      onChange={(e) => setEditAction(e.target.value)}
                    >
                      <option value="remove">🗑️ Remove</option>
                      <option value="add">➕ Add</option>
                      <option value="set">🔄 Set/Replace</option>
                    </select>
                  </div>
                </div>

                {/* Value Input */}
                <div className="mt-4">
                  <label className="block text-xs font-bold text-emerald-900 mb-2 uppercase tracking-wide">
                    {editField === "technical_skills" || editField === "skills"
                      ? "Skill to add/remove"
                      : editField === "projects" || editField === "work_experiences"
                      ? "Describe the change"
                      : "New value"}
                  </label>
                  <input
                    className="w-full rounded-xl border-2 border-emerald-200 bg-white 
                             px-4 py-3 text-sm text-emerald-900 
                             focus:outline-none focus:ring-2 focus:ring-emerald-500 
                             focus:border-emerald-500 transition-all
                             hover:border-emerald-300
                             placeholder:text-emerald-400"
                    placeholder={
                      editField === "technical_skills" || editField === "skills"
                        ? "e.g. PySpark"
                        : editField === "email"
                        ? "e.g. user@example.com"
                        : editField === "phone"
                        ? "e.g. +1-234-567-8900"
                        : "Enter new value..."
                    }
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                  />
                </div>

                {/* Action Buttons */}
                <div className="mt-5 flex justify-end gap-3">
                  <button
                    onClick={() => {
                      setShowEditPanel(false)
                      setEditCandidateId("")
                      setEditValue("")
                    }}
                    className="px-5 py-2.5 rounded-xl border-2 border-emerald-200 
                             text-emerald-800 hover:bg-emerald-50 font-semibold text-sm
                             transition-all hover:scale-105 active:scale-95
                             hover:border-emerald-300"
                  >
                    Cancel
                  </button>
                  <button
                    disabled={!editCandidateId || !editField || !editValue}
                    onClick={() => {
                      if (!editCandidateId || !editField || !editValue) return
                      const fieldLabel =
                        editField === "technical_skills"
                          ? "technical skills"
                          : editField.replace("_", " ")
                      const actionWord =
                        editAction === "remove"
                          ? "remove"
                          : editAction === "add"
                          ? "add"
                          : "set"
                      const msg = `EDIT ${actionWord} ${editValue} in ${fieldLabel} of candidate ${editCandidateId}`
                      setInput(msg)
                      setShowEditPanel(false)
                      setEditCandidateId("")
                      setEditValue("")
                    }}
                    className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 
                             text-white font-bold text-sm shadow-lg disabled:opacity-40
                             hover:from-emerald-600 hover:to-emerald-700
                             transition-all hover:scale-105 active:scale-95
                             disabled:hover:scale-100 disabled:cursor-not-allowed
                             hover:shadow-xl"
                  >
                    Prepare Command
                  </button>
                </div>
              </>
            )}
          </div>
        )}
        {/* Quick Action Pills */}
        <div className="flex gap-2 mb-4 justify-center">
          <FilterHelper setMessages={setMessages} />
          <ActionPill 
            icon="✏️" 
            label="Edit" 
            onClick={() => setShowEditPanel(true)} 
          />
          <ActionPill 
            icon="📊" 
            label="Rank" 
            onClick={openRankPanel} 
          />
          <ActionPill 
            icon="👥" 
            label="Team" 
            onClick={() => setShowTeamPanel(true)} 
          />
        </div>

        {/* Main Input Area */}
        <div className="relative max-w-5xl mx-auto">
          <div className="flex gap-3 items-end">
            <input
              type="file"
              accept=".pdf,.docx"
              multiple
              ref={fileInputRef}
              style={{ display: "none" }}
              onChange={async (e) => {
                const files = Array.from(e.target.files || [])
                if (!files.length) return

                const formData = new FormData()
                files.forEach((f) => formData.append("resumes", f))

                try {
                  const res = await fetch(
                    "http://localhost:5050/api/upload-resumes",
                    {
                      method: "POST",
                      body: formData,
                    },
                  )
                  const data = await res.json()
                  if (!res.ok) throw new Error(data.error || "Upload failed")

                  const successful = data.successful ?? files.length
                  const failed = data.failed ?? 0

                  const assistantMsg = {
                    id: Date.now(),
                    role: "assistant",
                    content: `✅ Uploaded ${files.length} resume(s) from chat. Parsed ${successful} successfully, ${failed} failed.`,
                    structured: {
                      type: "resume_added_from_chat",
                      successful,
                      failed,
                    },
                  }
                  setMessages((prev) => [...prev, assistantMsg])
                } catch (err) {
                  setMessages((prev) => [
                    ...prev,
                    {
                      id: Date.now() + 1,
                      role: "assistant",
                      content:
                        "Failed to upload files from chat. Check backend /api/upload-resumes.",
                    },
                  ])
                } finally {
                  e.target.value = ""
                }
              }}
            />

            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="group rounded-2xl bg-white/10 hover:bg-white/20 backdrop-blur-xl 
                       text-white p-3.5 shadow-lg border border-white/20 hover:border-white/30
                       transition-all duration-300 hover:scale-110 active:scale-95"
              title="Attach PDF/DOCX"
            >
              <span className="text-xl transition-transform duration-300 group-hover:rotate-12">
                📎
              </span>
            </button>

            <div className="flex-1 relative group">
              <div className="absolute -inset-0.5 bg-gradient-to-r from-emerald-400 to-blue-400 
                            rounded-3xl opacity-0 group-hover:opacity-20 group-focus-within:opacity-30 
                            blur transition-opacity duration-300" />
              
              <div className="relative">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={async (e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  // sendMessage() will be refactored below
                  if (loading || !input.trim()) return
                  // User message object
                  const userMsg = {
                    id: Date.now(),
                    role: "user",
                    content: input,
                  }
                  // --- RANKING/JDS logic
                  const upper = input.toUpperCase()
                  const isDirectRankBySid =
                    /^rank\b/i.test(input.trim()) &&
                    /#\s*[0-9]+/.test(input)
                  if (!isDirectRankBySid && (upper.includes("RANKING") || upper.includes("RANK"))) {
                    try {
                      const res = await fetch("http://localhost:5050/api/jds")
                      const data = await res.json()
                      setJdsList(data)
                      setShowLlmRanking(true)
                    } catch (err) {
                      console.error("Failed to fetch JDs for ranking", err)
                    }
                  }
                  setMessages((prev) => [...prev, userMsg])
                  setInput("")
                  try {
                    // Direct "rank #SID" → call llm-rank and skip /api/chat
                    const handled = await handleDirectRankIfNeeded(input)
                    if (handled) return

                    const res = await fetch("http://localhost:5050/api/chat", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ message: input }),
                    })
                    const data = await res.json()
                    // Use the canonical assistantMsg construction:
                    const assistantMsg = {
                      id: Date.now(),
                      role: "assistant",
                      content: data.message,
                      structured: data.structured,
                    }
                    handleChatResponse(assistantMsg)
                    setMessages((prev) => [...prev, assistantMsg])
                  } catch (err) {
                    setMessages((prev) => [
                      ...prev,
                      {
                        id: Date.now() + 1,
                        role: "assistant",
                        content: "Failed to get response from /api/chat.",
                      },
                    ])
                  }
                }
              }}
              placeholder="Ask about your candidates... (Shift + Enter for new line)"
              rows={1}
              className="w-full rounded-3xl px-6 py-4 pr-14
                       bg-white/95 backdrop-blur-xl
                       text-gray-800 placeholder-gray-400
                       shadow-[0_8px_30px_rgb(0,0,0,0.15)]
                       border-2 border-white/50 
                       focus:border-emerald-400/50
                       focus:outline-none focus:ring-4 focus:ring-emerald-400/20
                       transition-all duration-300 resize-none
                       text-[15px] leading-relaxed"
              style={{ 
                minHeight: '56px',
                maxHeight: '200px'
              }}
              onInput={(e) => {
                e.target.style.height = 'auto'
                e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px'
              }}
            />
                
                {input.length > 0 && (
                  <div className="absolute bottom-2 right-16 text-xs text-gray-400">
                    {input.length}
                  </div>
                )}
              </div>
            </div>

            <button
              onClick={async () => {
                if (loading || !input.trim()) return
                // User message object
                const userMsg = {
                  id: Date.now(),
                  role: "user",
                  content: input,
                }
                // --- RANKING/JDS logic
                const upper = input.toUpperCase()
                const isDirectRankBySid =
                  /^rank\b/i.test(input.trim()) &&
                  /#\s*[0-9]+/.test(input)
                if (!isDirectRankBySid && (upper.includes("RANKING") || upper.includes("RANK"))) {
                  try {
                    const res = await fetch("http://localhost:5050/api/jds")
                    const data = await res.json()
                    setJdsList(data)
                    setShowLlmRanking(true)
                  } catch (err) {
                    console.error("Failed to fetch JDs for ranking", err)
                  }
                }
                setMessages((prev) => [...prev, userMsg])
                setInput("")
                try {
                  // Direct "rank #SID" → call llm-rank and skip /api/chat
                  const handled = await handleDirectRankIfNeeded(input)
                  if (handled) return

                  const res = await fetch("http://localhost:5050/api/chat", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ message: input }),
                  })
                  const data = await res.json()
                  // Use the canonical assistantMsg construction:
                  const assistantMsg = {
                    id: Date.now(),
                    role: "assistant",
                    content: data.message,
                    structured: data.structured,
                  }
                  handleChatResponse(assistantMsg)
                  setMessages((prev) => [...prev, assistantMsg])
                } catch (err) {
                  setMessages((prev) => [
                    ...prev,
                    {
                      id: Date.now() + 1,
                      role: "assistant",
                      content: "Failed to get response from /api/chat.",
                    },
                  ])
                }
              }}
              disabled={loading || !input.trim()}
              className="group relative rounded-2xl bg-gradient-to-r from-emerald-500 to-emerald-600 
                       hover:from-emerald-600 hover:to-emerald-700
                       text-white px-8 py-4 font-semibold 
                       shadow-[0_8px_30px_rgb(16,185,129,0.4)]
                       hover:shadow-[0_12px_40px_rgb(16,185,129,0.5)]
                       transition-all duration-300 
                       hover:scale-105 active:scale-95
                       disabled:opacity-50 disabled:cursor-not-allowed 
                       disabled:hover:scale-100 disabled:shadow-lg
                       overflow-hidden min-w-[100px]"
            >
              <div className="absolute inset-0 -translate-x-full group-hover:translate-x-full 
                            transition-transform duration-700 ease-out
                            bg-gradient-to-r from-transparent via-white/30 to-transparent" />
              
              <span className="relative flex items-center gap-2">
                {loading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white 
                                  rounded-full animate-spin" />
                    <span>Sending</span>
                  </>
                ) : (
                  <>
                    <span>Send</span>
                    <span className="transition-transform duration-300 group-hover:translate-x-1">
                      →
                    </span>
                  </>
                )}
              </span>
            </button>
          </div>

          <p className="text-center text-white/50 text-xs mt-3 flex items-center justify-center gap-2">
            <span>💡</span>
            <span>
              Press <kbd className="px-2 py-0.5 bg-white/10 rounded border border-white/20 font-mono text-[10px]">Enter</kbd> to send,{" "}
              <kbd className="px-2 py-0.5 bg-white/10 rounded border border-white/20 font-mono text-[10px]">Shift+Enter</kbd> for new line
            </span>
          </p>

          <div className="text-xs text-white/40 mt-2 text-center">
            Backend: localhost:5050 | Your RAG resumes in ChromaDB
          </div>
        </div>
      </div>

      {showLlmRanking && (
        <LLM_RankingPanel
          jdsList={jdsList}
          onClose={() => setShowLlmRanking(false)}
          sendMessage={sendMessage}
        />
      )}

      {showRankPanel && (
        <LLM_RankingPanel
          jdsList={jdsList}
          onClose={() => setShowRankPanel(false)}
          sendMessage={sendMessage}
        />
      )}

      <TeamManagementPanel
        showTeamPanel={showTeamPanel}
        setShowTeamPanel={setShowTeamPanel}
        projects={projects}
        candidates={candidates}
        selectedProject={selectedProject}
        setSelectedProject={setSelectedProject}
        selectedCandidate={selectedCandidate}
        setSelectedCandidate={setSelectedCandidate}
        fetchProjects={fetchProjects}
      />

      <style>{`
        @keyframes gradientShift {
          0%, 100% { transform: translateX(0%) scale(1); }
          50% { transform: translateX(10%) scale(1.1); }
        }

        @keyframes float {
          0%, 100% { 
            transform: translate(0, 0) scale(1);
          }
          33% { 
            transform: translate(30px, -30px) scale(1.1);
          }
          66% { 
            transform: translate(-20px, 20px) scale(0.9);
          }
        }

        @keyframes messageSlide {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes slideDown {
          from {
            opacity: 0;
            transform: translateY(-10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes wiggle {
          0%, 100% {
            transform: rotate(-5deg);
          }
          50% {
            transform: rotate(5deg);
          }
        }

        .overflow-y-auto::-webkit-scrollbar {
          width: 8px;
        }

        .overflow-y-auto::-webkit-scrollbar-track {
          background: rgba(255, 255, 255, 0.05);
          border-radius: 10px;
        }

        .overflow-y-auto::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.2);
          border-radius: 10px;
          transition: background 0.3s;
        }

        .overflow-y-auto::-webkit-scrollbar-thumb:hover {
          background: rgba(255, 255, 255, 0.3);
        }
      `}</style>
      
    </div>
  )
}

function MessageBubble({ message }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end animate-[messageSlide_0.4s_ease-out]">
        <div className="max-w-4xl bg-gradient-to-r from-emerald-500 to-green-500 text-white rounded-3xl rounded-br-md p-6 shadow-xl">
          <FormattedMessage content={message.content} />
        </div>
      </div>
    )
  }

  const structured = message.structured

  if (!structured) {
    return (
      <div className="flex justify-start animate-[messageSlide_0.4s_ease-out]">
        <div className="max-w-5xl bg-white/95 rounded-3xl rounded-bl-md p-6 shadow-lg">
          <FormattedMessage content={message.content} />
        </div>
      </div>
    )
  }

  if (
    structured?.type === "skills_display" ||
    structured?.data?.skills_by_category
  ) {
    return (
      <div className="flex justify-start animate-[messageSlide_0.4s_ease-out]">
        <div className="max-w-4xl bg-white/95 rounded-3xl rounded-bl-md p-6 shadow-lg">
          <SkillsCategorizedDisplay data={structured.data} />
        </div>
      </div>
    )
  }

  if (structured?.type === "skills_table") {
    return (
      <div className="flex justify-start animate-[messageSlide_0.4s_ease-out]">
        <div className="max-w-4xl bg-white/95 rounded-3xl rounded-bl-md p-6 shadow-lg">
          <FormattedMessage content={message.content} />
          <div className="mt-4">
            <SkillsTable data={structured.data} />
          </div>
        </div>
      </div>
    )
  }

  if (structured?.type === "projects_table") {
    return (
      <div className="flex justify-start animate-[messageSlide_0.4s_ease-out]">
        <div className="max-w-5xl bg-white/95 rounded-3xl rounded-bl-md p-6 shadow-lg">
          <FormattedMessage content={message.content} />
          <div className="mt-4">
            <ProjectsTable data={structured.data} />
          </div>
        </div>
      </div>
    )
  }

  if (structured?.type === "candidate_table") {
    return (
      <div className="flex justify-start animate-[messageSlide_0.4s_ease-out]">
        <div className="max-w-5xl bg-white/95 rounded-3xl rounded-bl-md p-6 shadow-lg">
          <FormattedMessage content={message.content} />
          <div className="mt-4">
            <CandidateTable data={structured} />
          </div>
        </div>
      </div>
    )
  }

  if (structured?.type === "jd_detail") {
    const jd = structured.data || {}
    return (
      <div className="flex justify-start animate-[messageSlide_0.4s_ease-out]">
        <div className="max-w-5xl bg-white/95 rounded-3xl rounded-bl-md p-6 shadow-lg">
          <JDDetailTable jd={jd} />
        </div>
      </div>
    )
  }

  if (structured?.type === "ranking") {
  const rankingData = structured.data || structured
  return (
    <div className="flex justify-start animate-[messageSlide_0.4s_ease-out]">
      <div className="max-w-5xl bg-white/95 rounded-3xl rounded-bl-md p-6 shadow-lg">
        <FormattedMessage content={message.content} />
        <RankingTable data={rankingData} />
      </div>
    </div>
  )
}

  return (
    <div className="flex justify-start animate-[messageSlide_0.4s_ease-out]">
      <div className="max-w-4xl bg-white/95 rounded-3xl rounded-bl-md p-6 shadow-lg">
        <FormattedMessage content={message.content} />
      </div>
    </div>
  )
}

function FormattedMessage({ content }) {
  if (!content) return null

  const lines = content.split('\n')
  
  return (
    <div className="space-y-2">
      {lines.map((line, idx) => {
        if (line.includes('**')) {
          const formatted = line.replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-gray-900">$1</strong>')
          return (
            <p key={idx} dangerouslySetInnerHTML={{ __html: formatted }} 
               className="text-gray-800" />
          )
        }
        
        if (line.trim().startsWith('•')) {
          return (
            <div key={idx} className="flex items-start gap-2 ml-4">
              <span className="text-emerald-600 font-bold">•</span>
              <span className="text-gray-700">{line.replace('•', '').trim()}</span>
            </div>
          )
        }
        
        if (!line.trim()) {
          return <div key={idx} className="h-1" />
        }
        
        return <p key={idx} className="text-gray-700">{line}</p>
      })}
    </div>
  )
}

function SkillsTable({ data }) {
  const categories = data.skills_by_category || {}

  return (
    <div className="space-y-4">
      {Object.entries(categories).map(([category, skills]) =>
        skills.length > 0 ? (
          <div key={category}>
            <h4 className="text-emerald-600 font-semibold mb-2 text-sm">{category}</h4>
            <div className="flex flex-wrap gap-2">
              {skills.map((skill, idx) => (
                <span
                  key={idx}
                  className="px-3 py-1 bg-emerald-50 text-emerald-700 
                             rounded-lg text-sm border border-emerald-200"
                >
                  {skill}
                </span>
              ))}
            </div>
          </div>
        ) : null
      )}
    </div>
  )
}

function ProjectsTable({ data }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200">
      <table className="w-full text-left text-gray-700 text-sm">
        <thead className="bg-gray-100">
          <tr>
            <th className="px-4 py-3 font-semibold">Project</th>
            <th className="px-4 py-3 font-semibold">Role</th>
            <th className="px-4 py-3 font-semibold">Duration</th>
            <th className="px-4 py-3 font-semibold">Technologies</th>
          </tr>
        </thead>
        <tbody>
          {data.projects?.map((proj, idx) => (
            <tr key={idx} className="border-t border-gray-200 hover:bg-gray-50">
              <td className="px-4 py-3 font-medium">{proj.name}</td>
              <td className="px-4 py-3">{proj.role}</td>
              <td className="px-4 py-3">{proj.duration}</td>
              <td className="px-4 py-3">
                <div className="flex flex-wrap gap-1">
                  {proj.technologies?.map((tech, tIdx) => (
                    <span
                      key={tIdx}
                      className="px-2 py-1 bg-emerald-100 text-emerald-800 text-xs rounded-full"
                    >
                      {tech}
                    </span>
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CandidateTable({ data }) {
  const { rows = [], headers = [] } = data || {}

  if (!rows.length) {
    return (
      <div className="text-center py-8 text-gray-400">
        No candidates found
      </div>
    )
  }

  const colWidths = ["w-16", "w-56", "w-48", "w-28", "w-28", "w-[520px]", "w-64"]

  return (
    <div className="w-full overflow-x-auto rounded-xl border border-gray-200 bg-white">
      <table className="min-w-max border-collapse text-left text-gray-700 text-sm">
        <thead className="bg-gray-100">
          <tr>
            {headers.map((header, idx) => (
              <th
                key={idx}
                className={`px-3 py-2 font-semibold whitespace-nowrap ${colWidths[idx] || ""}`}
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rIdx) => (
            <tr key={rIdx} className="border-t border-gray-200 hover:bg-gray-50">
              {(row.cells || Object.values(row)).map((cell, cIdx) => (
                <td
                  key={cIdx}
                  className={`px-3 py-2 align-top ${colWidths[cIdx] || ""}`}
                >
                  <div
                    className={
                      cIdx === headers.findIndex((h) => String(h).toLowerCase().includes("skill"))
                        ? "max-h-24 overflow-y-auto whitespace-pre-wrap break-words"
                        : "whitespace-nowrap overflow-hidden text-ellipsis"
                    }
                    title={typeof cell === "string" ? cell : undefined}
                  >
                    {cell}
                  </div>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function JDDetailTable({ jd }) {
  if (!jd) return null

  const skills = jd.skills || []
  const skillsStr = skills.length ? skills.join(", ") : "—"

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold text-gray-900">
          📄 JD #{jd.sid}
        </h3>
      </div>

      <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
        <table className="w-full text-left text-sm text-gray-800 border-collapse">
          <tbody>
            <tr className="border-b border-gray-200">
              <th className="w-40 px-4 py-3 font-semibold text-gray-500">
                Title
              </th>
              <td className="px-4 py-3">
                {jd.title}
              </td>
            </tr>
            <tr className="border-b border-gray-200">
              <th className="px-4 py-3 font-semibold text-gray-500">
                Account / Project
              </th>
              <td className="px-4 py-3">
                {jd.account} {jd.project && " / " + jd.project}
              </td>
            </tr>
            <tr className="border-b border-gray-200">
              <th className="px-4 py-3 font-semibold text-gray-500">
                Competency
              </th>
              <td className="px-4 py-3">
                {jd.competency}
              </td>
            </tr>
            <tr className="border-b border-gray-200">
              <th className="px-4 py-3 font-semibold text-gray-500">
                Location
              </th>
              <td className="px-4 py-3">
                {jd.base_location_city}{" "}
                {jd.base_location_country && ` ${jd.base_location_country}`}{" "}
                {jd.location_type && ` (${jd.location_type})`}
              </td>
            </tr>
            <tr className="border-b border-gray-200">
              <th className="px-4 py-3 font-semibold text-gray-500">
                Billability / CTC
              </th>
              <td className="px-4 py-3">
                {jd.billability || "—"}{" "}
                {jd.ctc_rate && `| ${jd.ctc_rate}`}
              </td>
            </tr>
            <tr className="border-b border-gray-200 align-top">
              <th className="px-4 py-3 font-semibold text-gray-500">
                Skills
              </th>
              <td className="px-4 py-3 whitespace-pre-wrap">
                {skillsStr}
              </td>
            </tr>
            <tr className="align-top">
              <th className="px-4 py-3 font-semibold text-gray-500">
                Description
              </th>
              <td className="px-4 py-3">
                <div className="max-h-64 overflow-y-auto rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm whitespace-pre-wrap">
                  {jd.description}
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ActionPill({ icon, label, onClick }) {
  return (
    <button
      onClick={onClick}
      className="group flex items-center gap-2 px-4 py-2.5
               bg-white/80 hover:bg-white rounded-xl
               shadow-lg hover:shadow-emerald-500/25
               border border-white/50 text-emerald-900
               font-semibold text-sm transition-all duration-300
               hover:scale-105 active:scale-95"
    >
      <span className="text-lg transition-transform duration-300 group-hover:scale-125">
        {icon}
      </span>
      <span>{label}</span>
    </button>
  )
}
