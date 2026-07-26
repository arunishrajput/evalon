import { formatScore } from "@/lib/utils";
import type { EvaluationReport } from "@/lib/types";

interface PrintableReportProps {
  report: EvaluationReport;
  repoName: string;
  participantName: string;
  finalScore: number | string | null;
  submissionId: string;
}

const AGENT_LABELS: Record<string, string> = {
  repo_understanding: "Repository Understanding",
  code_quality: "Code Quality",
  innovation: "Innovation",
};

/** Hidden in normal view; rendered only under @media print (globals.css),
 * as a single flat document with every section already expanded — the
 * interactive tabbed ReportViewer is hidden for print instead. */
export function PrintableReport({ report, repoName, participantName, finalScore, submissionId }: PrintableReportProps) {
  return (
    <div className="hidden print:block" id="printable-report">
      <header className="mb-8 flex items-center justify-between border-b-2 border-black pb-4">
        <div>
          <h1 className="text-2xl font-bold">
            EVAL<span>ON</span>
          </h1>
          <p className="text-sm">Evaluation Report</p>
        </div>
        <div className="text-right text-sm">
          <p className="font-semibold">{repoName}</p>
          <p>{participantName}</p>
          <p>{new Date(report.generated_at).toLocaleString()}</p>
        </div>
      </header>

      <section className="mb-6 text-center">
        <div className="text-6xl font-bold">{formatScore(finalScore)}</div>
        <p className="text-sm uppercase tracking-wide">Overall score / 100</p>
        {report.degraded && (
          <p className="mt-2 text-sm italic">{report.degraded_explanation}</p>
        )}
      </section>

      <section className="mb-6">
        <h2 className="mb-2 text-lg font-bold">Summary</h2>
        <p className="text-sm">{report.summary}</p>
        <p className="mt-2 whitespace-pre-wrap text-sm">{report.overall_assessment}</p>
      </section>

      <section className="mb-6 break-inside-avoid">
        <h2 className="mb-2 text-lg font-bold">Scores by criterion</h2>
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-black text-left">
              <th className="py-1">Criterion</th>
              <th className="py-1">Score</th>
              <th className="py-1">Weight</th>
            </tr>
          </thead>
          <tbody>
            {report.scores.by_criterion.map((c) => (
              <tr key={c.criterion} className="border-b border-gray-300">
                <td className="py-1">{c.criterion}</td>
                <td className="py-1">{formatScore(c.score)}</td>
                <td className="py-1">{(c.weight * 100).toFixed(0)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="mb-6 grid grid-cols-2 gap-6">
        <div>
          <h2 className="mb-2 text-lg font-bold">Strengths</h2>
          <ul className="list-inside list-disc text-sm">
            {report.strengths.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
        <div>
          <h2 className="mb-2 text-lg font-bold">Weaknesses</h2>
          <ul className="list-inside list-disc text-sm">
            {report.weaknesses.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      </section>

      {report.agent_results.map((agent) => (
        <section key={agent.agent_id} className="mb-6 break-before-page">
          <h2 className="mb-2 text-lg font-bold">{AGENT_LABELS[agent.agent_id] || agent.agent_id}</h2>
          <p className="mb-2 text-sm font-semibold">Score: {formatScore(agent.score_raw)} / 100</p>
          {agent.abstained && (
            <p className="mb-2 text-sm italic">Static analysis only — {agent.abstain_reason}</p>
          )}
          {agent.reasoning && <p className="mb-2 whitespace-pre-wrap text-sm">{agent.reasoning}</p>}
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <h3 className="font-semibold">Strengths</h3>
              <ul className="list-inside list-disc">
                {agent.strengths.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="font-semibold">Weaknesses</h3>
              <ul className="list-inside list-disc">
                {agent.weaknesses.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      ))}

      <section className="mb-6 break-inside-avoid">
        <h2 className="mb-2 text-lg font-bold">Recommendations</h2>
        <ul className="space-y-1 text-sm">
          {report.recommendations.map((rec, i) => (
            <li key={i}>
              <strong className="uppercase">[{rec.priority}]</strong> {rec.recommendation} — {rec.rationale}
            </li>
          ))}
        </ul>
      </section>

      <footer className="mt-10 border-t border-black pt-3 text-xs text-gray-600">
        <p>EVALON — AI-Powered Hackathon Evaluation · Submission {submissionId}</p>
      </footer>
    </div>
  );
}
