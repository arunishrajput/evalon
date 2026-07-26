"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { CriteriaBuilder, emptyCriterion } from "@/components/hackathon/CriteriaBuilder";
import { hackathonApi, ApiError } from "@/lib/api";
import type { CriterionInput } from "@/lib/types";

const DEFAULT_CRITERIA: CriterionInput[] = [
  { name: "Code Quality", description: "Structure, maintainability, and best practices", weight: 0.4, agent_id: "code_quality", display_order: 0 },
  { name: "Innovation", description: "Novelty and creativity of the approach", weight: 0.35, agent_id: "innovation", display_order: 1 },
  { name: "Understanding", description: "Depth of architectural understanding shown", weight: 0.25, agent_id: "repo_understanding", display_order: 2 },
];

export default function NewHackathonPage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [maxSubmissions, setMaxSubmissions] = useState(100);
  const [maxRepoSizeMb, setMaxRepoSizeMb] = useState(50);
  const [showRankingsEarly, setShowRankingsEarly] = useState(false);
  const [criteria, setCriteria] = useState<CriterionInput[]>(DEFAULT_CRITERIA);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const weightSum = criteria.reduce((sum, c) => sum + (Number(c.weight) || 0), 0);
  const weightsValid = Math.abs(weightSum - 1) < 0.001;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!title.trim()) {
      setError("Title is required.");
      return;
    }
    if (criteria.length > 0 && !weightsValid) {
      setError("Criteria weights must sum to exactly 1.00 before you can save.");
      return;
    }
    setSubmitting(true);
    try {
      const hackathon = await hackathonApi.create({
        title,
        description: description || undefined,
        max_submissions: maxSubmissions,
        settings: {
          max_repo_size_mb: maxRepoSizeMb,
          show_rankings_before_finalization: showRankingsEarly,
        },
      });
      if (criteria.length > 0) {
        await hackathonApi.replaceCriteria(
          hackathon.id,
          criteria.map((c) => ({ ...c, name: c.name.trim() || "Untitled criterion" }))
        );
      }
      router.push(`/admin/hackathons/${hackathon.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to create hackathon. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-2xl font-bold text-white">New hackathon</h1>
      <form onSubmit={handleSubmit} className="space-y-6">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea id="description" value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="maxSubmissions">Max submissions</Label>
                <Input
                  id="maxSubmissions"
                  type="number"
                  min={1}
                  value={maxSubmissions}
                  onChange={(e) => setMaxSubmissions(parseInt(e.target.value, 10) || 1)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="maxRepoSize">Max repo size (MB)</Label>
                <Input
                  id="maxRepoSize"
                  type="number"
                  min={1}
                  value={maxRepoSizeMb}
                  onChange={(e) => setMaxRepoSizeMb(parseInt(e.target.value, 10) || 1)}
                />
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-300">
              <input
                type="checkbox"
                checked={showRankingsEarly}
                onChange={(e) => setShowRankingsEarly(e.target.checked)}
                className="h-4 w-4 rounded border-white/20 bg-card-elevated accent-accent"
              />
              Show rankings to participants before finalization
            </label>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Judging criteria</CardTitle>
          </CardHeader>
          <CardContent>
            <CriteriaBuilder criteria={criteria} onChange={setCriteria} />
          </CardContent>
        </Card>

        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting ? "Creating..." : "Create hackathon"}
        </Button>
      </form>
    </div>
  );
}
