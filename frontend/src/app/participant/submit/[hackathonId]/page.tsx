"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { CheckCircle2, ExternalLink, Github, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { hackathonApi, submissionApi, ApiError } from "@/lib/api";
import { rememberSubmission, getMySubmissionId } from "@/lib/mySubmissions";
import { useAuthStore } from "@/store/auth";

interface RepoPreview {
  name: string;
  full_name: string;
  description: string | null;
  language: string | null;
}

function parseGithubUrl(url: string): { owner: string; repo: string } | null {
  const match = url.trim().match(/github\.com\/([^/\s]+)\/([^/\s.]+)/i);
  if (!match) return null;
  return { owner: match[1], repo: match[2].replace(/\.git$/, "") };
}

export default function SubmitPage({ params }: { params: { hackathonId: string } }) {
  const router = useRouter();
  const { hackathonId } = params;
  const userId = useAuthStore((s) => s.user?.id);
  const { data: hackathon } = useSWR(["hackathon", hackathonId], () => hackathonApi.get(hackathonId));

  const [repoUrl, setRepoUrl] = useState("");
  const [preview, setPreview] = useState<RepoPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Captured once at mount, not recomputed on every render: a successful
  // submit calls rememberSubmission() (mutating localStorage) right before
  // router.push() navigates away, and re-reading localStorage on every
  // render would flip this to true and render the "already submitted"
  // branch instead — stranding the user on this page since the early
  // return short-circuits before the navigating render ever commits.
  const [existingSubmissionId] = useState(() => getMySubmissionId(userId, hackathonId));

  useEffect(() => {
    const parsed = parseGithubUrl(repoUrl);
    if (!parsed) {
      setPreview(null);
      setPreviewError(repoUrl.trim() ? "Enter a valid GitHub repository URL." : null);
      return;
    }
    setPreviewError(null);
    setPreviewLoading(true);
    const timeout = setTimeout(async () => {
      try {
        const res = await fetch(`https://api.github.com/repos/${parsed.owner}/${parsed.repo}`);
        if (!res.ok) {
          setPreview(null);
          setPreviewError("Repository not found or not public.");
          return;
        }
        const data = await res.json();
        setPreview({ name: data.name, full_name: data.full_name, description: data.description, language: data.language });
      } catch {
        setPreviewError("Couldn't reach GitHub to preview this repository.");
      } finally {
        setPreviewLoading(false);
      }
    }, 500);
    return () => clearTimeout(timeout);
  }, [repoUrl]);

  const handleSubmit = async () => {
    if (!userId) return;
    setSubmitError(null);
    setSubmitting(true);
    try {
      const submission = await submissionApi.create(hackathonId, repoUrl.trim());
      rememberSubmission(userId, hackathonId, submission.id);
      router.push(`/participant/evaluation/${submission.id}`);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Unable to submit your repository. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (existingSubmissionId) {
    return (
      <div className="mx-auto max-w-lg text-center">
        <p className="mb-4 text-gray-400">You&apos;ve already submitted to this hackathon.</p>
        <Button asChild>
          <a href={`/participant/evaluation/${existingSubmissionId}`}>View your evaluation</a>
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg">
      <h1 className="mb-1 text-2xl font-bold text-white">Submit your repository</h1>
      <p className="mb-6 text-sm text-gray-400">{hackathon?.title}</p>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">GitHub repository URL</CardTitle>
          <CardDescription>Must be a public repository.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="repoUrl">Repository URL</Label>
            <Input
              id="repoUrl"
              placeholder="https://github.com/owner/repo"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
            />
          </div>

          {previewLoading && <p className="text-sm text-gray-500">Checking repository...</p>}
          {previewError && (
            <div className="flex items-center gap-2 text-sm text-error">
              <XCircle className="h-4 w-4" />
              {previewError}
            </div>
          )}
          {preview && (
            <div className="rounded-lg border border-white/10 bg-card-elevated p-4">
              <div className="mb-1 flex items-center gap-2">
                <Github className="h-4 w-4 text-gray-400" />
                <span className="font-medium text-white">{preview.full_name}</span>
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              </div>
              {preview.description && <p className="mb-2 text-sm text-gray-400">{preview.description}</p>}
              {preview.language && <p className="text-xs text-gray-500">Primary language: {preview.language}</p>}
              <a
                href={repoUrl}
                target="_blank"
                rel="noreferrer"
                className="mt-2 inline-flex items-center gap-1 text-xs text-accent hover:underline"
              >
                View on GitHub <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          )}

          {submitError && (
            <Alert variant="destructive">
              <AlertDescription>{submitError}</AlertDescription>
            </Alert>
          )}

          <Button className="w-full" disabled={!preview || submitting} onClick={handleSubmit}>
            {submitting ? "Submitting..." : "Submit for evaluation"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
