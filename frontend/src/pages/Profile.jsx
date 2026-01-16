import React, { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import AppShell from "../components/AppShell"
import { useAuth } from "../auth/AuthContext"
import { updateProfile } from "../services/auth"

export default function Profile() {
  const navigate = useNavigate()
  const { user, loading, refresh } = useAuth()

  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")
  const [success, setSuccess] = useState("")

  useEffect(() => {
    setName(user?.name || "")
    setEmail(user?.email || user?.username || "")
  }, [user])

  const onSave = async (e) => {
    e.preventDefault()
    setError("")
    setSuccess("")
    setSaving(true)
    try {
      await updateProfile({ name, email })
      await refresh()
      setSuccess("Profile updated")
    } catch (e) {
      setError(e.message || "Failed to update profile")
    } finally {
      setSaving(false)
    }
  }

  return (
    <AppShell title="Profile">
      {loading ? (
        <div className="text-emerald-100/80">Loading...</div>
      ) : !user ? (
        <div className="text-red-200">Not authenticated</div>
      ) : (
        <div className="space-y-4">
          <form onSubmit={onSave} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-2xl bg-white/10 border border-white/15 p-4">
              <div className="text-xs text-emerald-100/70">Name</div>
              <input
                className="mt-2 w-full px-3 py-2 rounded-xl bg-white/10 border border-white/20 text-white placeholder-emerald-100/50 focus:outline-none focus:ring-2 focus:ring-emerald-400/60"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
              />
            </div>

            <div className="rounded-2xl bg-white/10 border border-white/15 p-4">
              <div className="text-xs text-emerald-100/70">Email</div>
              <input
                className="mt-2 w-full px-3 py-2 rounded-xl bg-white/10 border border-white/20 text-white placeholder-emerald-100/50 focus:outline-none focus:ring-2 focus:ring-emerald-400/60"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@happiestminds.com"
              />
              <div className="text-xs text-emerald-100/70 mt-1">Must be @happiestminds.com</div>
            </div>

            <div className="rounded-2xl bg-white/10 border border-white/15 p-4">
              <div className="text-xs text-emerald-100/70">Role</div>
              <div className="text-white font-medium">{user?.role || "-"}</div>
            </div>

            <div className="rounded-2xl bg-white/10 border border-white/15 p-4">
              <div className="text-xs text-emerald-100/70">Created</div>
              <div className="text-white font-medium">
                {user?.created_at ? new Date(user.created_at).toLocaleString() : "-"}
              </div>
            </div>

            <div className="rounded-2xl bg-white/10 border border-white/15 p-4">
              <div className="text-xs text-emerald-100/70">Last login</div>
              <div className="text-white font-medium">
                {user?.last_login ? new Date(user.last_login).toLocaleString() : "-"}
              </div>
            </div>

            <div className="rounded-2xl bg-white/10 border border-white/15 p-4">
              <div className="text-xs text-emerald-100/70">Force password change</div>
              <div className="text-white font-medium">{user?.force_password_change ? "yes" : "no"}</div>
            </div>
            <div className="md:col-span-2">
              {error && <div className="text-red-200 mb-2">{error}</div>}
              {success && <div className="text-emerald-100 mb-2">{success}</div>}

              <button
                type="submit"
                disabled={saving}
                className="w-full py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white font-medium shadow-lg disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save profile"}
              </button>
            </div>
          </form>

          <div className="flex flex-col sm:flex-row gap-3 pt-2">
            <button
              type="button"
              onClick={() => navigate("/change-password")}
              className="flex-1 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white font-medium shadow-lg"
            >
              Change Password
            </button>

            {user?.role === "admin" && (
              <button
                type="button"
                onClick={() => navigate("/admin/users")}
                className="flex-1 py-2.5 rounded-xl bg-white/15 hover:bg-white/20 text-white font-medium border border-white/20"
              >
                Manage Users
              </button>
            )}
          </div>
        </div>
      )}
    </AppShell>
  )
}
