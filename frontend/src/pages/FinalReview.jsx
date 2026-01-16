import { useState, useEffect } from 'react';

function FinalReview({ sessionId }) {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!sessionId) {
      setLoading(false);
      return;
    }

    fetch(`http://localhost:5050/api/final-review/${sessionId}`)
      .then(res => {
        if (!res.ok) throw new Error('Failed to fetch');
        return res.json();
      })
      .then(data => {
        setCandidates(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [sessionId]);

  if (loading) {
    return (
      <div className="flex justify-center items-center p-12">
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
          <div className="text-lg font-semibold text-emerald-700">Loading final review...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-emerald-50 border-l-4 border-emerald-500 rounded-xl shadow-lg">
        <div className="flex items-center gap-3">
          <svg className="w-6 h-6 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-emerald-800 font-semibold">Error: {error}</p>
        </div>
      </div>
    );
  }

  if (candidates.length === 0) {
    return (
      <div className="p-8 bg-yellow-50 border-l-4 border-yellow-400 rounded-xl shadow-lg">
        <div className="flex items-center gap-3">
          <svg className="w-8 h-8 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <div>
            <p className="text-yellow-800 font-semibold text-lg">No candidates found</p>
            <p className="text-yellow-600 text-sm">Run all 4 screenings first to generate the final review</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header Section - Soft Green */}
      <div className="bg-gradient-to-r from-emerald-100 via-emerald-50 to-teal-100 rounded-2xl shadow-lg p-8 border border-emerald-200">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="bg-white p-3 rounded-xl shadow-sm">
                <svg className="w-8 h-8 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
                </svg>
              </div>
              <h2 className="text-4xl font-bold text-emerald-900">
                Final Candidate Review
              </h2>
            </div>
            <p className="text-emerald-700 text-lg ml-14">
              {candidates.length} candidates ranked by AI-powered analysis
            </p>
          </div>
          <div className="bg-white/80 backdrop-blur-sm rounded-2xl px-8 py-6 text-center border border-emerald-200 shadow-sm">
            <div className="text-5xl font-bold text-emerald-700">{candidates.length}</div>
            <div className="text-emerald-600 text-sm mt-1 font-medium">Total Candidates</div>
          </div>
        </div>
      </div>

      {/* Stats Cards - Soft Green Theme */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-gradient-to-br from-emerald-50 to-teal-50 rounded-xl p-6 border border-emerald-200 shadow-lg hover:shadow-xl transition-shadow">
          <div className="flex items-center gap-4">
            <div className="bg-white p-3 rounded-xl shadow-sm">
              <svg className="w-6 h-6 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div>
              <div className="text-3xl font-bold text-emerald-900">
                {candidates.filter((_, i) => i < 3).length}
              </div>
              <div className="text-sm text-emerald-700 font-medium">Top 3 Finalists</div>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-emerald-50 to-teal-50 rounded-xl p-6 border border-emerald-200 shadow-lg hover:shadow-xl transition-shadow">
          <div className="flex items-center gap-4">
            <div className="bg-white p-3 rounded-xl shadow-sm">
              <svg className="w-6 h-6 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>
            <div>
              <div className="text-3xl font-bold text-emerald-900">
                {Math.round(candidates.reduce((sum, c) => sum + c.fitmentMatchScore, 0) / candidates.length)}%
              </div>
              <div className="text-sm text-emerald-700 font-medium">Avg Score</div>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-emerald-50 to-teal-50 rounded-xl p-6 border border-emerald-200 shadow-lg hover:shadow-xl transition-shadow">
          <div className="flex items-center gap-4">
            <div className="bg-white p-3 rounded-xl shadow-sm">
              <svg className="w-6 h-6 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7" />
              </svg>
            </div>
            <div>
              <div className="text-3xl font-bold text-emerald-900">
                {candidates[0]?.fitmentMatchScore || 0}%
              </div>
              <div className="text-sm text-emerald-700 font-medium">Top Score</div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Table - Soft Green */}
      <div className="bg-gradient-to-br from-emerald-50/50 to-teal-50/50 rounded-2xl shadow-lg overflow-hidden border border-emerald-200">
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr className="bg-gradient-to-r from-emerald-100 to-teal-100 border-b border-emerald-200">
                <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider text-emerald-900">Rank</th>
                <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider text-emerald-900">Candidate</th>
                <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider text-emerald-900">Role</th>
                <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider text-emerald-900">Experience</th>
                <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider text-emerald-900">Key Skills</th>
                <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider text-emerald-900">Certifications</th>
                <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-wider text-emerald-900">Fitment Score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-emerald-200">
              {candidates.map((candidate, index) => (
                <tr 
                  key={index} 
                  className={`transition-all duration-200 ${
                    index < 3 
                      ? 'bg-white hover:bg-emerald-50/50' 
                      : 'bg-white/60 hover:bg-white'
                  }`}
                >
                  {/* Rank Column */}
                  <td className="px-6 py-5">
                    <div className="flex items-center gap-3">
                      {index === 0 && (
                        <div className="flex items-center justify-center w-12 h-12 bg-gradient-to-br from-yellow-400 to-yellow-500 text-white rounded-full font-bold text-xl shadow-lg">
                          🥇
                        </div>
                      )}
                      {index === 1 && (
                        <div className="flex items-center justify-center w-12 h-12 bg-gradient-to-br from-gray-300 to-gray-400 text-white rounded-full font-bold text-xl shadow-lg">
                          🥈
                        </div>
                      )}
                      {index === 2 && (
                        <div className="flex items-center justify-center w-12 h-12 bg-gradient-to-br from-orange-400 to-orange-500 text-white rounded-full font-bold text-xl shadow-lg">
                          🥉
                        </div>
                      )}
                      {index > 2 && (
                        <div className="flex items-center justify-center w-12 h-12 bg-white text-emerald-700 rounded-full font-bold text-lg border-2 border-emerald-200 shadow-sm">
                          {candidate.rankPosition}
                        </div>
                      )}
                    </div>
                  </td>

                  {/* Candidate Name */}
                  <td className="px-6 py-5">
                    <div className="flex items-center gap-3">
                      <div className="flex-shrink-0 w-10 h-10 bg-gradient-to-br from-emerald-400 to-teal-500 rounded-full flex items-center justify-center text-white font-bold shadow-md">
                        {candidate.candidateName.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <div className="font-semibold text-gray-900 text-base">{candidate.candidateName}</div>
                        <div className="text-xs text-emerald-600">{candidate.jdRoleName}</div>
                      </div>
                    </div>
                  </td>

                  {/* Role */}
                  <td className="px-6 py-5">
                    <div className="bg-emerald-100 text-emerald-700 px-3 py-1 rounded-full text-sm font-medium inline-block border border-emerald-200">
                      {candidate.jdRoleName}
                    </div>
                  </td>

                  {/* Experience */}
                  <td className="px-6 py-5">
                    <div className="text-gray-700 font-medium">{candidate.candidateExperience}</div>
                  </td>

                  {/* Skills */}
                  <td className="px-6 py-5">
                    <div className="flex flex-wrap gap-1 max-w-xs">
                      {candidate.candidateSkills.split(',').slice(0, 3).map((skill, i) => (
                        <span key={i} className="px-2 py-1 bg-teal-50 text-teal-700 rounded-md text-xs font-medium border border-teal-200">
                          {skill.trim()}
                        </span>
                      ))}
                      {candidate.candidateSkills.split(',').length > 3 && (
                        <span className="px-2 py-1 bg-emerald-100 text-emerald-700 rounded-md text-xs font-medium border border-emerald-200">
                          +{candidate.candidateSkills.split(',').length - 3}
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Certifications */}
                  <td className="px-6 py-5">
                    {candidate.certifications === 'N/A' ? (
                      <span className="text-gray-400 text-sm">—</span>
                    ) : (
                      <span className="px-3 py-1 bg-emerald-100 text-emerald-700 rounded-full text-xs font-medium border border-emerald-200">
                        {candidate.certifications}
                      </span>
                    )}
                  </td>

                  {/* Fitment Score - All Emerald/Yellow/Teal */}
                  <td className="px-6 py-5 text-center">
                    <div className="flex flex-col items-center gap-2">
                      <div className={`text-3xl font-extrabold ${
                        candidate.fitmentMatchScore >= 80 ? 'text-emerald-600' :
                        candidate.fitmentMatchScore >= 60 ? 'text-yellow-600' :
                        'text-teal-600'
                      }`}>
                        {candidate.fitmentMatchScore}%
                      </div>
                      <div className="w-24 bg-emerald-100 rounded-full h-2 overflow-hidden border border-emerald-200">
                        <div 
                          className={`h-full rounded-full ${
                            candidate.fitmentMatchScore >= 80 ? 'bg-emerald-500' :
                            candidate.fitmentMatchScore >= 60 ? 'bg-yellow-500' :
                            'bg-teal-500'
                          }`}
                          style={{ width: `${candidate.fitmentMatchScore}%` }}
                        ></div>
                      </div>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Footer Note - Soft Green */}
        <div className="flex items-start gap-3">
          <div className="bg-white p-2 rounded-lg shadow-sm">
            <svg className="w-6 h-6 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
        </div>
      </div>
  );
}

export default FinalReview;
