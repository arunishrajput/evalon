"use client";

import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ComparisonView } from "@/components/comparison/ComparisonView";
import { comparisonApi } from "@/lib/api";

export default function ComparePage({ params }: { params: { id: string } }) {
  const { id } = params;
  const searchParams = useSearchParams();
  const ids = (searchParams.get("ids") || "").split(",").filter(Boolean);

  const { data, isLoading, error } = useSWR(
    ids.length >= 2 ? ["compare", id, ids.join(",")] : null,
    () => comparisonApi.compare(id, ids)
  );

  const handlePrint = () => {
    document.body.classList.add("printing-report");
    window.print();
    document.body.classList.remove("printing-report");
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Side-by-side comparison</h1>
        <Button variant="outline" onClick={handlePrint} disabled={!data}>
          <Download className="mr-1 h-4 w-4" />
          Export comparison
        </Button>
      </div>

      {ids.length < 2 && (
        <p className="text-gray-500">
          Select at least 2 submissions from the Submissions page to compare them here.
        </p>
      )}
      {isLoading && <p className="text-gray-500">Loading...</p>}
      {error && <p className="text-gray-500">Unable to load comparison for the selected submissions.</p>}
      {data && <ComparisonView submissions={data.submissions} />}
    </div>
  );
}
