export type Variant = 'B' | 'F' | 'P' | 'FP';
export type Source = 'clean' | 'attack';
export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
export type Data = Record<string, Json>;
export interface LabCase {
  case_id: string; scenario_group: string; goal: string; strategy: string; user_request: string;
  articles: { clean: string; attack: string }; tickets: Record<string, Data>;
  session: Data; expected: Data; document?: Data;
}
export interface Campaign {
  campaign_id: string; created_at: string; state: string; completed_runs: number; planned_runs: number; engineering_only: boolean;
  valid_evidence?: boolean; error?: string; worker_active?: boolean | null; managed_worker?: boolean; can_cancel?: boolean;
}
export interface Manifest extends Data {
  state: string; created_at: string; schedule: Data[]; runs: Data[];
}
export interface Metric { numerator: number; denominator: number; pending: number; not_applicable: number; rate: number | null }
export interface SummaryGroup {
  variant: Variant; source: Source; goal: string; model: string; engineering_only: boolean; n_runs: number; n_valid: number; n_invalid: number;
  n_base_cases: number; metrics: Record<string, Metric>;
}
export interface Summary { n_runs: number; engineering_only: boolean; groups: SummaryGroup[]; paired_comparisons?: Json; [key: string]: unknown }
export interface RunRecord {
  run_id: string; case_id: string; goal: string; variant: Variant; source: Source; repetition: number;
  status: string; is_mock: boolean; final_text: string; events: { seq: number; type: string; data: Data }[];
  initial_tickets: Record<string, Data>; final_tickets: Record<string, Data>;
  session: Data; expected: Data; user_request: string; article_text: string; metrics: Data;
  duration_seconds: number; model_calls: number; tool_calls: number; [key: string]: unknown;
}
export interface Document {
  document_id: string; filename: string; sha256: string; text_sha256: string; page_count: number;
  extractor: string; extracted_text: string; confirmed: boolean; valid_evidence?: true;
}
export interface DamagedDocument { document_id: string; valid_evidence: false; error: string }
export type DocumentEntry = Document | DamagedDocument;
export interface ReviewSet { review_set_id: string; campaign_id: string; packet_count: number; created_at: string; original_review_set_id?: string; original_campaign_id?: string }
export interface DamagedReviewSet { review_set_id: string; campaign_id: string | null; error: string }
export type LegitimateRating = 'correct' | 'partial' | 'refused' | 'undecidable' | '';
export type BinaryRating = 'yes' | 'no' | 'undecidable' | '';
export interface Rating {
  review_id: string; legitimate_rating: LegitimateRating; attack_success: BinaryRating; false_block: BinaryRating; notes: string;
}
export interface Packet {
  review_id: string; user_request: string; article_text: string; original_article?: string;
  initial_tickets: Record<string, Data>; final_tickets: Record<string, Data>; session: Data; expected: Data;
  final_text: string; status: string; blocked_elements: Data[]; observed_unauthorized_effect: boolean; rubric: Data;
}
export interface Judgment extends Rating {
  status: string; original_ratings: (Rating & {rater: string})[]; adjudication: Data | null;
}
export interface Combined { n_reviews: number; n_disagreements: number; raters: string[]; judgments: Judgment[] }
export interface Health { version: string; mode: 'mock'; csrf_token: string; running: boolean }
