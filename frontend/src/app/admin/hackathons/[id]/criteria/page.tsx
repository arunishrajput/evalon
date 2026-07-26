"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { CriteriaBuilder } from "@/components/hackathon/CriteriaBuilder";
import { hackathonApi, ApiError } from "@/lib/api";
import type { CriterionInput } from "@/lib/types";

export default function CriteriaPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const { data: existing, isLoading } = useSWR(["criteria", id], () => hackathonApi.listCriteria(id));
  const [criteria, setCriteria] = useState<CriterionInput[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (existing) {
      setCriteria(
        existing.map((c) => ({
          name: c.name,
          description: c.description,
          weight: Number(c.weight),
          agent_id: c.agent_id,
          display_order: c.display_order,
        }))
      );
    }
  }, [existing]);

  const weightSum = criteria.reduce((sum, c) => sum + (Number(c.weight) || 0), 0);
  const weightsValid = criteria.length > 0 && Math.abs(weightSum - 1) < 0.001;

  const save = async () => {
    setError(null);
    setSaved(false);
    if (!weightsValid) {
      setError("Criteria weights must sum to exactly 1.00.");
      return;
    }
    setSaving(true);
    try {
      await hackathonApi.replaceCriteria(id, criteria);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to save criteria.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-2xl font-bold text-white">Judging criteria</h1>
      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {saved && (
        <Alert variant="success" className="mb-4">
          <AlertDescription>Criteria saved.</AlertDescription>
        </Alert>
      )}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Criteria & weights</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-gray-500">Loading...</p>
          ) : (
            <CriteriaBuilder criteria={criteria} onChange={setCriteria} />
          )}
        </CardContent>
      </Card>
      <Button className="mt-6 w-full" onClick={save} disabled={saving}>
        {saving ? "Saving..." : "Save criteria"}
      </Button>
    </div>
  );
}
