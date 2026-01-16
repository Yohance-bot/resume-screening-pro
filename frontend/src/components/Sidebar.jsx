// src/components/Sidebar.jsx
import React from "react"
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function Sidebar({
  activePage,
  setActivePage,
  fetchCandidates,
  fetchProjects,
}) {
  const navigate = useNavigate()
  const { user } = useAuth()

  const navButtonBase =
    "w-full flex items-center gap-2 text-left px-3 py-2 rounded-xl transition text-sm"
  const inactiveClasses = "hover:bg-white/10 text-emerald-100/80"
  const activeClasses = "bg-emerald-500 text-white shadow-lg"

  return (
    <aside className="w-72 p-1 pl-0 hidden lg:block">
      <div className="h-full rounded-3xl bg-white/10 backdrop-blur-xl border border-white/20 shadow-2xl p-3 flex flex-col">
        {/* Brand */}
        <div className="text-emerald-100 mb-8">
          <div className="text-2xl font-bold mb-1">ResumePro AI</div>
          <div className="text-sm opacity-80">RAG Chatbot</div>
        </div>

        {/* Nav */}
        <nav className="space-y-1">
          <button
            onClick={() => setActivePage("chat")}
            className={`${navButtonBase} ${
              activePage === "chat" ? activeClasses : inactiveClasses
            }`}
          >
            <span className="text-base">💬</span>
            <span>Chat</span>
          </button>

          <button
            onClick={() => setActivePage("resumes")}
            className={`${navButtonBase} ${
              activePage === "resumes" ? activeClasses : inactiveClasses
            }`}
          >
            <span className="text-base">📄</span>
            <span>Upload resumes</span>
          </button>

          <button
            onClick={() => setActivePage("jd")}
            className={`${navButtonBase} ${
              activePage === "jd" ? activeClasses : inactiveClasses
            }`}
          >
            <span className="text-base">📌</span>
            <span>Upload JD</span>
          </button>

          <button
            onClick={() => {
              setActivePage("candidates")
              fetchCandidates()
            }}
            className={`${navButtonBase} ${
              activePage === "candidates" ? activeClasses : inactiveClasses
            }`}
          >
            <span className="text-base">📋</span>
            <span>Candidates</span>
          </button>

          <button
            onClick={() => {
              setActivePage("projects")
              fetchProjects && fetchProjects()
            }}
            className={`${navButtonBase} ${
              activePage === "projects" ? activeClasses : inactiveClasses
            }`}
          >
            <span className="text-base">📂</span>
            <span>Projects</span>
          </button>

          <button
            onClick={() => navigate('/profile')}
            className={`${navButtonBase} ${inactiveClasses}`}
          >
            <span className="text-base">👤</span>
            <span>Profile</span>
          </button>

          {user?.role === 'admin' && (
            <button
              onClick={() => navigate('/admin/users')}
              className={`${navButtonBase} ${inactiveClasses}`}
            >
              <span className="text-base">🛡️</span>
              <span>Manage users</span>
            </button>
          )}
        </nav>

        {/* Hints */}
        <div className="mt-8 text-xs text-emerald-100/70 space-y-1">
          <div>• rank these candidates</div>
          <div>• show Python developers</div>
          <div>• Data Scientist experience</div>
        </div>
      </div>
    </aside>
  )
}
