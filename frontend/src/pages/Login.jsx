import React, { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import hmBubble from '../assets/hm-bubble.png'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  
  const navigate = useNavigate()
  const location = useLocation()
  const { login } = useAuth()

  const from = location.state?.from?.pathname || '/'

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err.message || 'Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative min-h-screen bg-gradient-to-br from-emerald-900 via-emerald-800 to-amber-500 overflow-hidden">
      <div className="pointer-events-none absolute inset-0 flex justify-center items-center">
        <img
          src={hmBubble}
          alt="HM bubble"
          className="w-80 md:w-96 lg:w-[480px] opacity-75 drop-shadow-[0_0_60px_rgba(190,255,190,0.6)] mix-blend-screen animate-[pulse_8s_ease-in-out_infinite] transition-all duration-1000"
        />
      </div>

      <div className="relative z-10 min-h-screen flex items-center justify-center px-4">
        <div className="w-full max-w-md rounded-3xl bg-white/10 backdrop-blur-xl border border-white/20 shadow-2xl p-6">
          <div className="text-emerald-100 mb-8">
            <div className="text-2xl font-bold mb-1">ResumePro AI</div>
            <div className="text-sm opacity-80">RAG Chatbot</div>
          </div>

          <h2 className="text-xl font-semibold text-white mb-6">Sign in</h2>

          <form className="space-y-4" onSubmit={handleSubmit}>
            <div>
              <label htmlFor="email" className="block text-sm text-emerald-100/80 mb-1">
                Email or username
              </label>
              <input
                id="email"
                name="email"
                type="text"
                autoComplete="username"
                required
                className="w-full px-3 py-2 rounded-xl bg-white/10 border border-white/20 text-white placeholder-emerald-100/50 focus:outline-none focus:ring-2 focus:ring-emerald-400/60"
                placeholder="happyadmin"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm text-emerald-100/80 mb-1">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                className="w-full px-3 py-2 rounded-xl bg-white/10 border border-white/20 text-white placeholder-emerald-100/50 focus:outline-none focus:ring-2 focus:ring-emerald-400/60"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            {error && (
              <div className="text-red-200 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white font-medium shadow-lg disabled:opacity-50"
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
