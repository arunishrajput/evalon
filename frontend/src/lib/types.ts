// Mirrors backend/app/schemas/*.py exactly — one type per Pydantic response
// model. Decimal fields serialize as JSON strings from FastAPI, so numeric
// fields that are `Decimal` server-side are typed `number | string` here.

export type UserRole = "admin" | "participant";

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export type HackathonStatus = "draft" | "active" | "evaluating" | "finalized";

export interface HackathonSettings {
  allow_private_repos: boolean;
  max_repo_size_mb: number;
  evaluation_mode: string;
  show_rankings_before_finalization: boolean;
}

export interface Hackathon {
  id: string;
  title: string;
  description: string | null;
  admin_id: string;
  status: HackathonStatus;
  start_date: string | null;
  end_date: string | null;
  max_submissions: number;
  settings: HackathonSettings;
  created_at: string;
  updated_at: string | null;
}

export interface Criterion {
  id: string;
  hackathon_id: string;
  name: string;
  description: string | null;
  weight: number | string;
  agent_id: string | null;
  display_order: number;
  created_at: string;
}

export interface CriterionInput {
  name: string;
  description?: string | null;
  weight: number;
  agent_id?: string | null;
  display_order?: number;
}

export interface Participant {
  id: string;
  hackathon_id: string;
  user_id: string;
  joined_at: string;
}

export type SubmissionStatus =
  | "pending"
  | "cloning"
  | "analyzing"
  | "evaluating"
  | "completed"
  | "failed";

export interface Submission {
  id: string;
  hackathon_id: string;
  user_id: string;
  repo_url: string;
  repo_name: string | null;
  repo_description: string | null;
  tech_stack: string[];
  status: SubmissionStatus;
  error_message: string | null;
  degraded: boolean;
  degraded_reason: string | null;
  submitted_at: string;
  clone_completed_at: string | null;
  analysis_completed_at: string | null;
  evaluation_completed_at: string | null;
}

export type EvaluationStatus = "pending" | "running" | "completed" | "failed" | "degraded";

export interface EvidenceItem {
  description: string;
  source: string;
  impact: string;
  [key: string]: unknown;
}

export interface AgentResultDetail {
  agent_id: string;
  score_raw: number;
  confidence: number;
  evidence: EvidenceItem[];
  top_evidence: string[];
  strengths: string[];
  weaknesses: string[];
  reasoning: string | null;
  abstained: boolean;
  abstain_reason: string | null;
  fallback_used: boolean;
}

export interface CriterionScoreEntry {
  criterion: string;
  score: number;
  weight: number;
  agent_id?: string | null;
}

export interface Recommendation {
  priority: "high" | "medium" | "low";
  recommendation: string;
  rationale: string;
}

export interface ComparativeReport {
  agent_id: string;
  total_submissions_in_pool: number;
  this_submission_score: number;
  pool_average_score: number;
  pool_median_score: number;
  percentile: number;
  percentile_label: string;
  rank_in_pool: number;
  score_vs_average: string;
  shared_tech_stacks: { tech: string; count: number }[];
  unique_tech_stacks: { tech: string }[];
  criterion_comparisons: Record<string, unknown>[];
  summary: string;
  sufficient_data: boolean;
  data_note: string;
}

export interface EvaluationReport {
  summary: string;
  degraded: boolean;
  degraded_explanation: string | null;
  overall_assessment: string;
  tech_stack: string[];
  project_type: string;
  scores: {
    overall: number;
    by_criterion: CriterionScoreEntry[];
  };
  strengths: string[];
  weaknesses: string[];
  recommendations: Recommendation[];
  architecture_notes: string;
  agent_results: AgentResultDetail[];
  comparative: ComparativeReport | null;
  generated_at: string;
  model_versions: Record<string, string>;
}

export interface Evaluation {
  id: string;
  submission_id: string;
  hackathon_id: string;
  status: EvaluationStatus;
  final_score: number | string | null;
  report: EvaluationReport | null;
  started_at: string | null;
  completed_at: string | null;
  model_versions: Record<string, string> | null;
  agents_completed: string[];
  agents_abstained: string[];
  created_at: string;
}

