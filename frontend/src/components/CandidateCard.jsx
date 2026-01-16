import React from "react";
import { getResumePDF } from "../services/api";

function CandidateCard({ candidate }) {
  const {
    candidate_id,
    candidate_name,
    total_experience_years,
    parsed_data = {},
  } = candidate || {};

  const workExperiences = parsed_data.work_experiences || [];
  const skills = parsed_data.technical_skills || [];

  const handleViewResume = async () => {
    const url = await getResumePDF(candidate_id);
    window.open(url, "_blank", "noopener,noreferrer");
  };

  return (
    <div className="border rounded p-4 space-y-3 bg-white shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">{candidate_name}</h3>
          <p className="text-sm text-gray-600">
            Total Experience:{" "}
            {typeof total_experience_years === "number"
              ? total_experience_years.toFixed(1)
              : "N/A"}{" "}
            years
          </p>
        </div>
        <button
          onClick={handleViewResume}
          className="px-3 py-1 text-sm rounded bg-slate-800 text-white"
        >
          View Original Resume
        </button>
      </div>

      <div>
        <h4 className="font-medium mb-1 text-sm">Work Experience</h4>
        <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
          {workExperiences.map((exp, idx) => (
            <div key={idx} className="border rounded px-2 py-1 text-sm">
              <p className="font-semibold">
                {exp.job_title}{" "}
                <span className="font-normal">at {exp.company_name}</span>
              </p>
              <p className="text-xs text-gray-600">
                {exp.start_date} – {exp.end_date} · {exp.duration_months} months
              </p>
              {exp.location && (
                <p className="text-xs text-gray-500">{exp.location}</p>
              )}
              <ul className="list-disc ml-4 mt-1 space-y-1">
                {(exp.responsibilities || []).map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h4 className="font-medium mb-1 text-sm">Technical Skills</h4>
        <div className="flex flex-wrap gap-1 text-xs">
          {skills.map((skill, i) => (
            <span
              key={i}
              className="px-2 py-0.5 rounded-full bg-slate-100 border border-slate-200"
            >
              {skill}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

export default CandidateCard;
