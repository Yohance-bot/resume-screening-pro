import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { RequireAuth } from './auth/RequireAuth'
import { useAuth } from './auth/AuthContext'
import { RequireAdmin } from './auth/RequireAdmin'
import Login from './pages/Login'
import Home from './pages/Home'
import Chat from './pages/Chat'
import Profile from './pages/Profile'
import ChangePassword from './pages/ChangePassword'
import AdminUsers from './pages/AdminUsers'
import JDUpload from './pages/JDUpload'
import ResumeUpload from './pages/ResumeUpload'
import Ranking from './pages/Ranking'
import FinalReview from './pages/FinalReview'

function RootRedirect() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-600">Loading...</div>
      </div>
    )
  }

  if (!user) return <Navigate to="/login" replace />
  if (user.force_password_change) return <Navigate to="/change-password" replace />
  return <Navigate to="/chat" replace />
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<RootRedirect />} />
          <Route path="/profile" element={
            <RequireAuth>
              <Profile />
            </RequireAuth>
          } />
          <Route path="/change-password" element={
            <RequireAuth>
              <ChangePassword />
            </RequireAuth>
          } />
          <Route path="/admin/users" element={
            <RequireAdmin>
              <AdminUsers />
            </RequireAdmin>
          } />
          <Route path="/home" element={
            <RequireAuth>
              <Home />
            </RequireAuth>
          } />
          <Route path="/chat" element={
            <RequireAuth>
              <Chat />
            </RequireAuth>
          } />
          <Route path="/upload-jd" element={
            <RequireAuth>
              <JDUpload />
            </RequireAuth>
          } />
          <Route path="/upload-resume" element={
            <RequireAuth>
              <ResumeUpload />
            </RequireAuth>
          } />
          <Route path="/ranking" element={
            <RequireAuth>
              <Ranking />
            </RequireAuth>
          } />
          <Route path="/review" element={
            <RequireAuth>
              <FinalReview />
            </RequireAuth>
          } />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  )
}

export default App
