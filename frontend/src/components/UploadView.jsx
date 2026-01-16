import React, { useState } from "react";
import { uploadResume, batchUploadResumes } from "../services/api";

function UploadView() {
  const [singleFile, setSingleFile] = useState(null);
  const [batchFiles, setBatchFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [batchResult, setBatchResult] = useState(null);
  const [error, setError] = useState("");

  const handleSingleChange = (e) => {
    const file = e.target.files?.[0] || null;
    setSingleFile(file);
    setResult(null);
    setError("");
  };

  const handleBatchChange = (e) => {
    const files = e.target.files ? Array.from(e.target.files) : [];
    setBatchFiles(files);
    setBatchResult(null);
    setError("");
  };

  const handleSingleUpload = async () => {
    if (!singleFile) return;
    setLoading(true);
    setError("");
    try {
      const res = await uploadResume(singleFile);
      setResult(res);
    } catch (err) {
      setError(err.message || "Failed to upload");
    } finally {
      setLoading(false);
    }
  };

  const handleBatchUpload = async () => {
    if (!batchFiles.length) return;
    setLoading(true);
    setError("");
    try {
      const res = await batchUploadResumes(batchFiles);
      setBatchResult(res);
    } catch (err) {
      setError(err.message || "Failed to batch upload");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Upload Resumes</h2>

      {error && <p className="text-red-500 text-sm">{error}</p>}
      {loading && <p className="text-sm text-gray-500">Processing…</p>}

      <div className="border rounded p-4 space-y-3 bg-white">
        <h3 className="font-medium text-sm">Single Resume</h3>
        <input
          type="file"
          accept="application/pdf"
          onChange={handleSingleChange}
        />
        <button
          onClick={handleSingleUpload}
          disabled={!singleFile || loading}
          className="px-3 py-1 rounded bg-blue-600 text-white text-sm disabled:opacity-50"
        >
          Upload &amp; Process
        </button>

        {result?.success && (
          <div className="mt-3 text-sm">
            <p className="font-medium">
              Processed: {result.candidate_name} (ID: {result.candidate_id})
            </p>
            <p>Total Jobs: {result.stats.total_jobs}</p>
            <p>Total Experience: {result.stats.total_experience_years} years</p>
            <p>Total Responsibilities: {result.stats.total_responsibilities}</p>
            <p>Total Skills: {result.stats.skills_count}</p>
          </div>
        )}
      </div>

      <div className="border rounded p-4 space-y-3 bg-white">
        <h3 className="font-medium text-sm">Batch Upload</h3>
        <input
          type="file"
          accept="application/pdf"
          multiple
          onChange={handleBatchChange}
        />
        <button
          onClick={handleBatchUpload}
          disabled={!batchFiles.length || loading}
          className="px-3 py-1 rounded bg-blue-600 text-white text-sm disabled:opacity-50"
        >
          Upload All &amp; Process
        </button>

        {batchResult && (
          <div className="mt-3 text-sm">
            <p className="font-medium">
              Processed {batchResult.successful}/{batchResult.total} resumes
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default UploadView;
