// ---------- Extraction & Parsing (Resumes) ----------
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:5050";
export async function extractPdf(file) {
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch(`${API_BASE}/extract`, {  // REMOVED /api
    method: 'POST',
    body: formData,
    credentials: 'include',
  })

  if (!res.ok) {
    throw new Error(`Extract failed: ${res.status}`)
  }
  return res.json()
}

export async function parseResume(text) {
  const res = await fetch(`${API_BASE}/parse_resume`, {  // REMOVED /api
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
    credentials: 'include',
  })

  if (!res.ok) {
    throw new Error(`Parse resume failed: ${res.status}`)
  }
  return res.json()
}

// ---------- Extraction & Parsing (JD) ----------

export async function extractJd(file) {
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch(`${API_BASE}/extract`, {  // REMOVED /api
    method: 'POST',
    body: formData,
    credentials: 'include',
  })
  if (!res.ok) {
    throw new Error(`JD extract failed: ${res.status}`)
  }
  return res.json()
}

export async function parseJd(text) {
  const res = await fetch(`${API_BASE}/parse_jd`, {  // REMOVED /api
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
    credentials: 'include',
  })
  if (!res.ok) {
    throw new Error(`JD parse failed: ${res.status}`)
  }
  return res.json()
}

// ---------- JD persistence ----------

export async function saveJd(jd) {
  const res = await fetch(`${API_BASE}/jd`, {  // REMOVED /api
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(jd),
    credentials: 'include',
  })
  if (!res.ok) {
    throw new Error(`Save JD failed: ${res.status}`)
  }
  return res.json()
}

export async function fetchJds() {
  const res = await fetch(`${API_BASE}/jd`)  // REMOVED /api
  if (!res.ok) {
    throw new Error(`Fetch JDs failed: ${res.status}`)
  }
  const data = await res.json()
  return data
}

// ---------- Candidate persistence ----------

export async function saveCandidate(rawText, parsed) {
  const res = await fetch(`${API_BASE}/candidates`, {  // REMOVED /api
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ raw_text: rawText, parsed }),
    credentials: 'include',
  })
  if (!res.ok) {
    throw new Error(`Save candidate failed: ${res.status}`)
  }
  return res.json()
}

export async function fetchCandidates() {
  const res = await fetch(`${API_BASE}/candidates`)  // REMOVED /api
  if (!res.ok) {
    throw new Error(`Fetch candidates failed: ${res.status}`)
  }
  const data = await res.json()
  return data
}

// ---------- Screening APIs ----------

export async function runScreening1(jd, candidates) {
  const res = await fetch(`${API_BASE}/screening1`, {  // REMOVED /api
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jd, candidates }),
    credentials: 'include',
  })

  if (!res.ok) {
    throw new Error(`Screening 1 failed: ${res.status}`)
  }
  return res.json()
}

export async function runScreening2(jd, candidates) {
  const res = await fetch(`${API_BASE}/screening2`, {  // REMOVED /api
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jd, candidates }),
    credentials: 'include',
  })
  if (!res.ok) {
    throw new Error(`Screening 2 failed: ${res.status}`)
  }
  return res.json()
}

export async function runScreening3(jd, candidates) {
  const res = await fetch(`${API_BASE}/screening3`, {  // REMOVED /api
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jd, candidates }),
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`Screening 3 failed: ${res.status}`)
  return res.json()
}

export async function runScreening4(jd, candidates) {
  const res = await fetch(`${API_BASE}/screening4`, {  // REMOVED /api
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jd, candidates }),
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`Screening 4 failed: ${res.status}`)
  return res.json()
}

export async function parseBatch(data) {
  const res = await fetch(`${API_BASE}/parse_batch`, {  // REMOVED /api
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`Batch parse failed: ${res.status}`)
  return res.json()
}

export const fetchDashboardStats = async () => {
  const res = await fetch(`${API_BASE}/dashboard`, {
    credentials: 'include',
  })  // Already correct
  if (!res.ok) throw new Error('Failed to fetch dashboard stats')
  return res.json()
}
export async function uploadResume(file) {
  const formData = new FormData();
  formData.append("resume", file);

  const res = await fetch(`${API_BASE}/api/upload-resume`, {
    method: "POST",
    body: formData,
    credentials: 'include',
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || "Failed to upload resume");
  }

  return res.json();
}

export async function batchUploadResumes(files) {
  const formData = new FormData();
  files.forEach((file) => formData.append("resumes", file));

  const res = await fetch(`${API_BASE}/api/batch-upload-resumes`, {
    method: "POST",
    body: formData,
    credentials: 'include',
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || "Failed to batch upload resumes");
  }

  return res.json();
}

export async function semanticSearch(jobDescription, options = {}) {
  const body = {
    job_description: jobDescription,
    top_k: options.topK || 20,
    min_experience_years: options.minExperienceYears || null,
  };

  const res = await fetch(`${API_BASE}/api/search/semantic`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    credentials: 'include',
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || "Semantic search failed");
  }

  return res.json();
}

export async function getCandidateDetails(candidateId) {
  const res = await fetch(`${API_BASE}/api/candidate/${candidateId}`, {
    credentials: 'include',
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || "Failed to fetch candidate details");
  }

  return res.json();
}

export async function getResumePDF(candidateId) {
  // Backend returns JSON with { pdf_url } OR serves the file directly.
  // You already have `/api/resume-pdf/<id>` that uses send_file.
  // For send_file, just open the URL in a new tab.
  return `${API_BASE}/api/resume-pdf/${candidateId}`;
}
export async function uploadJdsCsv(file) {
  const formData = new FormData()
  formData.append('jds_csv', file)

  const res = await fetch(`${API_BASE}/api/upload-jds-csv`, {
    method: 'POST',
    body: formData,
    credentials: 'include',
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.error || 'JD CSV upload failed')
  }
  return res.json()
}