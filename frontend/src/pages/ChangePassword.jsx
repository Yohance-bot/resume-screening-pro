import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '../components/AppShell'
import { changePassword } from '../services/auth'
import { useAuth } from '../auth/AuthContext'

export default function ChangePassword() {
  const navigate = useNavigate()
  const { refresh } = useAuth()

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmNewPassword, setConfirmNewPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')

    if (newPassword !== confirmNewPassword) {
      setError('New password and confirmation do not match')
      return
    }

    setLoading(true)
    try {
      await changePassword(currentPassword, newPassword)
      await refresh()
      setSuccess('Password changed successfully')
      navigate('/chat', { replace: true })
    } catch (err) {
      setError(err.message || 'Failed to change password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AppShell title="Change Password">
      <div className="max-w-md">
        <form className="space-y-4" onSubmit={handleSubmit}>
            <div>
              <label className="block text-sm text-emerald-100/80 mb-1" htmlFor="current_password">
                Current password
              </label>
              <input
                id="current_password"
                type="password"
                autoComplete="current-password"
                required
                className="w-full px-3 py-2 rounded-xl bg-white/10 border border-white/20 text-white placeholder-emerald-100/50 focus:outline-none focus:ring-2 focus:ring-emerald-400/60"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
              />
            </div>

            <div>
              <label className="block text-sm text-emerald-100/80 mb-1" htmlFor="new_password">
                New password
              </label>
              <input
                id="new_password"
                type="password"
                autoComplete="new-password"
                required
                className="w-full px-3 py-2 rounded-xl bg-white/10 border border-white/20 text-white placeholder-emerald-100/50 focus:outline-none focus:ring-2 focus:ring-emerald-400/60"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
              <div className="text-xs text-emerald-100/70 mt-1">
                Min 8 chars, include upper/lower/number/special.
              </div>
            </div>

            <div>
              <label className="block text-sm text-emerald-100/80 mb-1" htmlFor="confirm_new_password">
                Confirm new password
              </label>
              <input
                id="confirm_new_password"
                type="password"
                autoComplete="new-password"
                required
                className="w-full px-3 py-2 rounded-xl bg-white/10 border border-white/20 text-white placeholder-emerald-100/50 focus:outline-none focus:ring-2 focus:ring-emerald-400/60"
                value={confirmNewPassword}
                onChange={(e) => setConfirmNewPassword(e.target.value)}
              />
            </div>

            {error && <div className="text-red-200 text-sm">{error}</div>}
            {success && <div className="text-emerald-100 text-sm">{success}</div>}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white font-medium shadow-lg disabled:opacity-50"
            >
              {loading ? 'Saving...' : 'Update password'}
            </button>

            <button
              type="button"
              onClick={() => navigate('/profile')}
              className="w-full py-2.5 rounded-xl bg-white/10 hover:bg-white/15 text-white font-medium border border-white/20"
            >
              Back to Profile
            </button>
          </form>
      </div>
    </AppShell>
  )
}
