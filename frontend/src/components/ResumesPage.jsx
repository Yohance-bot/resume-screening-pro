// src/components/ResumesPage.jsx
import React from "react"

export default function ResumesPage({
  selectedFiles,
  setSelectedFiles,
  uploadStatus,
  handleResumeUpload,
}) {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="max-w-xl w-full rounded-3xl bg-white/80 backdrop-blur-xl border border-white/40 shadow-2xl p-6">
        <h2 className="text-lg font-semibold text-emerald-900 mb-2">
          Upload resumes
        </h2>
        <p className="text-xs text-emerald-800/80 mb-4">
          Upload PDF / DOCX resumes. They&apos;ll be parsed and added to the
          vector database for chat.
        </p>
        <input
          type="file"
          accept=".pdf,.docx"
          multiple
          onChange={(e) =>
            setSelectedFiles(Array.from(e.target.files || []))
          }
          className="block w-full text-sm text-emerald-900
                     file:mr-3 file:py-2 file:px-3
                     file:rounded-xl file:border-0
                     file:text-sm file:font-medium
                     file:bg-emerald-500 file:text-white
                     hover:file:bg-emerald-400"
        />
        <div className="mt-3 flex items-center justify-between">
          <span className="text-xs text-emerald-800">
            {selectedFiles.length
              ? `${selectedFiles.length} file(s) selected`
              : "No files selected yet"}
          </span>
          <button
            onClick={handleResumeUpload}
            disabled={!selectedFiles.length}
            className="text-xs bg-emerald-500 hover:bg-emerald-400 text-white px-3 py-2 rounded-xl font-medium shadow disabled:opacity-50"
          >
            Upload &amp; parse
          </button>
        </div>
        {uploadStatus && (
          <div className="mt-3 text-xs text-emerald-800">{uploadStatus}</div>
        )}
      </div>
    </div>
  )
}
