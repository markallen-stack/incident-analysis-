export interface IncidentAnalysis {
  analysis_id: string;
  status: "answer" | "refuse" | "request_more_data";
  confidence: number;
  root_cause: string;
  evidence: Evidence;
  timeline: string;
  recommended_actions: string[];
  alternative_hypotheses: AlternativeHypothesis[];
  missing_evidence: string[] | null;
  processing_time_ms: number;
  agent_history: AgentHistory[];
}

export interface Evidence {
  log: string;
  historical: string;
}

export interface AlternativeHypothesis {
  hypothesis: string;
  why_less_likely: string;
}

export interface AgentHistory {
  agent: AgentName;
  status?: "complete";
  evidence_count?: number;
  events?: number;
  count?: number;
  confidence?: number;
  decision?: "answer" | "insufficient_evidence" | "refusal";
}

export type AgentName =
  | "planner"
  | "log_retriever"
  | "rag_retriever"
  | "timeline"
  | "hypothesis"
  | "verifier"
  | "decision_gate";
