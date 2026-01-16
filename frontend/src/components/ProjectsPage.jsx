// src/components/ProjectsPage.jsx
import React, { useState, useMemo, useEffect } from 'react';
import { 
  FolderOpenIcon, 
  UserGroupIcon, 
  ClockIcon,
  BuildingOfficeIcon,
  MagnifyingGlassIcon,
  CodeBracketIcon,
  XMarkIcon,
  CalendarIcon,
  BriefcaseIcon,
  SparklesIcon,
  UserIcon,
  CheckCircleIcon,
  FireIcon
} from '@heroicons/react/24/outline';

const ProjectsPage = ({ onRefresh }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTab, setSelectedTab] = useState('all');
  const [selectedOrganization, setSelectedOrganization] = useState('all');
  const [selectedTech, setSelectedTech] = useState('all');
  const [selectedProject, setSelectedProject] = useState(null);
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [mergeTargetId, setMergeTargetId] = useState('');
  const [mergeBusy, setMergeBusy] = useState(false);
  const [mergeSuggestions, setMergeSuggestions] = useState([]);
  const [suggestBusy, setSuggestBusy] = useState(false);

  // ✅ Fetch projects from API
  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const response = await fetch('http://localhost:5050/api/projects');
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('📊 Raw API response:', data);

        // Combine ongoing and archived projects
        const allProjects = [
          ...(data.projects || []).map(p => ({ ...p, status: 'ongoing' })),
          ...(data.archived_projects || []).map(p => ({ ...p, status: 'archived' }))
        ];

        console.log('✅ All projects with status:', allProjects);
        setProjects(allProjects);
        setError(null);
      } catch (err) {
        console.error('❌ Error fetching projects:', err);
        setError(err.message);
        setProjects([]);
      } finally {
        setLoading(false);
      }
    };

    fetchProjects();
  }, []);

  const fetchMergeSuggestions = async () => {
    setSuggestBusy(true);
    try {
      const res = await fetch('http://localhost:5050/api/projects/merge/suggest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ threshold: 0.82, limit: 12 }),
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data?.error || 'Failed to fetch suggestions');
        return;
      }
      setMergeSuggestions(data?.suggestions || []);
    } catch (e) {
      alert('Failed to fetch suggestions: ' + e.message);
    } finally {
      setSuggestBusy(false);
    }
  };

  const applySuggestedMerge = async (sourceId, targetId) => {
    if (!sourceId || !targetId) return;
    if (String(sourceId) === String(targetId)) return;
    const ok = confirm(`Merge project ${sourceId} into ${targetId}?`);
    if (!ok) return;

    setMergeBusy(true);
    try {
      const res = await fetch('http://localhost:5050/api/projects/merge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_project_id: sourceId,
          target_project_id: targetId,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        const reason = data?.details?.reason || data?.llm?.reason;
        const conf = data?.details?.confidence || data?.llm?.confidence;
        const extra = reason ? `\n\nLLM reason: ${reason}${conf !== undefined ? `\nConfidence: ${conf}` : ''}` : '';
        alert((data?.error || 'Merge failed') + extra);
        return;
      }
      alert('✅ Merge complete');
      await refreshProjects();
      await fetchMergeSuggestions();
    } catch (e) {
      alert('Merge failed: ' + e.message);
    } finally {
      setMergeBusy(false);
    }
  };

  const refreshProjects = async () => {
    try {
      if (onRefresh) {
        await onRefresh();
        return;
      }
      const response = await fetch('http://localhost:5050/api/projects');
      const data = await response.json();
      const allProjects = [
        ...(data.projects || []).map(p => ({ ...p, status: 'ongoing' })),
        ...(data.archived_projects || []).map(p => ({ ...p, status: 'archived' }))
      ];
      setProjects(allProjects);
    } catch (e) {
      console.error('❌ Error refreshing projects:', e);
    }
  };

  const doMerge = async () => {
    if (!selectedProject?.db_id) return;
    if (!mergeTargetId) return;
    if (String(mergeTargetId) === String(selectedProject.db_id)) return;

    const ok = confirm(
      `Merge '${selectedProject.name}' (source) into project ID ${mergeTargetId} (target)?\n\nThis will be validated by the LLM and is reversible via Unmerge.`
    );
    if (!ok) return;

    setMergeBusy(true);
    try {
      const res = await fetch('http://localhost:5050/api/projects/merge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_project_id: selectedProject.db_id,
          target_project_id: parseInt(mergeTargetId, 10),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        const reason = data?.details?.reason || data?.llm?.reason;
        const conf = data?.details?.confidence || data?.llm?.confidence;
        const extra = reason ? `\n\nLLM reason: ${reason}${conf !== undefined ? `\nConfidence: ${conf}` : ''}` : '';
        alert((data?.error || 'Merge failed') + extra);
        return;
      }
      alert('✅ Merge complete');
      setMergeTargetId('');
      await refreshProjects();
      setSelectedProject(null);
    } catch (e) {
      alert('Merge failed: ' + e.message);
    } finally {
      setMergeBusy(false);
    }
  };

  const doUnmerge = async (mergeHistoryId) => {
    if (!mergeHistoryId) return;
    const ok = confirm('Unmerge this project? This will restore contributions/links based on merge history.');
    if (!ok) return;

    setMergeBusy(true);
    try {
      const res = await fetch('http://localhost:5050/api/projects/unmerge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ merge_history_id: mergeHistoryId }),
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data?.error || 'Unmerge failed');
        return;
      }
      alert('✅ Unmerge complete');
      await refreshProjects();
      setSelectedProject(null);
    } catch (e) {
      alert('Unmerge failed: ' + e.message);
    } finally {
      setMergeBusy(false);
    }
  };

  // Get unique organizations
  const organizations = useMemo(() => {
    const orgs = new Set();
    projects.forEach(p => {
      if (p.organization) orgs.add(p.organization);
    });
    return Array.from(orgs).sort();
  }, [projects]);

  // Get unique technologies
  const technologies = useMemo(() => {
    const techs = new Set();
    projects.forEach(p => {
      (p.technologies || []).forEach(t => techs.add(t));
    });
    return Array.from(techs).sort();
  }, [projects]);

  // ✅ FIXED: Filter projects with proper logging
  const filteredProjects = useMemo(() => {
    console.log('🔍 Filtering with tab:', selectedTab);
    let data = [...projects];

    // Tab filter - CRITICAL: Check exact match
    if (selectedTab === 'ongoing') {
      data = data.filter(p => {
        console.log(`Project: ${p.name}, Status: ${p.status}, Match: ${p.status === 'ongoing'}`);
        return p.status === 'ongoing';
      });
    } else if (selectedTab === 'archived') {
      data = data.filter(p => {
        console.log(`Project: ${p.name}, Status: ${p.status}, Match: ${p.status === 'archived'}`);
        return p.status === 'archived';
      });
    }

    console.log(`✅ After tab filter (${selectedTab}): ${data.length} projects`);

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      data = data.filter(p => 
        (p.name || '').toLowerCase().includes(query) ||
        (p.organization || '').toLowerCase().includes(query) ||
        (p.technologies || []).some(t => t.toLowerCase().includes(query)) ||
        (p.members || []).some(m => (m.name || '').toLowerCase().includes(query))
      );
    }

    // Organization filter
    if (selectedOrganization !== 'all') {
      data = data.filter(p => p.organization === selectedOrganization);
    }

    // Technology filter
    if (selectedTech !== 'all') {
      data = data.filter(p => 
        (p.technologies || []).includes(selectedTech)
      );
    }

    console.log(`✅ Final filtered: ${data.length} projects`);
    return data;
  }, [projects, selectedTab, searchQuery, selectedOrganization, selectedTech]);

  const ongoingCount = projects.filter(p => p.status === 'ongoing').length;
  const archivedCount = projects.filter(p => p.status === 'archived').length;
  const totalMembers = projects.reduce((sum, p) => sum + (p.members?.length || 0), 0);

  // Log counts for debugging
  useEffect(() => {
    console.log('📊 Project counts:', {
      total: projects.length,
      ongoing: ongoingCount,
      archived: archivedCount,
      filtered: filteredProjects.length
    });
  }, [projects, ongoingCount, archivedCount, filteredProjects]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-emerald-50 to-yellow-50">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-emerald-200 border-t-emerald-600 rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-600 font-semibold">Loading Projects...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-emerald-50 to-yellow-50">
        <div className="text-center max-w-md bg-white rounded-2xl shadow-xl p-8 border border-red-200">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <XMarkIcon className="w-8 h-8 text-red-600" />
          </div>
          <h3 className="text-xl font-bold text-gray-900 mb-2">Connection Failed</h3>
          <p className="text-gray-600 mb-4">Unable to connect to the backend server.</p>
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
            <p className="text-sm text-red-800 font-mono">{error}</p>
          </div>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 px-6 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-lg transition-colors"
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-emerald-50 to-yellow-50 overflow-hidden">
      {/* HEADER */}
      <div className="flex-shrink-0 bg-gradient-to-r from-emerald-600 via-emerald-500 to-yellow-500 shadow-lg">
        <div className="max-w-7xl mx-auto px-8 py-8">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-white/20 backdrop-blur rounded-xl flex items-center justify-center shadow-lg">
                <BriefcaseIcon className="w-7 h-7 text-white" />
              </div>
              <div>
                <h1 className="text-3xl font-bold text-white">Projects</h1>
              </div>
            </div>
            <div className="bg-white/20 backdrop-blur px-6 py-3 rounded-xl border border-white/30">
              <div className="text-3xl font-bold text-white">{projects.length}</div>
              <p className="text-emerald-100 text-xs">Total Projects</p>
            </div>
          </div>

          {/* STATS */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-white/15 backdrop-blur rounded-lg p-4 border border-white/20">
              <div className="flex items-center gap-3">
                <FireIcon className="w-5 h-5 text-orange-300" />
                <div>
                  <div className="text-2xl font-bold text-white">{ongoingCount}</div>
                  <p className="text-emerald-100 text-xs">Ongoing Projects</p>
                </div>
              </div>
            </div>
            <div className="bg-white/15 backdrop-blur rounded-lg p-4 border border-white/20">
              <div className="flex items-center gap-3">
                <CheckCircleIcon className="w-5 h-5 text-green-300" />
                <div>
                  <div className="text-2xl font-bold text-white">{archivedCount}</div>
                  <p className="text-emerald-100 text-xs">COMPLETED</p>
                </div>
              </div>
            </div>
            <div className="bg-white/15 backdrop-blur rounded-lg p-4 border border-white/20">
              <div className="flex items-center gap-3">
                <UserGroupIcon className="w-5 h-5 text-yellow-300" />
                <div>
                  <div className="text-2xl font-bold text-white">{totalMembers}</div>
                  <p className="text-emerald-100 text-xs">Team Members</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* SCROLLABLE CONTENT */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-7xl mx-auto px-8 py-8 space-y-6">
          {/* SEARCH */}
          <div className="relative">
            <MagnifyingGlassIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search by project name, organization, technology, or team member..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-12 pr-4 py-3 rounded-xl bg-white border border-gray-200 text-gray-900 placeholder-gray-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 transition-all outline-none shadow-sm"
            />
          </div>

          {/* FILTERS */}
          <div className="flex flex-wrap gap-3">
            {/* TABS - ✅ FIXED WITH DEBUG LOGGING */}
            <div className="flex gap-2 bg-white rounded-xl p-1.5 border border-gray-200 shadow-sm">
              {[
                { value: 'all', label: `All (${projects.length})`, icon: '📁' },
                { value: 'ongoing', label: `Ongoing (${ongoingCount})`, icon: '🔥' },
                { value: 'archived', label: `Completed (${archivedCount})`, icon: '📦' }
              ].map(tab => (
                <button
                  key={tab.value}
                  onClick={() => {
                    console.log(`🖱️ Clicked tab: ${tab.value}`);
                    setSelectedTab(tab.value);
                  }}
                  className={`px-4 py-2 rounded-lg font-medium transition-all flex items-center gap-2 text-sm ${
                    selectedTab === tab.value
                      ? 'bg-emerald-600 text-white shadow-md'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <span>{tab.icon}</span>
                  {tab.label}
                </button>
              ))}
            </div>

            {/* ORGANIZATION FILTER */}
            {organizations.length > 0 && (
              <select
                value={selectedOrganization}
                onChange={(e) => setSelectedOrganization(e.target.value)}
                className="px-4 py-2 rounded-lg bg-white border border-gray-200 text-gray-700 font-medium focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 transition-all outline-none text-sm shadow-sm"
              >
                <option value="all">🏢 All Organizations</option>
                {organizations.map(org => (
                  <option key={org} value={org}>{org}</option>
                ))}
              </select>
            )}

            {/* TECHNOLOGY FILTER */}
            {technologies.length > 0 && (
              <select
                value={selectedTech}
                onChange={(e) => setSelectedTech(e.target.value)}
                className="px-4 py-2 rounded-lg bg-white border border-gray-200 text-gray-700 font-medium focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 transition-all outline-none text-sm shadow-sm"
              >
                <option value="all">💻 All Technologies</option>
                {technologies.slice(0, 30).map(tech => (
                  <option key={tech} value={tech}>{tech}</option>
                ))}
              </select>
            )}

            {/* CLEAR FILTERS */}
            {(searchQuery || selectedOrganization !== 'all' || selectedTech !== 'all') && (
              <button
                onClick={() => {
                  setSearchQuery('');
                  setSelectedOrganization('all');
                  setSelectedTech('all');
                }}
                className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 bg-white border border-gray-200 hover:border-red-300 rounded-lg transition-all shadow-sm"
              >
                ✕ Clear Filters
              </button>
            )}
          </div>

          {/* RESULTS INFO */}
          <div className="flex items-center justify-between text-sm text-gray-600 bg-white rounded-lg px-4 py-3 border border-gray-200 shadow-sm">
            <span>Showing <span className="text-emerald-600 font-bold">{filteredProjects.length}</span> of <span className="text-emerald-600 font-bold">{projects.length}</span> projects</span>
            <span>{totalMembers} team members across all projects</span>
          </div>

          {/* SUGGESTED MERGES */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
            <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-gray-100">
              <div className="text-sm font-bold text-gray-900">Suggested merges</div>
              <div className="flex items-center gap-2">
                <button
                  onClick={fetchMergeSuggestions}
                  disabled={suggestBusy || mergeBusy}
                  className="px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {suggestBusy ? '⏳' : '✨ Suggest merges'}
                </button>
                {mergeSuggestions.length > 0 && (
                  <button
                    onClick={() => setMergeSuggestions([])}
                    disabled={suggestBusy || mergeBusy}
                    className="px-3 py-2 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-bold disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>

            <div className="p-4">
              {mergeSuggestions.length === 0 ? (
                <div className="text-xs text-gray-500">No suggestions loaded. Click “Suggest merges”.</div>
              ) : (
                <div className="space-y-3">
                  {mergeSuggestions.map((s, idx) => (
                    <div key={idx} className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-xs font-bold text-gray-900">
                            Source: {s.recommended_source_id} → Target: {s.recommended_target_id}
                          </div>
                          <div className="mt-1 text-[11px] text-gray-700 whitespace-pre-line">
                            {s.reason || '—'}
                          </div>
                          <div className="mt-1 text-[11px] text-gray-500">
                            Confidence: {(Number(s.confidence || 0) * 100).toFixed(0)}% | Score: {Number(s.score || 0).toFixed(2)}
                          </div>
                        </div>
                        <button
                          onClick={() => applySuggestedMerge(s.recommended_source_id, s.recommended_target_id)}
                          disabled={mergeBusy || suggestBusy || !s.recommended_source_id || !s.recommended_target_id}
                          className="flex-shrink-0 px-3 py-2 rounded-lg bg-white border border-emerald-200 text-emerald-700 hover:bg-emerald-50 text-xs font-bold disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          Merge
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* PROJECTS GRID */}
          {filteredProjects.length > 0 ? (
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6 pb-8">
              {filteredProjects.map((project) => (
                <div
                  key={project.db_id}
                  className="group bg-white rounded-xl border border-gray-200 hover:border-emerald-300 shadow-sm hover:shadow-lg transition-all duration-200 overflow-hidden flex flex-col cursor-pointer transform hover:-translate-y-0.5"
                  onClick={() => setSelectedProject(project)}
                >
                  {/* CARD HEADER */}
                  <div className="flex-none p-5 border-b border-gray-100 bg-gradient-to-r from-gray-50 to-emerald-50">
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <h3 className="flex-1 text-base font-bold text-gray-900 group-hover:text-emerald-600 transition-colors line-clamp-2">
                        {project.name}
                      </h3>
                      <span className={`flex-none px-2.5 py-1 rounded-md text-xs font-bold uppercase tracking-wide ${
                        project.status === 'ongoing' 
                          ? 'bg-orange-100 text-orange-700 border border-orange-200' 
                          : 'bg-gray-100 text-gray-700 border border-gray-300'
                      }`}>
                        {project.status === 'ongoing' ? '🔥 Ongoing' : '📦 COMPLETED'}
                      </span>
                    </div>
                    {project.organization && (
                      <div className="flex items-center gap-2 text-xs text-gray-700 bg-emerald-50 px-3 py-1.5 rounded-md border border-emerald-100">
                        <BuildingOfficeIcon className="w-3.5 h-3.5 text-emerald-600" />
                        <span className="truncate font-medium">{project.organization}</span>
                      </div>
                    )}
                  </div>

                  {/* CARD BODY */}
                  <div className="flex-1 p-5 space-y-4">
                    {/* METRICS */}
                    <div className="grid grid-cols-2 gap-3">
                      {project.members && project.members.length > 0 && (
                        <div className="flex items-center gap-2 bg-yellow-50 border border-yellow-100 px-3 py-2 rounded-lg">
                          <UserGroupIcon className="w-4 h-4 text-yellow-600" />
                          <div>
                            <div className="text-lg font-bold text-gray-900">{project.members.length}</div>
                            <div className="text-xs text-gray-600">Team</div>
                          </div>
                        </div>
                      )}
                      {project.duration_months && (
                        <div className="flex items-center gap-2 bg-emerald-50 border border-emerald-100 px-3 py-2 rounded-lg">
                          <ClockIcon className="w-4 h-4 text-emerald-600" />
                          <div>
                            <div className="text-lg font-bold text-gray-900">{project.duration_months}m</div>
                            <div className="text-xs text-gray-600">Duration</div>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* DATE RANGE */}
                    {(project.start_date || project.end_date) && (
                      <div className="flex items-center gap-2 text-xs text-gray-700 bg-gray-50 px-3 py-2 rounded-lg border border-gray-100">
                        <CalendarIcon className="w-4 h-4 text-gray-500" />
                        <span className="font-medium">
                          {project.start_date || 'Unknown'} → {project.end_date || 'Ongoing'}
                        </span>
                      </div>
                    )}

                    {/* TECHNOLOGIES */}
                    {project.technologies && project.technologies.length > 0 && (
                      <div>
                        <div className="flex items-center gap-2 text-xs font-semibold text-gray-700 mb-2">
                          <CodeBracketIcon className="w-4 h-4" />
                          <span>Technologies ({project.technologies.length})</span>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {project.technologies.slice(0, 4).map((tech, idx) => (
                            <span
                              key={idx}
                              className="px-2.5 py-1 bg-emerald-100 text-emerald-700 text-xs font-medium rounded-md border border-emerald-200"
                            >
                              {tech}
                            </span>
                          ))}
                          {project.technologies.length > 4 && (
                            <span className="px-2.5 py-1 bg-gray-100 text-gray-700 text-xs font-medium rounded-md border border-gray-200">
                              +{project.technologies.length - 4}
                            </span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* FOOTER */}
                  <div className="flex-none px-5 py-3 bg-gradient-to-r from-emerald-50 to-yellow-50 border-t border-emerald-100 text-center group-hover:from-emerald-100 group-hover:to-yellow-100 transition-all">
                    <span className="text-xs font-semibold text-emerald-600 group-hover:text-emerald-700 flex items-center justify-center gap-2">
                      View Details
                      <svg className="w-3 h-3 group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-20 bg-white rounded-2xl border-2 border-dashed border-gray-300">
              <FolderOpenIcon className="w-20 h-20 text-gray-400 mx-auto mb-4" />
              <h3 className="text-xl font-bold text-gray-900 mb-2">No Projects Found</h3>
              <p className="text-gray-600">Try adjusting your search or filter criteria</p>
            </div>
          )}
        </div>
      </div>

      {/* MODAL - (keeping it the same as before) */}
      {selectedProject && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl max-h-[90vh] overflow-hidden flex flex-col border border-gray-200 my-8">
            
            {/* MODAL HEADER */}
            <div className="flex-shrink-0 bg-gradient-to-r from-emerald-600 to-yellow-500 px-8 py-6">
              <div className="flex items-start justify-between gap-6 mb-4">
                <div className="flex-1">
                  <div className="inline-block px-3 py-1 bg-white/20 backdrop-blur rounded-full text-xs font-bold uppercase tracking-wide text-white mb-2">
                    {selectedProject.status === 'ongoing' ? '🔥 Ongoing' : '📦 COMPLETED'}
                  </div>
                  <h2 className="text-2xl font-bold text-white mb-1">{selectedProject.name}</h2>
                  {selectedProject.organization && (
                    <div className="flex items-center gap-2 text-emerald-100">
                      <BuildingOfficeIcon className="w-4 h-4" />
                      <span className="font-medium">{selectedProject.organization}</span>
                    </div>
                  )}
                </div>
                <button
                  onClick={() => setSelectedProject(null)}
                  className="flex-none p-2 hover:bg-white/20 rounded-lg transition-all text-white"
                >
                  <XMarkIcon className="w-6 h-6" />
                </button>
              </div>

              {/* MERGE CONTROLS */}
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <div className="flex items-center gap-2 bg-white/15 backdrop-blur rounded-xl border border-white/20 px-3 py-2">
                  <div className="text-xs font-bold text-white/90 whitespace-nowrap">Merge into</div>
                  <select
                    value={mergeTargetId}
                    onChange={(e) => setMergeTargetId(e.target.value)}
                    className="rounded-lg bg-white/90 text-gray-900 text-xs font-semibold px-2 py-1 outline-none"
                    disabled={mergeBusy}
                  >
                    <option value="">Select target…</option>
                    {projects
                      .filter(p => String(p.db_id) !== String(selectedProject.db_id))
                      .slice(0, 80)
                      .map(p => (
                        <option key={p.db_id} value={p.db_id}>
                          {p.name} (ID {p.db_id})
                        </option>
                      ))}
                  </select>
                  <button
                    onClick={doMerge}
                    disabled={!mergeTargetId || mergeBusy}
                    className="ml-1 px-3 py-1.5 rounded-lg bg-white/20 hover:bg-white/30 text-white text-xs font-bold disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {mergeBusy ? '…' : 'Merge'}
                  </button>
                </div>

                {selectedProject?.merged_children?.length > 0 && (
                  <div className="text-xs font-bold text-white/90">
                    Merged: {selectedProject.merged_children.length}
                  </div>
                )}
              </div>

              {/* QUICK STATS */}
              <div className="grid grid-cols-4 gap-3">
                {selectedProject.members && selectedProject.members.length > 0 && (
                  <div className="bg-white/15 backdrop-blur px-3 py-2 rounded-lg border border-white/20">
                    <div className="text-xl font-bold text-white">{selectedProject.members.length}</div>
                    <div className="text-xs text-emerald-100">Members</div>
                  </div>
                )}
                {selectedProject.duration_months && (
                  <div className="bg-white/15 backdrop-blur px-3 py-2 rounded-lg border border-white/20">
                    <div className="text-xl font-bold text-white">{selectedProject.duration_months}m</div>
                    <div className="text-xs text-emerald-100">Duration</div>
                  </div>
                )}
                {selectedProject.technologies && (
                  <div className="bg-white/15 backdrop-blur px-3 py-2 rounded-lg border border-white/20">
                    <div className="text-xl font-bold text-white">{selectedProject.technologies.length}</div>
                    <div className="text-xs text-emerald-100">Technologies</div>
                  </div>
                )}
                {selectedProject.start_date && (
                  <div className="bg-white/15 backdrop-blur px-3 py-2 rounded-lg border border-white/20">
                    <div className="text-sm font-bold text-white truncate">{selectedProject.start_date}</div>
                    <div className="text-xs text-emerald-100">Start Date</div>
                  </div>
                )}
              </div>
            </div>

            {/* MODAL BODY */}
            <div className="flex-1 overflow-y-auto bg-gradient-to-br from-emerald-50 to-yellow-50">
              <div className="p-8 space-y-6">
                {/* MERGED CHILDREN */}
                {selectedProject.merged_children && selectedProject.merged_children.length > 0 && (
                  <div className="bg-white rounded-xl p-6 border border-gray-200 shadow-sm">
                    <h3 className="text-lg font-bold text-gray-900 mb-4">Merged Projects</h3>
                    <div className="space-y-3">
                      {selectedProject.merged_children.map((child) => (
                        <div key={child.db_id} className="flex items-center justify-between gap-3 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
                          <div className="min-w-0">
                            <div className="font-semibold text-gray-900 truncate">{child.name}</div>
                            <div className="text-xs text-gray-600">ID {child.db_id}</div>
                          </div>
                          <button
                            onClick={() => doUnmerge(child.merge_history_id)}
                            disabled={!child.merge_history_id || mergeBusy}
                            className="flex-shrink-0 px-3 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-xs font-bold disabled:opacity-50 disabled:cursor-not-allowed"
                            title={!child.merge_history_id ? 'Missing merge history id' : 'Unmerge'}
                          >
                            Unmerge
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* SUMMARY */}
                {selectedProject.summary && (
                  <div className="bg-white rounded-xl p-6 border border-gray-200 shadow-sm">
                    <h3 className="text-lg font-bold text-gray-900 mb-3 flex items-center gap-2">
                      <SparklesIcon className="w-5 h-5 text-emerald-600" />
                      Project Overview
                    </h3>
                    <p className="text-gray-700 leading-relaxed whitespace-pre-line">{selectedProject.summary}</p>
                  </div>
                )}

                {/* TECHNOLOGIES */}
                {selectedProject.technologies && selectedProject.technologies.length > 0 && (
                  <div className="bg-white rounded-xl p-6 border border-gray-200 shadow-sm">
                    <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                      <CodeBracketIcon className="w-5 h-5 text-emerald-600" />
                      Technology Stack
                    </h3>
                    <div className="flex flex-wrap gap-2">
                      {selectedProject.technologies.map((tech, idx) => (
                        <span
                          key={idx}
                          className="px-3 py-1.5 bg-emerald-100 text-emerald-700 font-medium rounded-lg border border-emerald-200"
                        >
                          {tech}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* TEAM */}
                {selectedProject.members && selectedProject.members.length > 0 && (
                  <div className="bg-white rounded-xl p-6 border border-gray-200 shadow-sm">
                    <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                      <UserGroupIcon className="w-5 h-5 text-yellow-600" />
                      Team Contributions ({selectedProject.members.length})
                    </h3>
                    <div className="space-y-4">
                      {selectedProject.members.map((member, idx) => (
                        <div key={idx} className="bg-gradient-to-r from-emerald-50 to-yellow-50 rounded-xl p-5 border border-gray-200">
                          <div className="flex items-start gap-4 mb-3">
                            <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-emerald-500 to-yellow-500 flex items-center justify-center text-white text-lg font-bold flex-none shadow-md">
                              {(member.name || 'U')[0].toUpperCase()}
                            </div>
                            <div className="flex-1">
                              <h4 className="text-base font-bold text-gray-900">{member.name}</h4>
                              {member.role && (
                                <span className="inline-block px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs font-semibold rounded border border-emerald-200 mt-1">
                                  {member.role}
                                </span>
                              )}
                              {member.years && (
                                <p className="text-gray-600 text-sm mt-1">{member.years} years experience</p>
                              )}
                            </div>
                          </div>

                          {member.contribution && (
                            <div className="mb-3 p-3 bg-yellow-50 border-l-4 border-yellow-400 rounded">
                              <p className="text-gray-800 text-sm"><span className="font-semibold text-yellow-700">Contribution: </span>{member.contribution}</p>
                            </div>
                          )}

                          {member.technical_tools && member.technical_tools.length > 0 && (
                            <div>
                              <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">Tools & Technologies</p>
                              <div className="flex flex-wrap gap-2">
                                {member.technical_tools.map((tool, tidx) => (
                                  <span
                                    key={tidx}
                                    className="px-2.5 py-1 bg-white text-gray-700 text-xs font-medium rounded border border-gray-300"
                                  >
                                    {tool}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* MODAL FOOTER */}
            <div className="flex-shrink-0 bg-white border-t border-gray-200 px-8 py-4 flex justify-end">
              <button
                onClick={() => setSelectedProject(null)}
                className="px-6 py-2.5 bg-gradient-to-r from-emerald-600 to-yellow-500 hover:from-emerald-700 hover:to-yellow-600 text-white font-semibold rounded-lg shadow-md transition-all"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProjectsPage;
