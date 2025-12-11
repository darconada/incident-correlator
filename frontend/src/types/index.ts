// API Types

export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  success: boolean
  message: string
  token?: string
}

export interface SessionInfo {
  authenticated: boolean
  username?: string
  jira_url: string
}

export interface SearchOptions {
  window_before: string
  window_after: string
  include_active: boolean
  include_no_end: boolean
  include_external_maintenance: boolean
  max_results: number
  extra_jql: string
  project: string
}

export interface ExtractionRequest {
  inc: string
  window: string
  search_options?: SearchOptions
}

export interface ManualAnalysisRequest {
  name?: string
  impact_time: string
  services: string[]
  hosts: string[]
  technologies: string[]
  team?: string
  brands?: string[]
  search_options?: SearchOptions
}

export interface ExtractionResponse {
  job_id: string
  message: string
}

export type JobType = 'standard' | 'custom' | 'manual'

export interface JobInfo {
  job_id: string
  inc: string
  window: string
  status: JobStatus
  progress: number
  total_teccms?: number
  error?: string
  created_at: string
  completed_at?: string
  job_type?: JobType
  username?: string
  search_summary?: string
}

export interface Weights {
  time: number
  service: number
  infra: number
  org: number
}

export interface Penalties {
  no_live_intervals: number
  no_hosts: number
  no_services: number
  generic_change: number
  long_duration_week: number
  long_duration_month: number
  long_duration_quarter: number
}

export interface Bonuses {
  proximity_exact: number
  proximity_1h: number
  proximity_2h: number
  proximity_4h: number
}

export interface Thresholds {
  time_decay_hours: number
  min_score_to_show: number
}

export interface AppConfig {
  weights: Weights
  penalties: Penalties
  bonuses: Bonuses
  thresholds: Thresholds
  top_results: number
}

export interface SubScores {
  time: number
  service: number
  infra: number
  org: number
}

export interface SubScoreDetail {
  score: number
  reason: string
  matches: string[]
}

export interface TECCMRankingItem {
  rank: number
  issue_key: string
  summary: string
  final_score: number
  sub_scores: SubScores
  details: {
    time_reason: string
    service_matches: string[]
    infra_matches: string[]
    org_matches: string[]
    penalties: string[]
  }
  assignee?: string
  team?: string
  planned_start?: string
  planned_end?: string
  live_intervals: Array<{ start: string; end: string }>
  resolution?: string
  services: string[]
  hosts: string[]
  technologies: string[]
}

export interface IncidentInfo {
  issue_key: string
  summary: string
  first_impact_time?: string
  created_at?: string
  services: string[]
  hosts: string[]
  technologies: string[]
}

export interface RankingResponse {
  incident: IncidentInfo
  analysis: {
    teccm_analyzed: number
    teccm_in_ranking: number
    scored_at: string
    weights: Weights
  }
  ranking: TECCMRankingItem[]
}

export interface TECCMDetail {
  issue_key: string
  summary: string
  final_score: number
  sub_scores: {
    time: SubScoreDetail
    service: SubScoreDetail
    infra: SubScoreDetail
    org: SubScoreDetail
  }
  penalties: string[]
  teccm_info: {
    assignee?: string
    team?: string
    planned_start?: string
    planned_end?: string
    live_intervals: Array<{ start: string; end: string }>
    resolution?: string
    services: string[]
    hosts: string[]
    technologies: string[]
  }
  jira_url: string
}