export interface AgentResultRow {
  id: string;
  agent_id: string;
  criterion_id: string | null;
  score_raw: number | string | null;
  confidence: number | string | null;
  evidence: EvidenceItem[];
  strengths: string[];
  weaknesses: string[];
  top_evidence: string[];
  reasoning: string | null;
  abstained: boolean;
  abstain_reason: string | null;
  fallback_used: boolean;
  processing_time_ms: number | null;
  created_at: string;
}

export interface RankingEntry {
  submission_id: string;
  rank: number;
  percentile: number | string | null;
  normalized_score: number | string | null;
  final_score: number | string | null;
  finalized: boolean;
  repo_name: string | null;
  participant_name: string | null;
  is_you: boolean;
}

export interface DashboardStats {
  total_submissions: number;
  evaluations_completed: number;
  evaluations_in_progress: number;
  evaluations_queued: number;
  evaluations_failed: number;
  score_distribution: Record<string, number>;
  tech_stack_frequency: Record<string, number>;
  avg_score: number | string | null;
  // spec's stats_service.py top5_preview shape: {rank, repo_name, score} only
  // — no submission_id (the "leaderboard preview" is deliberately anonymous
  // pre-finalization, matching the spec Section 10 dashboard mock).
  top5_preview: { rank: number; repo_name: string | null; score: number }[];
}

export interface CriterionScore {
  criterion: string;
  score: number;
  weight: number;
  top_evidence: string[];
}

export interface ComparisonSubmission {
  submission_id: string;
  repo_name: string | null;
  participant_name: string;
  final_score: number | string | null;
  scores_by_criterion: CriterionScore[];
  strengths: string[];
  weaknesses: string[];
  tech_stack: string[];
  rank: number | null;
  percentile: number | null;
}

export interface ComparisonResponse {
  submissions: ComparisonSubmission[];
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  created_at: string;
}

export interface ChatSession {
  id: string;
  submission_id: string;
  created_at: string;
  last_message_at: string | null;
  mentor_available: boolean;
  unavailable_reason: string | null;
  degraded: boolean;
}

export interface ModelStatus {
  ollama_reachable: boolean;
  inference_model: string;
  inference_model_loaded: boolean;
  embedding_model: string;
  embedding_model_loaded: boolean;
  lock_held_by: string | null;
  queue_depth: number;
  estimated_wait_seconds: number;
}

export interface AdminHackathonSummary {
  id: string;
  title: string;
  status: string;
  total_submissions: number;
  evaluations_completed: number;
  avg_score: number | string | null;
}

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface ApiErrorBody {
  detail: string;
  error_code: string;
}

// --- SSE event payloads (spec Section 6) ---

export type ProgressStage =
  | "cloning"
  | "analyzing"
  | "agent_repo_understanding"
  | "agent_code_quality"
  | "agent_innovation"
  | "agent_comparative"
  | "aggregating"
  | "generating_report"
  | "embedding"
  | "model_loading"
  | "model_waiting";

export interface ProgressEvent {
  event: "progress";
  data: { stage: ProgressStage; message: string; progress_pct: number; timestamp: string; degraded: boolean };
}

export interface AgentCompleteEvent {
  event: "agent_complete";
  data: { agent_id: string; score: number; abstained: boolean; timestamp: string };
}

export interface CompletedEvent {
  event: "completed";
  data: { evaluation_id: string; final_score: number; degraded: boolean; timestamp: string };
}

export interface DegradedEvent {
  event: "degraded";
  data: { message: string; affected_agents: string[]; timestamp: string };
}

export interface ErrorEvent {
  event: "error";
  data: { message: string; stage: string; recoverable: boolean; timestamp: string };
}

export type SubmissionSSEEvent =
  | ProgressEvent
  | AgentCompleteEvent
  | CompletedEvent
  | DegradedEvent
  | ErrorEvent;

export interface DashboardSSEEvent {
  event: "stats_update";
  data: DashboardStats;
}

export interface ChatTokenEvent {
  token: string;
  done: boolean;
  message_id?: string;
  error?: string;
}
