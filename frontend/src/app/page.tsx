"use client";

import { useState, useRef, useEffect, useCallback } from "react";

type TaskStatus = "idle" | "uploading" | "processing" | "success" | "error";

interface CandidateScore {
  candidate_id: string;
  candidate_name: string | null;
  candidate_email: string | null;
  tfidf_score: number;
  bm25_score: number;
  skill_score: number;
  final_score: number;
  explanation_log: Record<string, any>;
}

export default function Home() {
  const [jobDescription, setJobDescription] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);
  const [status, setStatus] = useState<TaskStatus>("idle");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<CandidateScore[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const resetState = useCallback(() => {
    setStatus("idle");
    setTaskId(null);
    setCandidates([]);
    setError(null);
    setProgress("");
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFiles(e.target.files);
  };



  const pollTask = async (tid: string): Promise<any> => {
    const res = await fetch(`/api/v1/tasks/${tid}`);
    if (!res.ok) throw new Error(`Poll failed: ${res.status}`);
    return res.json();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setCandidates([]);

    if (!jobDescription.trim() || !files || files.length === 0) {
      setError("Please provide a job description and at least one resume.");
      return;
    }

    try {
      setStatus("uploading");
      setProgress("Creating job...");

      // Step 1: Create job
      const jobRes = await fetch("/api/v1/jobs/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: "Uploaded Job",
          description: jobDescription,
          required_skills: [],
          preferred_skills: [],
        }),
      });
      if (!jobRes.ok) throw new Error(`Job creation failed: ${jobRes.status}`);
      const jobData = await jobRes.json();
      const jobId = jobData.job_id;

      // Step 2: Upload resumes
      setProgress(`Uploading ${files.length} resume(s)...`);
      const candidateIds: string[] = [];

      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const formData = new FormData();
        formData.append("file", file);

        const resumeRes = await fetch("/api/v1/resumes/", {
          method: "POST",
          body: formData,
        });
        if (!resumeRes.ok) {
          const errData = await resumeRes.json().catch(() => ({}));
          throw new Error(`Resume upload failed for ${file.name}: ${errData.detail || resumeRes.statusText}`);
        }
        const resumeData = await resumeRes.json();
        // Wait for ingestion task to complete
        let ingestResult = await pollTask(resumeData.task_id);
        while (ingestResult.status === "pending" || ingestResult.status === "PENDING") {
          await new Promise((r) => setTimeout(r, 2000));
          ingestResult = await pollTask(resumeData.task_id);
        }
        if (ingestResult.status !== "success" && ingestResult.result?.status !== "success") {
          throw new Error(`Ingestion failed for ${file.name}`);
        }
        const candidateId = ingestResult.result?.candidate_id || ingestResult.candidate_id;
        candidateIds.push(candidateId);
        setProgress(`Uploaded ${i + 1}/${files.length} resumes...`);
      }

      // Step 3: Trigger matching
      setProgress("Running AI matching...");
      const matchRes = await fetch("/api/v1/matches/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: jobId, candidate_ids: candidateIds }),
      });
      if (!matchRes.ok) throw new Error(`Match request failed: ${matchRes.status}`);
      const matchData = await matchRes.json();
      const matchTaskId = matchData.task_id;
      setTaskId(matchTaskId);
      setStatus("processing");

      // Step 4: Poll match task
      let matchResult = await pollTask(matchTaskId);
      while (matchResult.status === "pending" || matchResult.status === "PENDING") {
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
      setError(err.message || "An unexpected error occurred");
      setStatus("error");
      setProgress("");
    }
  };

  const isProcessing = status === "uploading" || status === "processing";

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-black">
      <main className="mx-auto max-w-5xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="mb-10 text-center">
          <h1 className="text-4xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50">
            ResumeRanker
          </h1>
          <p className="mt-2 text-lg text-zinc-600 dark:text-zinc-400">
            Upload a job description and resumes to rank candidates with AI.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-8">
          {/* Job Description */}
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

          {/* Resume Upload */}
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
                onChange={handleFileChange}
                className="hidden"
              />
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                {files && files.length > 0
                  ? `${files.length} file(s) selected`
                  : "Click to upload or drag and drop PDF/DOCX resumes"}
              </p>
            </div>
          </section>

          {/* Submit */}
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

        {/* Error */}
        {error && (
          <div className="mt-8 rounded-md bg-red-50 p-4 text-sm text-red-800 dark:bg-red-900/20 dark:text-red-200">
            {error}
          </div>
        )}

        {/* Loading State */}
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

        {/* Leaderboard */}
        {status === "success" && candidates.length > 0 && (
          <section className="mt-12">
            <h3 className="mb-6 text-2xl font-bold text-zinc-900 dark:text-zinc-50">
              Leaderboard
            </h3>
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

                  {/* Skill badges */}
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

                  {/* Score breakdown */}
                  <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <span className="text-zinc-500 dark:text-zinc-400">TF-IDF</span>
                      <div className="font-medium text-zinc-900 dark:text-zinc-50">
                        {(c.tfidf_score * 100).toFixed(1)}
                      </div>
                    </div>
                    <div>
                      <span className="text-zinc-500 dark:text-zinc-400">BM25</span>
                      <div className="font-medium text-zinc-900 dark:text-zinc-50">
                        {(c.bm25_score * 100).toFixed(1)}
                      </div>
                    </div>
                    <div>
                      <span className="text-zinc-500 dark:text-zinc-400">Skills</span>
                      <div className="font-medium text-zinc-900 dark:text-zinc-50">
                        {(c.skill_score * 100).toFixed(1)}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}