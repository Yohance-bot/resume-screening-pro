import React, { useState, useRef, useEffect, useCallback } from "react"
import { useLocation } from 'react-router-dom'
import hmBubble from "../assets/hm-bubble.png"

import Sidebar from "../components/Sidebar"
import ChatView from "../components/ChatView"
import ResumesPage from "../components/ResumesPage"
import JdPage from "../components/JdPage"
import CandidatesPage from "../components/CandidatesPage"
import ProjectsPage from "../components/ProjectsPage"
import ProjectTreeModal from "../components/ProjectTreeModal"
import JDUpload from "./JDUpload"

export default function Chat() {
  const location = useLocation()
  const sessionIdRef = useRef(null)
  const [sessionId, setSessionId] = useState(null)
  
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: "assistant",
      content:
        "Hey! I'm your resume RAG assistant 👋\n\nTry: \"rank these candidates\" or \"show Python developers\"",
    },
  ])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  const [activePage, setActivePage] = useState("chat")

  const [selectedFiles, setSelectedFiles] = useState([])
  const [uploadStatus, setUploadStatus] = useState("")

  const [jdText, setJdText] = useState("")
  const [jdStatus, setJdStatus] = useState("")

  const [candidates, setCandidates] = useState([])
  const [candidatesLoading, setCandidatesLoading] = useState(false)
  const [candidatesError, setCandidatesError] = useState("")
  const [expandedId, setExpandedId] = useState(null)

  const [showEditPanel, setShowEditPanel] = useState(false)
  const [editCandidateId, setEditCandidateId] = useState("")
  const [editField, setEditField] = useState("technical_skills")
  const [editAction, setEditAction] = useState("remove")
  const [editValue, setEditValue] = useState("")

  const [showRankPanel, setShowRankPanel] = useState(false)
  const [showJdPanel, setShowJdPanel] = useState(false)
  const [currentJd, setCurrentJd] = useState(null)

  const [projects, setProjects] = useState([])
  const [projectsLoading, setProjectsLoading] = useState(false)
  const [projectsError, setProjectsError] = useState("")
  const [activeProject, setActiveProject] = useState(null)
  const [showTeamPanel, setShowTeamPanel] = useState(false)
  const [selectedProject, setSelectedProject] = useState("")
  const [selectedCandidate, setSelectedCandidate] = useState("")
  const fileInputRef = useRef(null)

  const [isPageTransitioning, setIsPageTransitioning] = useState(false)

  useEffect(() => {
    const nextPage = location?.state?.activePage
    if (nextPage && typeof nextPage === 'string') {
      setActivePage(nextPage)
    }
  }, [location])

  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth", block: "end" })
    }
  }, [messages])

  useEffect(() => {
    if (activePage === 'candidates') {
      fetchCandidates()
    }
    if (activePage === 'projects') {
      fetchProjects()
    }
  }, [activePage])

  const handlePageChange = (page) => {
    setIsPageTransitioning(true)
    setTimeout(() => {
      setActivePage(page)
      setIsPageTransitioning(false)
    }, 200)
  }

  const fetchCandidates = async () => {
    try {
      setCandidatesLoading(true)
      setCandidatesError("")
      const res = await fetch("http://localhost:5050/api/candidates")
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || "Failed to load candidates")

      const normalized = (data.candidates || []).map((c) => {
        if (c.role_bucket) return c
        if (c.bucket) return { ...c, role_bucket: c.bucket }

        const role = (c.primary_role || "").toLowerCase()
        const inferred =
          role.includes("data scientist") ||
          role.includes("machine learning") ||
          role.includes("ml engineer")
            ? "data_scientist"
            : "data_practice"

        return { ...c, role_bucket: inferred }
      })

      setCandidates(normalized)
    } catch (err) {
      setCandidatesError(
        "Failed to load candidates. Check backend /api/candidates.",
      )
    } finally {
      setCandidatesLoading(false)
    }
  }

  const fetchProjects = async () => {
    try {
      setProjectsLoading(true)
      setProjectsError("")
      
      const timestamp = new Date().getTime()
      const res = await fetch(`http://localhost:5050/api/projects?_t=${timestamp}`, {
        cache: 'no-store',
        headers: { 'Cache-Control': 'no-cache' }
      })
      
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || "Failed to load projects")
      
      setProjects([...data.projects || []])
      
    } catch (err) {
      setProjectsError("Failed to load projects. Check backend /api/projects.")
    } finally {
      setProjectsLoading(false)
    }
  }

  const handleRawResponse = useCallback((rawResponse) => {
    // 🔥 JD intercept FIRST
    if (rawResponse?.structured?.type === "jd_details") {
      setShowJdPanel(true)
      setCurrentJd(rawResponse.structured.jd_json)
      setLoading(false)
      return // STOP - don't add to messages
    }

    // Normal flow
    setMessages(prev => [...prev, rawResponse])
    setLoading(false)
  }, [])

  const sendMessage = async (overrideText) => {
    const content = (overrideText ?? input).trim()
    if (!content || loading) return

    // Only run the single-word command shortcuts when the user typed into the box.
    // If a panel passes overrideText, it is already a fully-formed command.
    if (overrideText == null) {
      const trimmed = content.toUpperCase()
      if (trimmed === "EDIT") {
        setShowEditPanel(true)
        setInput("")
        if (candidates.length === 0) fetchCandidates()
        return
      }
      if (trimmed === "RANK") {
        setShowRankPanel(true)
        setInput("")
        if (candidates.length === 0) fetchCandidates()
        return
      }
      if (trimmed === "TEAM") {
        setShowTeamPanel(true)
        setInput("")
        if (candidates.length === 0) fetchCandidates()
        if (projects.length === 0) fetchProjects()
        return
      }
    }

    const userMsg = { id: Date.now(), role: "user", content }
    setMessages((prev) => [...prev, userMsg])
    if (overrideText == null) setInput("")
    setLoading(true)

    try {
      console.log("📤 SENDING TO BACKEND:", {
        session_id: sessionIdRef.current,
        message: userMsg.content
      })

      const res = await fetch("http://localhost:5050/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionIdRef.current,
          message: userMsg.content,
        }),
      })

      const data = await res.json()
      
      // ✅ DEBUG: Log the full response
      console.log("📥 FULL BACKEND RESPONSE:", data)
      console.log("📊 Response structure:", {
        has_message: !!data.message,
        has_structured: !!data.structured,
        structured_type: data.structured?.type,
        structured_data_keys: data.structured?.data ? Object.keys(data.structured.data) : null
      })
      
      if (!res.ok && data?.error) throw new Error(data.error || "Error")

      if (data.session_id) {
        if (!sessionIdRef.current) {
          console.log("🔑 Session ID saved:", data.session_id)
        } else if (sessionIdRef.current !== data.session_id) {
          console.warn("⚠️ Session ID changed! Old:", sessionIdRef.current, "New:", data.session_id)
        } else {
          console.log("✅ Session ID maintained:", data.session_id)
        }
        sessionIdRef.current = data.session_id
        setSessionId(data.session_id)
      } else {
        console.error("❌ No session_id in response!")
      }

      // ✅ Normalize structured so rows are never dropped
      let structured = data.structured || null

      // If backend wrapped rows under structured.data, lift them up
      if (structured?.data && !structured?.rows) {
        structured = {
          ...structured.data,
          type: structured.type || structured.data.type,
        }
      }

      const assistantMsg = {
        id: Date.now() + 1,
        role: "assistant",
        content: data.message || data.response || "No response received.",
        structured, // ✅ guaranteed correct shape for ChatView
      }

      console.log("💬 FINAL assistant message:", assistantMsg)

      handleRawResponse(assistantMsg)
    } catch (err) {
      console.error("❌ Error in sendMessage:", err)
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 2,
          role: "assistant",
          content:
            "Oops! Something went wrong. Check if backend is running on port 5050.",
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const startNewChat = () => {
    setMessages([
      {
        id: 1,
        role: "assistant",
        content:
          "Hey! I'm your resume RAG assistant 👋\n\nTry: \"rank these candidates\" or \"show Python developers\"",
      },
    ])
    sessionIdRef.current = null
    setSessionId(null)
    console.log("🔄 New chat session started - previous context cleared")
  }

  const handleResumeUpload = async () => {
    if (!selectedFiles.length) return
    const formData = new FormData()
    selectedFiles.forEach((f) => formData.append("resumes", f))

    try {
      const res = await fetch("http://localhost:5050/api/upload-resumes", {
        method: "POST",
        body: formData,
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || "Upload failed")
      setUploadStatus(
        `✅ Uploaded ${selectedFiles.length} resumes. Parsed ${
          data.successful || 0
        } successfully, ${data.failed || 0} failed.`,
      )
      setSelectedFiles([])
    } catch (err) {
      setUploadStatus("Failed to upload resumes. Check backend logs.")
    }
  }

  const handleJdSave = async () => {
    if (!jdText.trim()) return
    try {
      const res = await fetch("http://localhost:5050/api/jd", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: jdText }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || "Failed to save JD")
      setJdStatus("JD saved. Ask: rank these candidates for this JD.")
    } catch (err) {
      setJdStatus("Failed to save JD. Check backend.")
    }
  }

  return (
    <div className="relative min-h-screen bg-gradient-to-br from-emerald-900 via-emerald-800 to-amber-500 overflow-hidden">
      
      <div className="relative flex h-screen w-full gap-3 pl-4">
        
        <Sidebar
          activePage={activePage}
          setActivePage={handlePageChange}
          fetchCandidates={fetchCandidates}
          fetchProjects={fetchProjects}
        />

        <div className="relative flex-1 flex flex-col min-w-0 pr-4">
          
          {activePage === "chat" && (
            <div className="pointer-events-none absolute inset-0 flex justify-center items-center z-0">
              <img
                src={hmBubble}
                alt="HM bubble"
                className="w-80 md:w-96 lg:w-[480px] opacity-75 
                         drop-shadow-[0_0_60px_rgba(190,255,190,0.6)] 
                         mix-blend-screen 
                         animate-[pulse_8s_ease-in-out_infinite]
                         transition-all duration-1000"
              />
            </div>
          )}

          <main className={`
            relative z-10 flex-1 flex flex-col min-h-0
            transition-all duration-300 ease-out
            ${isPageTransitioning 
              ? 'opacity-0 scale-95 blur-sm' 
              : 'opacity-100 scale-100 blur-0'
            }
          `}>
            
            {activePage === "chat" && (
              <ChatView
                messages={messages}
                loading={loading}
                bottomRef={bottomRef}
                input={input}
                setInput={setInput}
                sendMessage={sendMessage}
                startNewChat={startNewChat}
                showEditPanel={showEditPanel}
                setShowEditPanel={setShowEditPanel}
                candidates={candidates}
                editCandidateId={editCandidateId}
                setEditCandidateId={setEditCandidateId}
                editField={editField}
                setEditField={setEditField}
                editAction={editAction}
                setEditAction={setEditAction}
                editValue={editValue}
                setEditValue={setEditValue}
                showRankPanel={showRankPanel}
                setShowRankPanel={setShowRankPanel}
                fileInputRef={fileInputRef}
                setMessages={setMessages}
                showTeamPanel={showTeamPanel}          
                setShowTeamPanel={setShowTeamPanel}     
                selectedProject={selectedProject}       
                setSelectedProject={setSelectedProject} 
                selectedCandidate={selectedCandidate}   
                setSelectedCandidate={setSelectedCandidate} 
                projects={projects} 
                fetchProjects={fetchProjects}     
                fetchCandidates={fetchCandidates}
                showJdPanel={showJdPanel}
                setShowJdPanel={setShowJdPanel}
                currentJd={currentJd}
                setCurrentJd={setCurrentJd}
              />
            )}

            {activePage === "resumes" && (
              <ResumesPage
                selectedFiles={selectedFiles}
                setSelectedFiles={setSelectedFiles}
                uploadStatus={uploadStatus}
                handleResumeUpload={handleResumeUpload}
              />
            )}

            {activePage === "jd" && (
              <JDUpload
                jdText={jdText}
                setJdText={setJdText}
                jdStatus={jdStatus}
                handleJdSave={handleJdSave}
              />
            )}

            {activePage === "candidates" && (
              <CandidatesPage
                candidates={candidates}
                candidatesLoading={candidatesLoading}
                candidatesError={candidatesError}
                expandedId={expandedId}
                setExpandedId={setExpandedId}
                fetchCandidates={fetchCandidates}
                setCandidates={setCandidates}
              />
            )}

            {activePage === "projects" && (
              <ProjectsPage 
                onRefresh={async () => {
                  if (!confirm('🔄 Re-process ALL resumes with improved date extraction?\nThis will fix missing project dates.')) return
                  
                  try {
                    setProjectsLoading(true)
                    const res = await fetch("http://localhost:5050/api/normalize-resumes", {
                      method: "POST",
                    })
                    const data = await res.json()
                    if (!res.ok) throw new Error(data.error || "Normalize failed")
                    
                    alert(data.message || "✅ Normalization complete!")
                    await fetchProjects()
                    await fetchCandidates()
                  } catch (err) {
                    alert("Failed to normalize: " + err.message)
                  } finally {
                    setProjectsLoading(false)
                  }
                }}
                projectsLoading={projectsLoading}
                projects={projects}
                projectsError={projectsError}
                setActiveProject={setActiveProject}
              />
            )}
            
          </main>

          {activePage === "projects" && activeProject && (
            <ProjectTreeModal
              project={activeProject}
              onClose={() => setActiveProject(null)}
            />
          )}
          
        </div>
      </div>

      <style>{`
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </div>
  )
}
