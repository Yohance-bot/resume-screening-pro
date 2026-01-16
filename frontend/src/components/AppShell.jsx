import React from 'react'
import hmBubble from '../assets/hm-bubble.png'
import UnifiedSidebar from './UnifiedSidebar'

export default function AppShell({ title, children }) {
  return (
    <div className="relative min-h-screen bg-gradient-to-br from-emerald-900 via-emerald-800 to-amber-500 overflow-hidden">
      <div className="pointer-events-none absolute inset-0 flex justify-center items-center">
        <img
          src={hmBubble}
          alt="HM bubble"
          className="w-80 md:w-96 lg:w-[480px] opacity-60 drop-shadow-[0_0_60px_rgba(190,255,190,0.6)] mix-blend-screen animate-[pulse_8s_ease-in-out_infinite] transition-all duration-1000"
        />
      </div>

      <div className="relative flex min-h-screen w-full gap-3 pl-4">
        <UnifiedSidebar />

        <div className="relative flex-1 flex flex-col min-w-0 pr-4 py-4">
          <div className="rounded-3xl bg-white/10 backdrop-blur-xl border border-white/20 shadow-2xl p-6">
            {children}
          </div>
        </div>
      </div>
    </div>
  )
}
