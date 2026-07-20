"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useSession, signIn, signOut } from "next-auth/react";
import { saveJobHistory, getJobHistories, type JobHistoryItem, isErrorLikeString } from "@/lib/api";

type TaskStatus = "idle" | "uploading" | "processing" | "success" | "error";

interface CandidateScore {
  candidate_id: string;
  candidate_name: string | null;
  candidate_email: string | null;
  tfidf_score: number;
  bm25_score: number;
  skill_score: number;
  vector_score: number;
  final_score: number;
  explanation_log: Record<string, any>;
}

interface JobDetail {
  id: string;
  title: string;
  description: string | null;
  created_at: string;
  source: "my-jobs" | "job-history" | "my-resume";
  required_skills?: string | null;
  is_active?: boolean;
  updated_at?: string;
  candidate_email?: string | null;
  candidate_id?: string | null;
}

export default function Home() {
  const { data: session, status: sessionStatus } = useSession();
  const [jobDescription, setJobDescription] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);
  const [status, setStatus] = useState<TaskStatus>("idle");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<CandidateScore[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<string>("");
  const [jobHistories, setJobHistories] = useState<JobHistoryItem[]>([]);
  const [isRegistering, setIsRegistering] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<JobDetail | null>(null);
  const [toast, setToast] = useState<{ message: string; type: "error" | "success" | "info" } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const accessToken = typeof session?.accessToken === "string" ? session.accessToken : undefined;

  const showToast = useCallback((message: string, type: "error" | "success" | "info" = "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 5000);
  }, []);

  const apiFetch = useCallback(
    async (path: string, options: RequestInit = {}, token?: string) => {
      const tk = token ?? accessToken;
      if (!tk) {
        throw new Error("Missing access token");
      }
      const headers: Record<string, string> = {
        ...(options.headers as Record<string, string> | undefined),
      };
      headers["Authorization"] = `Bearer ${tk}`;
      const res = await fetch(`http://127.0.0.1:8001${path}`, {
        ...options,
        headers,
      });
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(`API ${res.status}: ${text || res.statusText}`);
      }
      return res;
    },
    [accessToken]
  );

  const pollTask = async (tid: string): Promise<any> => {
    const res = await apiFetch(`/api/v1/tasks/${tid}`);
    return res.json();
  };

  useEffect(() => {
    if (!accessToken) {
      setJobHistories([]);
      setMyResumes([]);
      setMyJobs([]);
      setMyMatches([]);
      setCandidates([]);
      setStatus("idle");
      setTaskId(null);
      setProgress("");
      setError(null);
      setSelectedJob(null);
      return;
    }
    getJobHistories(accessToken)
      .then(setJobHistories)
      .catch(() => setJobHistories([]));
  }, [accessToken]);

  // Dashboard state (post-login "session details" view)
  const [myResumes, setMyResumes] = useState<any[]>([]);
  const [myJobs, setMyJobs] = useState<any[]>([]);
  const [myMatches, setMyMatches] = useState<any[]>([]);
  const [dashLoading, setDashLoading] = useState(false);

  const loadDashboard = useCallback(
    async (tk?: string) => {
      const token = tk ?? accessToken;
      if (!token) return;
      setDashLoading(true);
      try {
        const [r, j, m] = await Promise.all([
          apiFetch("/api/v1/resumes/", {}, token).then((x) => x.json()),
          apiFetch("/api/v1/jobs/", {}, token).then((x) => x.json()),
          apiFetch("/api/v1/matches/history", {}, token).then((x) => x.json()),
        ]);
        setMyResumes(r.candidates ?? []);
        setMyJobs(j.jobs ?? []);
        setMyMatches(m.matches ?? []);
      } catch {
        /* dashboard is best-effort; ignore errors */
      } finally {
        setDashLoading(false);
      }
    },
    [accessToken, apiFetch]
  );

  // Reload the dashboard whenever the session (account) changes.
  useEffect(() => {
    if (session?.accessToken) loadDashboard();
  }, [session?.accessToken, loadDashboard]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setCandidates([]);

    if (isErrorLikeString(jobDescription)) {
      showToast("Invalid job description. Please paste actual job content, not error messages.", "error");
      return;
    }

    if (!jobDescription.trim() || !files || files.length === 0) {
      showToast("Please provide a job description and at least one resume.", "error");
      return;
    }

    if (!accessToken) {
      showToast("Session expired. Please log in again.", "error");
      return;
    }

    try {
      setStatus("uploading");
      setProgress("Creating job...");

      const jobRes = await apiFetch("/api/v1/jobs/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: "Uploaded Job",
          description: jobDescription,
          required_skills: [],
          preferred_skills: [],
        }),
      });
      const jobData = await jobRes.json();
      const jobId = jobData.job_id;

      try {
        const historyPayload = {
          title: "Uploaded Job",
          description: jobDescription,
          required_skills: "",
        };
        console.log("PAYLOAD:", historyPayload);
        const savedHistory = await saveJobHistory(historyPayload, accessToken);
        console.log("HISTORY SAVED:", savedHistory);
        const histories = await getJobHistories(accessToken);
        setJobHistories(histories);
      } catch (historyError: any) {
        console.error("HISTORY ERROR:", historyError);
      }

      setProgress(`Uploading ${files.length} resume(s)...`);
      const candidateIds: string[] = [];

      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const formData = new FormData();
        formData.append("file", file, file.name);

        const resumeRes = await apiFetch("/api/v1/resumes/", {
          method: "POST",
          body: formData,
        });
        const resumeData = await resumeRes.json();
        let ingestResult = await pollTask(resumeData.task_id);
        const ingestStart = Date.now();
        while (
          ingestResult.status !== "success" &&
          ingestResult.status !== "failure" &&
          ingestResult.status !== "SUCCESS" &&
          ingestResult.status !== "FAILURE"
        ) {
          if (Date.now() - ingestStart > 5 * 60 * 1000) {
            throw new Error(`Ingestion timed out for ${file.name}`);
          }
          await new Promise((r) => setTimeout(r, 2000));
          ingestResult = await pollTask(resumeData.task_id);
        }
        if (ingestResult.status !== "success" && ingestResult.result?.status !== "success") {
          const ingestError = ingestResult.result?.error || ingestResult.error || "Unknown error";
          throw new Error(`Ingestion failed for ${file.name}: ${ingestError}`);
        }
        const candidateId = ingestResult.result?.candidate_id || ingestResult.candidate_id;
        candidateIds.push(candidateId);
        setProgress(`Uploaded ${i + 1}/${files.length} resumes...`);
      }

      setProgress("Running AI matching...");
      
      const myResumeIds = new Set((myResumes || []).map((r: any) => r.id));
      const validCandidateIds = candidateIds.filter((id) => myResumeIds.has(id));
      const skippedCount = candidateIds.length - validCandidateIds.length;
      
      if (skippedCount > 0) {
        showToast(
          `Skipped ${skippedCount} candidate(s) from a previous session. Matching with ${validCandidateIds.length} current candidate(s).`,
          "info",
        );
      }
      
      if (validCandidateIds.length === 0) {
        showToast("No valid candidates available for matching. Please upload resumes first.", "error");
        setStatus("error");
        setProgress("");
        return;
      }
      
      const matchRes = await apiFetch("/api/v1/matches/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: jobId, candidate_ids: validCandidateIds }),
      });
      const matchData = await matchRes.json();
      const matchTaskId = matchData.task_id;
      setTaskId(matchTaskId);
      setStatus("processing");

      let matchResult = await pollTask(matchTaskId);
      const matchStart = Date.now();
      while (
        matchResult.status !== "success" &&
        matchResult.status !== "failure" &&
        matchResult.status !== "SUCCESS" &&
        matchResult.status !== "FAILURE"
      ) {
        if (Date.now() - matchStart > 5 * 60 * 1000) {
          throw new Error("Matching timed out");
        }
        await new Promise((r) => setTimeout(r, 2000));
        matchResult = await pollTask(matchTaskId);
      }

      if (matchResult.status === "success" || matchResult.result?.status === "success") {
        const matches = matchResult.result?.matches || matchResult.matches || [];
        setCandidates(matches);
        setStatus("success");
        setProgress("Analysis complete.");
      } else {
        throw new Error(matchResult.result?.error || matchResult.error || "Matching failed");
      }
    } catch (err: any) {
      const message = err.message || "An unexpected error occurred";
      console.error("[handleSubmit error]", err);
      if (isErrorLikeString(message)) {
        const statusMatch = message.match(/^API (\d{3})/);
        const status = statusMatch ? statusMatch[1] : "error";
        const detail = message.replace(/^API \d{3}: /, "").slice(0, 120);
        showToast(`Request failed (HTTP ${status}): ${detail || "Please try again or contact support."}`, "error");
      } else {
        showToast(message, "error");
      }
      setStatus("error");
      setProgress("");
    }
  };

  if (sessionStatus === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-black">
        <p className="text-zinc-600 dark:text-zinc-400">Loading...</p>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-black">
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setAuthError(null);
            const form = e.target as HTMLFormElement;
            const email = form.email.value;
            const password = form.password.value;

            if (isRegistering) {
              try {
                const regRes = await fetch("http://127.0.0.1:8001/api/v1/auth/register", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ email, password }),
                });
                if (!regRes.ok) {
                  const data = await regRes.json().catch(() => ({}));
                  throw new Error(data.detail || "Registration failed");
                }
                await signIn("credentials", { email, password, redirect: false });
              } catch (err: any) {
                setAuthError(err.message || "Registration failed");
              }
              return;
            }

            const result = await signIn("credentials", {
              email,
              password,
              redirect: false,
            });
            if (result?.error) {
              setAuthError("Invalid email or password");
            }
          }}
          className="w-full max-w-sm rounded-lg bg-white p-6 shadow-md dark:bg-zinc-900"
        >
          <h2 className="mb-4 text-xl font-semibold text-zinc-900 dark:text-zinc-50">
            {isRegistering ? "Create an account" : "Sign in to ResumeRanker"}
          </h2>
          <input
            name="email"
            type="email"
            required
            placeholder="Email"
            className="mb-3 w-full rounded-md border border-zinc-300 p-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
          <input
            name="password"
            type="password"
            required
            minLength={8}
            placeholder="Password (min 8 characters)"
            className="mb-4 w-full rounded-md border border-zinc-300 p-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
          <button
            type="submit"
            className="w-full rounded-md bg-zinc-900 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            {isRegistering ? "Sign Up" : "Sign In"}
          </button>
          {authError && (
            <p className="mt-3 text-xs text-red-600 dark:text-red-400">{authError}</p>
          )}
          <button
            type="button"
            onClick={() => {
              setIsRegistering(!isRegistering);
              setAuthError(null);
            }}
            className="mt-3 text-sm text-gray-400 hover:text-white cursor-pointer transition-colors"
          >
            {isRegistering
              ? "Already have an account? Sign in"
              : "Don't have an account? Sign up"}
          </button>
          {!isRegistering && (
            <p className="mt-3 text-xs text-zinc-500 dark:text-zinc-400">
              Demo: demo@resumeranker.local / demo1234
            </p>
          )}
        </form>
      </div>
    );
  }

  const isProcessing = status === "uploading" || status === "processing";

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-black">
      {/* Toast notification */}
      {toast && (
        <div
          className={`fixed top-4 right-4 z-50 rounded-md p-4 shadow-lg ${
            toast.type === "error"
              ? "bg-red-50 text-red-800 dark:bg-red-900/20 dark:text-red-200"
              : toast.type === "success"
              ? "bg-green-50 text-green-800 dark:bg-green-900/20 dark:text-green-200"
              : "bg-blue-50 text-blue-800 dark:bg-blue-900/20 dark:text-blue-200"
          }`}
        >
          <div className="flex items-center justify-between gap-4">
            <p className="text-sm font-medium">{toast.message}</p>
            <button
              onClick={() => setToast(null)}
              className="text-lg leading-none opacity-70 hover:opacity-100"
            >
              &times;
            </button>
          </div>
        </div>
      )}

      {/* Job detail modal */}
      {selectedJob && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) setSelectedJob(null);
          }}
        >
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-lg bg-white p-6 shadow-xl dark:bg-zinc-900">
            <div className="flex items-start justify-between">
              <h3 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">
                {selectedJob.title}
              </h3>
              <button
                onClick={() => setSelectedJob(null)}
                className="ml-4 text-2xl leading-none text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-50"
              >
                &times;
              </button>
            </div>
            <div className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
              Created: {new Date(selectedJob.created_at).toLocaleString()}
              {selectedJob.updated_at && (
                <span> &middot; Updated: {new Date(selectedJob.updated_at).toLocaleString()}</span>
              )}
              {selectedJob.is_active !== undefined && (
                <span> &middot; {selectedJob.is_active ? "Active" : "Inactive"}</span>
              )}
            </div>
            {selectedJob.required_skills && (
              <div className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
                <span className="font-medium">Required Skills:</span> {selectedJob.required_skills}
              </div>
            )}
            <div className="mt-6">
              <h4 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Description</h4>
              <p className="mt-2 whitespace-pre-wrap rounded-md bg-zinc-50 p-4 text-sm text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                {selectedJob.description || "No description provided."}
              </p>
            </div>
            {selectedJob.source === "my-jobs" && myMatches.filter((m) => m.job_id === selectedJob.id).length > 0 && (
              <div className="mt-6">
                <h4 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Match Results</h4>
                <div className="mt-3 space-y-2">
                  {myMatches
                    .filter((m) => m.job_id === selectedJob.id)
                    .map((m, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between rounded-md bg-zinc-50 p-3 dark:bg-zinc-800"
                      >
                        <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                          {m.candidate_name || "Candidate"}
                        </span>
                        <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                          {m.final_score.toFixed(2)}
                        </span>
                      </div>
                    ))}
                </div>
              </div>
            )}
            {selectedJob.source === "my-resume" && (
              <div className="mt-6">
                <h4 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Candidate Details</h4>
                <div className="mt-3 space-y-2">
                  {selectedJob.candidate_email && (
                    <div className="flex items-center justify-between rounded-md bg-zinc-50 p-3 dark:bg-zinc-800">
                      <span className="text-sm font-medium text-zinc-500 dark:text-zinc-400">Email</span>
                      <span className="text-sm text-zinc-900 dark:text-zinc-100">{selectedJob.candidate_email}</span>
                    </div>
                  )}
                  {selectedJob.candidate_id && (
                    <div className="flex items-center justify-between rounded-md bg-zinc-50 p-3 dark:bg-zinc-800">
                      <span className="text-sm font-medium text-zinc-500 dark:text-zinc-400">Candidate ID</span>
                      <span className="font-mono text-xs text-zinc-900 dark:text-zinc-100">{selectedJob.candidate_id}</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <main className="mx-auto max-w-5xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="mb-10 flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50">
              ResumeRanker
            </h1>
            <p className="mt-2 text-lg text-zinc-600 dark:text-zinc-400">
              Upload a job description and resumes to rank candidates with AI.
            </p>
          </div>
          <button
            onClick={() => signOut()}
            className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            Sign Out
          </button>
        </div>

        {/* Dashboard: session details */}
        {session && (
          <div className="mt-10 space-y-8">
            {dashLoading && (
              <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading your dashboard…</p>
            )}

            {/* My Resumes */}
            <section className="rounded-lg bg-white p-6 shadow-md dark:bg-zinc-900">
              <h3 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">
                My Resumes ({myResumes.length})
              </h3>
              {myResumes.length === 0 ? (
                <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">No resumes uploaded yet.</p>
              ) : (
                <ul className="mt-4 divide-y divide-zinc-100 dark:divide-zinc-800">
                  {myResumes.map((r: any) => (
                    <li
                      key={r.id}
                      onClick={() => setSelectedJob({
                        id: r.id,
                        title: r.name || "Unnamed candidate",
                        description: `Candidate from uploaded resume. Skills: ${(r.skills || []).join(", ")}`,
                        created_at: r.created_at || new Date().toISOString(),
                        source: "my-resume",
                        candidate_email: r.email,
                        candidate_id: r.id,
                      })}
                      className="cursor-pointer py-3 transition-all hover:border-gray-600 dark:hover:border-zinc-600"
                    >
                      <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                        {r.name || "Unnamed candidate"}
                      </p>
                      <p className="text-xs text-zinc-500 dark:text-zinc-400">{r.email}</p>
                      <p className="text-xs text-zinc-500 dark:text-zinc-400">
                        Skills: {(r.skills || []).slice(0, 8).join(", ")}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {/* My Jobs */}
            <section className="rounded-lg bg-white p-6 shadow-md dark:bg-zinc-900">
              <h3 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">
                My Jobs ({myJobs.length})
              </h3>
              {myJobs.length === 0 ? (
                <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">No jobs created yet.</p>
              ) : (
                <ul className="mt-4 divide-y divide-zinc-100 dark:divide-zinc-800">
                  {myJobs.map((j: any) => (
                    <li
                      key={j.id}
                      onClick={() => setSelectedJob({ id: j.id, title: j.title, description: j.description, created_at: j.created_at, source: "my-jobs" })}
                      className="cursor-pointer py-3 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
                    >
                      <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{j.title}</p>
                      <p className="text-xs text-zinc-500 dark:text-zinc-400 line-clamp-1">
                        {j.description}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {/* Match History */}
            <section className="rounded-lg bg-white p-6 shadow-md dark:bg-zinc-900">
              <h3 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">
                Match History ({myMatches.length})
              </h3>
              {myMatches.length === 0 ? (
                <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">No matches run yet.</p>
              ) : (
                <ul className="mt-4 divide-y divide-zinc-100 dark:divide-zinc-800">
                  {myMatches.map((m: any, idx: number) => (
                    <li key={idx} className="py-3 flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                          {m.candidate_name || "Candidate"} → {m.job_title || "Job"}
                        </p>
                      </div>
                      <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                        {m.final_score.toFixed(2)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-8">
          <section className="rounded-lg bg-white p-6 shadow-md dark:bg-zinc-900">
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">
              Job Description
            </h2>
            <textarea
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
              placeholder="Paste the job description here..."
              rows={6}
              className="mt-4 w-full rounded-md border border-zinc-300 p-3 text-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
            />
          </section>

          <section className="rounded-lg bg-white p-6 shadow-md dark:bg-zinc-900">
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">
              Resumes
            </h2>
            <div
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                if (e.dataTransfer.files) setFiles(e.dataTransfer.files);
              }}
              className="mt-4 flex cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed border-zinc-300 p-8 transition-colors hover:border-zinc-400 dark:border-zinc-700 dark:hover:border-zinc-600"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx"
                multiple
                onChange={(e) => setFiles(e.target.files)}
                className="hidden"
              />
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                {files && files.length > 0
                  ? `${files.length} file(s) selected`
                  : "Click to upload or drag and drop PDF/DOCX resumes"}
              </p>
            </div>
          </section>

          <div className="flex items-center justify-between">
            <button
              type="submit"
              disabled={isProcessing}
              className="rounded-md bg-zinc-900 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
            >
              {isProcessing ? "Processing..." : "Match Candidates"}
            </button>
            {isProcessing && (
              <span className="text-sm text-zinc-600 dark:text-zinc-400">{progress}</span>
            )}
          </div>
        </form>

        {error && (
          <div className="mt-8 rounded-md bg-red-50 p-4 text-sm text-red-800 dark:bg-red-900/20 dark:text-red-200">
            {error}
          </div>
        )}

        {status === "processing" && (
          <div className="mt-10 flex flex-col items-center justify-center space-y-4">
            <div className="h-12 w-12 animate-spin rounded-full border-4 border-zinc-300 border-t-zinc-900 dark:border-zinc-700 dark:border-t-zinc-100" />
            <p className="text-lg font-medium text-zinc-700 dark:text-zinc-300">
              AI Analyzing Candidates...
            </p>
            {taskId && (
              <p className="font-mono text-xs text-zinc-500 dark:text-zinc-400">
                Task ID: {taskId}
              </p>
            )}
          </div>
        )}

        {status === "success" && candidates.length > 0 && (
          <section className="mt-12">
            <div className="mb-6 flex items-center justify-between">
              <h3 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">
                Leaderboard
              </h3>
              <div className="text-xs text-zinc-500 dark:text-zinc-400">
                Scoring against: Uploaded Job
              </div>
            </div>
            <div className="space-y-4">
              {candidates.map((c, idx) => (
                <div
                  key={c.candidate_id}
                  className="rounded-lg bg-white p-5 shadow-md dark:bg-zinc-900"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-3">
                        <span className="text-lg font-bold text-zinc-500 dark:text-zinc-400">
                          #{idx + 1}
                        </span>
                        <h4 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
                          {c.candidate_name || "Unknown Candidate"}
                        </h4>
                      </div>
                      {c.candidate_email && (
                        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                          {c.candidate_email}
                        </p>
                      )}
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">
                        {c.final_score.toFixed(1)}
                      </div>
                      <div className="text-xs text-zinc-500 dark:text-zinc-400">/ 100</div>
                    </div>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2">
                    {(c.explanation_log?.matched_skills || []).map((skill: string) => (
                      <span
                        key={skill}
                        className="rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900/30 dark:text-green-300"
                      >
                        {skill}
                      </span>
                    ))}
                    {(c.explanation_log?.missing_skills || []).map((skill: string) => (
                      <span
                        key={skill}
                        className="rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-800 dark:bg-red-900/30 dark:text-red-300"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>

                  <div className="mt-4 grid grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="whitespace-nowrap text-zinc-500 dark:text-zinc-400">Keyword Match (TF)</span>
                      <div className="font-medium text-zinc-900 dark:text-zinc-50">
                        {(c.tfidf_score * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div>
                      <span className="whitespace-nowrap text-zinc-500 dark:text-zinc-400">Keyword Match (BM)</span>
                      <div className="font-medium text-zinc-900 dark:text-zinc-50">
                        {(c.bm25_score * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div>
                      <span className="whitespace-nowrap text-zinc-500 dark:text-zinc-400">Contextual Match</span>
                      <div className="font-medium text-zinc-900 dark:text-zinc-50">
                        {(c.vector_score * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div>
                      <span className="whitespace-nowrap text-zinc-500 dark:text-zinc-400">Hard Skills Overlap</span>
                      <div className="font-medium text-zinc-900 dark:text-zinc-50">
                        {(c.skill_score * 100).toFixed(1)}%
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {jobHistories.length > 0 ? (
          <section className="mt-12">
            <h3 className="mb-6 text-2xl font-bold text-zinc-900 dark:text-zinc-50">
              Job History
            </h3>
            <div className="space-y-3">
              {jobHistories.map((jh) => (
                <div
                  key={jh.id}
                  onClick={() => setSelectedJob({
                    id: jh.id,
                    title: jh.title,
                    description: jh.description,
                    created_at: jh.created_at,
                    source: "job-history",
                    required_skills: jh.required_skills,
                    is_active: jh.is_active,
                    updated_at: jh.updated_at,
                  })}
                  className="cursor-pointer rounded-lg border border-zinc-200 bg-white p-4 shadow-sm transition-all hover:border-gray-600 dark:border-zinc-800 dark:bg-zinc-900"
                >
                  <div className="flex items-center justify-between">
                    <h4 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
                      {jh.title}
                    </h4>
                    <span className="text-xs text-zinc-500 dark:text-zinc-400">
                      {new Date(jh.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <p className="mt-2 line-clamp-2 text-sm text-zinc-600 dark:text-zinc-400">
                    {jh.description}
                  </p>
                </div>
              ))}
            </div>
          </section>
        ) : (
          <section className="mt-12">
            <h3 className="mb-6 text-2xl font-bold text-zinc-900 dark:text-zinc-50">
              Job History
            </h3>
            <p className="text-zinc-500 dark:text-zinc-400">No saved sessions found.</p>
          </section>
        )}
      </main>
    </div>
  );
}
