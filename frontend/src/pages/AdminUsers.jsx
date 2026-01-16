import React, { useEffect, useState } from 'react'
import AppShell from '../components/AppShell'
import { createUser, deleteUser, listUsers, resetUserPassword } from '../services/admin'

export default function AdminUsers() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [users, setUsers] = useState([])

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('user')
  const [password, setPassword] = useState('')
  const [creating, setCreating] = useState(false)
  const [createdTempPassword, setCreatedTempPassword] = useState('')

  const [resettingId, setResettingId] = useState(null)
  const [resetTempPassword, setResetTempPassword] = useState('')

  const [deletingId, setDeletingId] = useState(null)

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await listUsers()
      setUsers(data.users || [])
    } catch (e) {
      setError(e.message || 'Failed to load users')
    } finally {
      setLoading(false)
    }
  }

  const onDelete = async (u) => {
    const ok = window.confirm(`Delete user ${u.email || u.name || u.id}? This cannot be undone.`)
    if (!ok) return

    setDeletingId(u.id)
    setError('')
    try {
      await deleteUser(u.id)
      await load()
    } catch (e) {
      setError(e.message || 'Failed to delete user')
    } finally {
      setDeletingId(null)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const onCreate = async (e) => {
    e.preventDefault()
    setCreating(true)
    setError('')
    setCreatedTempPassword('')

    try {
      const res = await createUser({ name, email, password: password || undefined, role })
      setCreatedTempPassword(res.temporary_password || '')
      setName('')
      setEmail('')
      setRole('user')
      setPassword('')
      await load()
    } catch (e) {
      setError(e.message || 'Failed to create user')
    } finally {
      setCreating(false)
    }
  }

  const onReset = async (userId) => {
    setResettingId(userId)
    setError('')
    try {
      const res = await resetUserPassword(userId, resetTempPassword || undefined)
      setResetTempPassword('')
      await load()
      alert(`Temporary password (shown once): ${res.temporary_password}`)
    } catch (e) {
      setError(e.message || 'Failed to reset password')
    } finally {
      setResettingId(null)
    }
  }

  return (
    <AppShell title="Admin · User Management">
      <div className="max-w-5xl space-y-6">
        <div className="rounded-3xl bg-white/10 backdrop-blur-xl border border-white/20 shadow-2xl p-6">

            {error && <div className="mt-4 text-red-200">{error}</div>}

            <form className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4" onSubmit={onCreate}>
              <div>
                <label className="block text-sm text-emerald-100/80 mb-1">Name</label>
                <input
                  className="w-full px-3 py-2 rounded-xl bg-white/10 border border-white/20 text-white placeholder-emerald-100/50 focus:outline-none focus:ring-2 focus:ring-emerald-400/60"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Jane Doe"
                />
              </div>

              <div>
                <label className="block text-sm text-emerald-100/80 mb-1">Email (@happiestminds.com)</label>
                <input
                  className="w-full px-3 py-2 rounded-xl bg-white/10 border border-white/20 text-white placeholder-emerald-100/50 focus:outline-none focus:ring-2 focus:ring-emerald-400/60"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="user@happiestminds.com"
                  required
                />
              </div>

              <div>
                <label className="block text-sm text-emerald-100/80 mb-1">Role</label>
                <select
                  className="w-full px-3 py-2 rounded-xl bg-white/10 border border-white/20 text-white focus:outline-none focus:ring-2 focus:ring-emerald-400/60"
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                >
                  <option value="user">user</option>
                  <option value="admin">admin</option>
                </select>
              </div>

              <div>
                <label className="block text-sm text-emerald-100/80 mb-1">Initial Password (optional)</label>
                <input
                  className="w-full px-3 py-2 rounded-xl bg-white/10 border border-white/20 text-white placeholder-emerald-100/50 focus:outline-none focus:ring-2 focus:ring-emerald-400/60"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Leave blank to auto-generate"
                />
                <div className="text-xs text-emerald-100/70 mt-1">
                  If blank, the system generates a policy-compliant temporary password.
                </div>
              </div>

              <div className="md:col-span-2">
                <button
                  type="submit"
                  disabled={creating}
                  className="w-full py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white font-medium shadow-lg disabled:opacity-50"
                >
                  {creating ? 'Creating...' : 'Create user'}
                </button>

                {createdTempPassword && (
                  <div className="mt-3 rounded-2xl bg-white/10 border border-white/20 p-3 text-white">
                    <div className="text-sm font-medium">Temporary password (shown once)</div>
                    <div className="mt-1 font-mono break-all">{createdTempPassword}</div>
                  </div>
                )}
              </div>
            </form>
        </div>

        <div className="rounded-3xl bg-white/10 backdrop-blur-xl border border-white/20 shadow-2xl p-6">
          <div className="text-white font-semibold mb-4">Users</div>

            {loading ? (
              <div className="text-emerald-100/80">Loading...</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm text-emerald-50/90">
                  <thead>
                    <tr className="text-emerald-100/80">
                      <th className="text-left py-2 pr-4">Name</th>
                      <th className="text-left py-2 pr-4">Email</th>
                      <th className="text-left py-2 pr-4">Role</th>
                      <th className="text-left py-2 pr-4">Created</th>
                      <th className="text-left py-2 pr-4">Force change</th>
                      <th className="text-left py-2 pr-4">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.id} className="border-t border-white/10">
                        <td className="py-2 pr-4">{u.name || '-'}</td>
                        <td className="py-2 pr-4">{u.email || '-'}</td>
                        <td className="py-2 pr-4">{u.role}</td>
                        <td className="py-2 pr-4">{u.created_at ? new Date(u.created_at).toLocaleString() : '-'}</td>
                        <td className="py-2 pr-4">{u.force_password_change ? 'yes' : 'no'}</td>
                        <td className="py-2 pr-4">
                          <div className="flex flex-col gap-2">
                            <input
                              className="w-56 px-2 py-1 rounded-lg bg-white/10 border border-white/20 text-white placeholder-emerald-100/50 focus:outline-none"
                              placeholder="Temp password (optional)"
                              value={resettingId === u.id ? resetTempPassword : ''}
                              onChange={(e) => setResetTempPassword(e.target.value)}
                              disabled={resettingId !== null && resettingId !== u.id}
                            />
                            <button
                              type="button"
                              onClick={() => onReset(u.id)}
                              disabled={resettingId !== null && resettingId !== u.id}
                              className="px-3 py-1.5 rounded-xl bg-white/15 hover:bg-white/20 text-white border border-white/20 disabled:opacity-50"
                            >
                              {resettingId === u.id ? 'Resetting...' : 'Reset password'}
                            </button>

                            <button
                              type="button"
                              onClick={() => onDelete(u)}
                              disabled={deletingId !== null}
                              className="px-3 py-1.5 rounded-xl bg-red-500/70 hover:bg-red-500 text-white border border-white/20 disabled:opacity-50"
                            >
                              {deletingId === u.id ? 'Deleting...' : 'Delete user'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
        </div>
      </div>
    </AppShell>
  )
}
