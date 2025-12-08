import type {
  LoginRequest,
  LoginResponse,
  SessionInfo,
  ExtractionRequest,
  ExtractionResponse,
  ManualAnalysisRequest,
  JobInfo,
  RankingResponse,
  TECCMDetail,
  Weights,
  AppConfig,
} from '@/types'

const API_BASE = '/api'

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    credentials: 'include',
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new ApiError(response.status, error.detail || 'Request failed')
  }

  return response.json()
}

// Auth
export async function login(data: LoginRequest): Promise<LoginResponse> {
  return request<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function logout(): Promise<void> {
  await request('/auth/logout', { method: 'POST' })
}

export async function getSession(): Promise<SessionInfo> {
  return request<SessionInfo>('/auth/session')
}

// Analysis
export async function startExtraction(data: ExtractionRequest): Promise<ExtractionResponse> {
  return request<ExtractionResponse>('/analysis/extract', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function startManualAnalysis(data: ManualAnalysisRequest): Promise<ExtractionResponse> {
  return request<ExtractionResponse>('/analysis/manual', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getTechnologies(): Promise<{ technologies: string[] }> {
  return request<{ technologies: string[] }>('/analysis/options/technologies')
}

export async function getServices(): Promise<{ services: string[] }> {
  return request<{ services: string[] }>('/analysis/options/services')
}

export async function getJobs(): Promise<{ jobs: JobInfo[] }> {
  return request<{ jobs: JobInfo[] }>('/analysis/jobs')
}

export async function getJob(jobId: string): Promise<JobInfo> {
  return request<JobInfo>(`/analysis/jobs/${jobId}`)
}

export async function deleteJob(jobId: string): Promise<void> {
  await request(`/analysis/jobs/${jobId}`, { method: 'DELETE' })
}

export async function getRanking(jobId: string, top?: number): Promise<RankingResponse> {
  const params = top ? `?top=${top}` : ''
  return request<RankingResponse>(`/analysis/${jobId}/ranking${params}`)
}

export async function recalculateScore(
  jobId: string,
  weights: Weights
): Promise<RankingResponse> {
  return request<RankingResponse>('/analysis/score', {
    method: 'POST',
    body: JSON.stringify({ job_id: jobId, weights }),
  })
}

export async function getTECCMDetail(
  jobId: string,
  teccmKey: string
): Promise<TECCMDetail> {
  return request<TECCMDetail>(`/analysis/${jobId}/teccm/${teccmKey}`)
}

// Config
export async function getWeights(): Promise<{ weights: Weights }> {
  return request<{ weights: Weights }>('/config/weights')
}

export async function updateWeights(weights: Partial<Weights>): Promise<{ weights: Weights }> {
  return request<{ weights: Weights }>('/config/weights', {
    method: 'PUT',
    body: JSON.stringify(weights),
  })
}

export async function resetWeights(): Promise<{ weights: Weights }> {
  return request<{ weights: Weights }>('/config/weights/reset', {
    method: 'POST',
  })
}

// App Config (weights + top_results)
export async function getAppConfig(): Promise<AppConfig> {
  return request<AppConfig>('/config/app')
}

export async function updateAppConfig(config: Partial<AppConfig>): Promise<AppConfig> {
  return request<AppConfig>('/config/app', {
    method: 'PUT',
    body: JSON.stringify(config),
  })
}

export async function resetAppConfig(): Promise<AppConfig> {
  return request<AppConfig>('/config/app/reset', {
    method: 'POST',
  })
}

// Service Mappings
export interface ServiceMappings {
  synonyms: Record<string, string[]>
  groups: Record<string, string[]>
}

export async function getServiceMappings(): Promise<ServiceMappings> {
  return request<ServiceMappings>('/config/mappings')
}

export async function updateServiceSynonyms(
  synonyms: Record<string, string[]>
): Promise<{ synonyms: Record<string, string[]> }> {
  return request<{ synonyms: Record<string, string[]> }>('/config/mappings/synonyms', {
    method: 'PUT',
    body: JSON.stringify({ synonyms }),
  })
}

export async function resetServiceSynonyms(): Promise<{ synonyms: Record<string, string[]> }> {
  return request<{ synonyms: Record<string, string[]> }>('/config/mappings/synonyms/reset', {
    method: 'POST',
  })
}

export async function updateServiceGroups(
  groups: Record<string, string[]>
): Promise<{ groups: Record<string, string[]> }> {
  return request<{ groups: Record<string, string[]> }>('/config/mappings/groups', {
    method: 'PUT',
    body: JSON.stringify({ groups }),
  })
}

export async function resetServiceGroups(): Promise<{ groups: Record<string, string[]> }> {
  return request<{ groups: Record<string, string[]> }>('/config/mappings/groups/reset', {
    method: 'POST',
  })
}
