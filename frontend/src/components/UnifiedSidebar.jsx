import React from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function UnifiedSidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuth()

  const navButtonBase =
    'w-full flex items-center gap-2 text-left px-3 py-2 rounded-xl transition text-sm'
  const inactiveClasses = 'hover:bg-white/10 text-emerald-100/80'
  const activeClasses = 'bg-emerald-500 text-white shadow-lg'

  const isActivePath = (path) => location.pathname === path

  const goChatView = (activePage) => {
    navigate('/chat', { state: { activePage } })
  }

  return (
    <aside className="w-72 p-1 pl-0 hidden lg:block">
      <div className="h-[calc(100vh-2rem)] mt-4 rounded-3xl bg-white/10 backdrop-blur-xl border border-white/20 shadow-2xl p-3 flex flex-col">
        <div className="text-emerald-100 mb-8">
          <div className="text-2xl font-bold mb-1">ResumePro AI</div>
          <div className="text-sm opacity-80">RAG Chatbot</div>
        </div>

        <nav className="space-y-1">
          <button
            onClick={() => goChatView('chat')}
            className={`${navButtonBase} ${isActivePath('/chat') ? activeClasses : inactiveClasses}`}
          >
            <span className="text-base">💬</span>
            <span>Chat</span>
          </button>

          <button
            onClick={() => goChatView('resumes')}
            className={`${navButtonBase} ${isActivePath('/upload-resume') ? activeClasses : inactiveClasses}`}
          >
            <span className="text-base">📄</span>
            <span>Upload resumes</span>
          </button>

          <button
            onClick={() => goChatView('jd')}
            className={`${navButtonBase} ${isActivePath('/upload-jd') ? activeClasses : inactiveClasses}`}
          >
            <span className="text-base">📌</span>
            <span>Upload JD</span>
          </button>

          <button
            onClick={() => goChatView('candidates')}
            className={`${navButtonBase} ${inactiveClasses}`}
          >
            <span className="text-base">📋</span>
            <span>Candidates</span>
          </button>

          <button
            onClick={() => goChatView('projects')}
            className={`${navButtonBase} ${inactiveClasses}`}
          >
            <span className="text-base">📂</span>
            <span>Projects</span>
          </button>

          <button
            onClick={() => navigate('/profile')}
            className={`${navButtonBase} ${isActivePath('/profile') ? activeClasses : inactiveClasses}`}
          >
            <span className="text-base">👤</span>
            <span>Profile</span>
          </button>

          {user?.role === 'admin' && (
            <button
              onClick={() => navigate('/admin/users')}
              className={`${navButtonBase} ${isActivePath('/admin/users') ? activeClasses : inactiveClasses}`}
            >
              <span className="text-base">🛡️</span>
              <span>Manage users</span>
            </button>
          )}
        </nav>

        <div className="mt-auto pt-4 border-t border-white/10">
          <div className="text-xs text-emerald-100/70 mb-2">
            Signed in as: {user?.email || user?.username || 'user'}
          </div>
          <button
            onClick={async () => {
              await logout()
              navigate('/login', { replace: true })
            }}
            className="w-full px-3 py-2 rounded-xl bg-white/10 hover:bg-white/15 text-white border border-white/20"
          >
            Logout
          </button>
        </div>
      </div>
    </aside>
  )
}
