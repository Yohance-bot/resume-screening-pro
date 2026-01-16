import React, { useMemo, useState } from "react";

const TeamManagementPanel = ({
  showTeamPanel,
  setShowTeamPanel,
  projects = [],
  candidates = [],
  fetchProjects,
}) => {
  // Per-project dropdown selection
  const [selectedCandidateByProject, setSelectedCandidateByProject] = useState({});
  // Per-project loading state (prevents other cards from “losing” their button)
  const [loadingByProject, setLoadingByProject] = useState({});

  const anyLoading = useMemo(
    () => Object.values(loadingByProject).some(Boolean),
    [loadingByProject]
  );

  const totalAssignments = useMemo(
    () => projects.reduce((sum, p) => sum + (p?.members?.length || 0), 0),
    [projects]
  );

  const setProjectLoading = (projectId, value) => {
    setLoadingByProject((prev) => ({ ...prev, [projectId]: value }));
  };

  const manageTeam = async ({ action, project, candidateId }) => {
    if (!candidateId) return;

    setProjectLoading(project.id, true);
    try {
      const res = await fetch("http://localhost:5050/api/projects/manage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          project_id: project.name, // keep as-is for your backend today
          candidate_id: parseInt(candidateId, 10),
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        alert("Failed to update team: " + (data?.error || "Unknown error"));
        return;
      }

      // Clear only this project's select
      setSelectedCandidateByProject((prev) => ({ ...prev, [project.id]: "" }));

      if (fetchProjects) {
        await fetchProjects();
      }

      alert(
        `${action === "add" ? "✅ Added" : "✅ Removed"} candidate ${
          action === "add" ? "to" : "from"
        } project!`
      );
    } catch (e) {
      console.error("❌ Error:", e);
      alert("Failed to update team: " + e.message);
    } finally {
      setProjectLoading(project.id, false);
    }
  };

  if (!showTeamPanel) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="flex w-full max-w-7xl max-h-[90vh] flex-col overflow-hidden rounded-3xl border border-white/30 bg-white/95 shadow-2xl backdrop-blur-2xl">
        {/* Header */}
        <div className="flex flex-shrink-0 items-center justify-between gap-4 border-b border-gray-200 bg-gradient-to-r from-emerald-50 to-blue-50 p-6">
          <div className="min-w-0">
            <h2 className="truncate text-2xl font-bold text-gray-900">Project Teams</h2>
          </div>

          <button
            onClick={() => setShowTeamPanel(false)}
            className="rounded-xl p-2 text-xl font-bold text-gray-600 transition hover:bg-gray-200 hover:text-gray-900"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="space-y-6">
            {/* Stats */}
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-xl border border-emerald-100 bg-emerald-50 p-4 text-center">
                <div className="text-2xl font-bold text-emerald-600">{projects.length}</div>
                <div className="mt-1 text-xs text-gray-600">Total Projects</div>
              </div>

              <div className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-center">
                <div className="text-2xl font-bold text-blue-600">{totalAssignments}</div>
                <div className="mt-1 text-xs text-gray-600">Total Assignments</div>
              </div>

              <div className="rounded-xl border border-purple-100 bg-purple-50 p-4 text-center">
                <div className="text-2xl font-bold text-purple-600">{candidates.length}</div>
                <div className="mt-1 text-xs text-gray-600">Available Candidates</div>
              </div>
            </div>

            {/* Projects */}
            <div>
              <div className="mb-4 flex items-center justify-between gap-3">
                <h3 className="text-lg font-bold text-gray-900">Projects</h3>
                {anyLoading ? <div className="text-xs font-semibold text-gray-500">Updating…</div> : null}
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                {projects.map((project) => {
                  const members = project?.members || [];
                  const selectedValue = selectedCandidateByProject[project.id] || "";
                  const isLoadingThis = !!loadingByProject[project.id];

                  const availableCandidates = candidates.filter(
                    (cand) => !members.some((m) => String(m.id) === String(cand.id))
                  );

                  return (
                    <div key={project.id} className="h-full min-w-0">
                      <div className="flex h-full min-w-0 flex-col rounded-2xl border-2 border-gray-200 bg-white p-5 transition hover:border-emerald-400 hover:shadow-xl">
                        {/* Card header */}
                        <div className="mb-4 flex min-h-[60px] min-w-0 items-start justify-between gap-3">
                          <h4 className="line-clamp-2 min-w-0 flex-1 text-base font-bold text-gray-900">
                            {project.name}
                          </h4>

                          <span className="flex-shrink-0 whitespace-nowrap rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-bold text-emerald-800">
                            {members.length} {members.length === 1 ? "member" : "members"}
                          </span>
                        </div>

                        {/* Team list */}
                        <div className="mb-4 flex-1 min-w-0">
                          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
                            Current Team
                          </p>

                          <div className="space-y-2 overflow-y-auto pr-1 max-h-[240px] min-w-0">
                            {members.length === 0 ? (
                              <div className="py-2 text-xs italic text-gray-400">No members yet</div>
                            ) : (
                              members.map((member) => (
                                <div
                                  key={member.id}
                                  className="flex min-w-0 items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs transition hover:bg-gray-100"
                                >
                                  <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-emerald-400 to-blue-500 text-xs font-bold text-white">
                                    {(member?.name || "?").charAt(0).toUpperCase()}
                                  </div>

                                  <div className="min-w-0 flex-1">
                                    <div className="truncate font-semibold text-gray-900">
                                      {member?.name || "Unnamed"}
                                    </div>
                                    <div className="truncate text-xs text-gray-500">
                                      {member?.role || "No role"}
                                    </div>
                                  </div>

                                  <button
                                    onClick={() => manageTeam({ action: "remove", project, candidateId: member.id })}
                                    disabled={isLoadingThis}
                                    className="flex-shrink-0 rounded-full p-1 text-gray-400 transition hover:bg-red-50 hover:text-red-500 disabled:opacity-50"
                                    title="Remove from project"
                                    aria-label="Remove member"
                                  >
                                    <span className="text-sm">✕</span>
                                  </button>
                                </div>
                              ))
                            )}
                          </div>
                        </div>

                        {/* Add member */}
                        <div className="mt-auto border-t border-gray-200 pt-3">
                          <div className="flex min-w-0 items-stretch gap-2">
                            <select
                              value={selectedValue}
                              onChange={(e) =>
                                setSelectedCandidateByProject((prev) => ({
                                  ...prev,
                                  [project.id]: e.target.value,
                                }))
                              }
                              className="w-full min-w-0 flex-1 rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500"
                              disabled={isLoadingThis}
                            >
                              <option value="">Add candidate...</option>
                              {availableCandidates.map((cand) => (
                                <option key={cand.id} value={cand.id}>
                                  {cand.full_name} - {cand.primary_role}
                                </option>
                              ))}
                            </select>

                            <button
                              onClick={() => manageTeam({ action: "add", project, candidateId: selectedValue })}
                              disabled={!selectedValue || isLoadingThis}
                              className="flex-shrink-0 whitespace-nowrap rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-md transition hover:bg-emerald-700 hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {isLoadingThis ? "⏳" : "➕ Add"}
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex flex-shrink-0 items-center justify-end gap-3 border-t border-gray-200 bg-white p-4">
          <button
            onClick={() => setShowTeamPanel(false)}
            className="rounded-xl border border-gray-300 bg-white px-4 py-2 text-sm font-semibold text-gray-700 transition hover:bg-gray-100"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default TeamManagementPanel;
