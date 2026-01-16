import React from 'react'

export default
function SkillsCategorizedDisplay({ data }) {
  const categories = data.skills_by_category || {}
  const candidate = data.candidate
  const totalSkills = data.total_skills || 0

  return (
    <div>
      <div className="mb-6">
        <h3 className="text-2xl font-bold text-gray-900 mb-1">
          {candidate?.name}'s Technical Skills
        </h3>
        <p className="text-sm text-gray-500">
          {totalSkills} total skills • {candidate?.experience} years experience
        </p>
      </div>

      <div className="space-y-5">
        {Object.entries(categories).map(([category, skills]) =>
          skills && skills.length > 0 ? (
            <div key={category} className="group">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-lg">
                  {category.includes('Programming') ? '💻' :
                   category.includes('Framework') ? '⚛️' :
                   category.includes('Database') ? '🗄️' :
                   category.includes('Cloud') ? '☁️' : '🔧'}
                </span>
                <h4 className="text-base font-bold text-gray-800">{category}</h4>
                <span className="ml-auto text-xs font-medium text-gray-400 bg-gray-100 px-2 py-1 rounded-full">
                  {skills.length}
                </span>
              </div>
              
              <div className="flex flex-wrap gap-2 pl-8">
                {skills.map((skill, idx) => (
                  <span
                    key={idx}
                    className="px-3 py-1.5 bg-gradient-to-br from-emerald-50 to-emerald-100 
                             text-emerald-800 rounded-lg text-sm font-medium
                             border border-emerald-200/50 shadow-sm
                             hover:shadow-md hover:scale-105 transition-all duration-200
                             cursor-default"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          ) : null
        )}
      </div>

      {candidate && (
        <div className="mt-6 pt-4 border-t border-gray-200">
          <div className="flex items-center gap-4 text-xs text-gray-500">
            <span>📧 {candidate.email || 'N/A'}</span>
            <span>•</span>
            <span>🎯 {candidate.role || 'N/A'}</span>
            <span>•</span>
            <span>📦 {candidate.bucket || 'N/A'}</span>
          </div>
        </div>
      )}
    </div>
  )
}