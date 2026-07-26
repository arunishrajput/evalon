"use client";

import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { CriterionInput } from "@/lib/types";

const AGENT_OPTIONS = [
  { value: "repo_understanding", label: "Repository Understanding agent" },
  { value: "code_quality", label: "Code Quality agent" },
  { value: "innovation", label: "Innovation agent" },
  { value: "none", label: "None (static analysis only)" },
];

export function emptyCriterion(order: number): CriterionInput {
  return { name: "", description: "", weight: 0, agent_id: null, display_order: order };
}

interface CriteriaBuilderProps {
  criteria: CriterionInput[];
  onChange: (criteria: CriterionInput[]) => void;
}

export function CriteriaBuilder({ criteria, onChange }: CriteriaBuilderProps) {
  const totalWeight = criteria.reduce((sum, c) => sum + (Number(c.weight) || 0), 0);
  const isValid = Math.abs(totalWeight - 1) < 0.001;

  const update = (index: number, patch: Partial<CriterionInput>) => {
    const next = [...criteria];
    next[index] = { ...next[index], ...patch };
    onChange(next);
  };

  const remove = (index: number) => {
    onChange(criteria.filter((_, i) => i !== index).map((c, i) => ({ ...c, display_order: i })));
  };

  const add = () => {
    onChange([...criteria, emptyCriterion(criteria.length)]);
  };

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-white/10 bg-card-elevated p-4">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="text-gray-300">Weight total</span>
          <span className={isValid ? "font-medium text-emerald-400" : "font-medium text-degraded"}>
            {totalWeight.toFixed(2)} / 1.00
          </span>
        </div>
        <Progress
          value={Math.min(totalWeight, 1) * 100}
          indicatorClassName={isValid ? "bg-emerald-500" : "bg-degraded"}
        />
        {!isValid && <p className="mt-2 text-xs text-degraded">Criteria weights must sum to exactly 1.00.</p>}
      </div>

      <div className="space-y-3">
        {criteria.map((criterion, index) => (
          <div key={index} className="rounded-lg border border-white/10 bg-card p-4">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div className="flex-1 space-y-2">
                <Label>Name</Label>
                <Input
                  value={criterion.name}
                  onChange={(e) => update(index, { name: e.target.value })}
                  placeholder="e.g. Code Quality"
                />
              </div>
              <Button type="button" variant="ghost" size="icon" className="mt-6" onClick={() => remove(index)}>
                <Trash2 className="h-4 w-4 text-error" />
              </Button>
            </div>
            <div className="mb-3 space-y-2">
              <Label>Description</Label>
              <Input
                value={criterion.description || ""}
                onChange={(e) => update(index, { description: e.target.value })}
                placeholder="What this criterion measures"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label>Weight ({(criterion.weight * 100).toFixed(0)}%)</Label>
                <Input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={criterion.weight}
                  onChange={(e) => update(index, { weight: parseFloat(e.target.value) || 0 })}
                />
              </div>
              <div className="space-y-2">
                <Label>Agent mapping</Label>
                <Select
                  value={criterion.agent_id || "none"}
                  onValueChange={(value) => update(index, { agent_id: value === "none" ? null : value })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {AGENT_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        ))}
      </div>

      <Button type="button" variant="outline" onClick={add} className="w-full">
        <Plus className="mr-1 h-4 w-4" />
        Add criterion
      </Button>
    </div>
  );
}
