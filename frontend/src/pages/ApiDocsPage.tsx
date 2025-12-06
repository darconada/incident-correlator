import { useState } from 'react'
import { Header } from '@/components/Header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Copy, Check, ExternalLink, Code2 } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ApiDocsPageProps {
  username?: string
  onLogout?: () => void
}

interface Endpoint {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE'
  path: string
  description: string
  auth: boolean
  body?: string
  response?: string
}

const API_BASE = window.location.origin + '/api'

const endpoints: Record<string, Endpoint[]> = {
  'Authentication': [
    {
      method: 'POST',
      path: '/api/auth/login',
      description: 'Authenticate with Jira credentials. Returns a session cookie.',
      auth: false,
      body: `{
  "username": "your_jira_user",
  "password": "your_jira_password"
}`,
      response: `{
  "success": true,
  "message": "Connected to Jira",
  "token": "session-uuid"
}`
    },
    {
      method: 'POST',
      path: '/api/auth/logout',
      description: 'End current session and clear cookies.',
      auth: true,
      response: `{ "success": true, "message": "Logged out" }`
    },
    {
      method: 'GET',
      path: '/api/auth/session',
      description: 'Get current session info.',
      auth: false,
      response: `{
  "authenticated": true,
  "username": "user",
  "jira_url": "https://jira.example.com"
}`
    }
  ],
  'Analysis': [
    {
      method: 'POST',
      path: '/api/analysis/extract',
      description: 'Start extraction job for an incident. Returns job_id for polling.',
      auth: true,
      body: `{
  "inc": "INC-123456",
  "window": "48h",
  "search_options": {
    "window_before": "48h",
    "window_after": "2h",
    "include_active": true,
    "include_no_end": true,
    "include_external_maintenance": false,
    "max_results": 500,
    "extra_jql": null,
    "project": "TECCM"
  }
}`,
      response: `{
  "job_id": "uuid",
  "message": "Extraction started for INC-123456"
}`
    },
    {
      method: 'POST',
      path: '/api/analysis/manual',
      description: 'Start manual analysis without an incident ticket.',
      auth: true,
      body: `{
  "name": "Analysis name",
  "impact_time": "2024-01-15T10:30:00",
  "services": ["Service A", "Service B"],
  "hosts": ["host1.example.com"],
  "technologies": ["Linux", "MySQL"],
  "team": "Team Name",
  "search_options": { ... }
}`,
      response: `{
  "job_id": "uuid",
  "message": "Manual analysis started"
}`
    },
    {
      method: 'GET',
      path: '/api/analysis/jobs',
      description: 'List recent analysis jobs.',
      auth: true,
      response: `{
  "jobs": [
    {
      "id": "uuid",
      "inc": "INC-123456",
      "status": "completed",
      "progress": 100,
      "created_at": "2024-01-15T10:30:00",
      ...
    }
  ]
}`
    },
    {
      method: 'GET',
      path: '/api/analysis/jobs/{job_id}',
      description: 'Get job status and progress.',
      auth: true,
      response: `{
  "id": "uuid",
  "inc": "INC-123456",
  "status": "running",
  "progress": 45,
  "teccm_count": 12,
  ...
}`
    },
    {
      method: 'DELETE',
      path: '/api/analysis/jobs/{job_id}',
      description: 'Delete a job and its data.',
      auth: true,
      response: `{ "success": true, "message": "Job deleted" }`
    },
    {
      method: 'GET',
      path: '/api/analysis/{job_id}/ranking',
      description: 'Get TECCM ranking for a completed job.',
      auth: true,
      response: `{
  "incident": { "issue_key": "INC-123456", ... },
  "analysis": { "total_teccms": 25, ... },
  "ranking": [
    {
      "rank": 1,
      "issue_key": "TECCM-789",
      "final_score": 0.85,
      "sub_scores": { ... },
      ...
    }
  ]
}`
    },
    {
      method: 'POST',
      path: '/api/analysis/score',
      description: 'Recalculate ranking with custom weights.',
      auth: true,
      body: `{
  "job_id": "uuid",
  "weights": {
    "time": 0.35,
    "service": 0.30,
    "infra": 0.20,
    "org": 0.15
  }
}`,
      response: `{ "incident": {...}, "ranking": [...] }`
    },
    {
      method: 'GET',
      path: '/api/analysis/{job_id}/teccm/{teccm_key}',
      description: 'Get detailed info about a specific TECCM.',
      auth: true,
      response: `{
  "issue_key": "TECCM-789",
  "summary": "...",
  "final_score": 0.85,
  "jira_url": "https://jira.example.com/browse/TECCM-789",
  ...
}`
    },
    {
      method: 'GET',
      path: '/api/analysis/options/technologies',
      description: 'Get list of available technologies for manual analysis.',
      auth: true,
      response: `{ "technologies": ["Linux", "Windows", "MySQL", ...] }`
    },
    {
      method: 'GET',
      path: '/api/analysis/options/services',
      description: 'Get list of available service names for manual analysis.',
      auth: true,
      response: `{ "services": ["Service A", "Service B", ...] }`
    }
  ],
  'Configuration': [
    {
      method: 'GET',
      path: '/api/config/weights',
      description: 'Get current scoring weights.',
      auth: true,
      response: `{
  "weights": {
    "time": 0.35,
    "service": 0.30,
    "infra": 0.20,
    "org": 0.15
  }
}`
    },
    {
      method: 'PUT',
      path: '/api/config/weights',
      description: 'Update scoring weights.',
      auth: true,
      body: `{
  "time": 0.40,
  "service": 0.25,
  "infra": 0.20,
  "org": 0.15
}`,
      response: `{ "weights": { ... } }`
    },
    {
      method: 'POST',
      path: '/api/config/weights/reset',
      description: 'Reset weights to default values.',
      auth: true,
      response: `{ "weights": { ... } }`
    },
    {
      method: 'GET',
      path: '/api/config/app',
      description: 'Get all app configuration (weights, penalties, bonuses, thresholds).',
      auth: true,
      response: `{
  "weights": { ... },
  "penalties": { ... },
  "bonuses": { ... },
  "thresholds": { ... },
  "top_results": 20
}`
    },
    {
      method: 'PUT',
      path: '/api/config/app',
      description: 'Update app configuration.',
      auth: true,
      body: `{
  "weights": { ... },
  "penalties": { ... },
  "bonuses": { ... },
  "thresholds": { ... },
  "top_results": 30
}`,
      response: `{ ... }`
    },
    {
      method: 'POST',
      path: '/api/config/app/reset',
      description: 'Reset all configuration to defaults.',
      auth: true,
      response: `{ ... }`
    }
  ],
  'Health': [
    {
      method: 'GET',
      path: '/health',
      description: 'Health check endpoint. Does not require authentication.',
      auth: false,
      response: `{ "status": "healthy" }`
    }
  ]
}

const methodColors: Record<string, string> = {
  GET: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  POST: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  PUT: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  DELETE: 'bg-red-500/20 text-red-400 border-red-500/30'
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      className="h-6 w-6 absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity"
      onClick={handleCopy}
    >
      {copied ? (
        <Check className="h-3 w-3 text-emerald-400" />
      ) : (
        <Copy className="h-3 w-3" />
      )}
    </Button>
  )
}

function CodeBlock({ code }: { code: string }) {
  return (
    <div className="relative group">
      <pre className="bg-secondary/50 rounded-lg p-3 text-xs overflow-x-auto border border-border/50">
        <code className="text-muted-foreground">{code}</code>
      </pre>
      <CopyButton text={code} />
    </div>
  )
}

function EndpointCard({ endpoint }: { endpoint: Endpoint }) {
  const [expanded, setExpanded] = useState(false)

  const curlCommand = `curl -X ${endpoint.method} "${window.location.origin}${endpoint.path}"${
    endpoint.auth ? ' \\\n  -H "Cookie: session_id=YOUR_SESSION"' : ''
  }${
    endpoint.body ? ` \\\n  -H "Content-Type: application/json" \\\n  -d '${endpoint.body.replace(/\n/g, ' ').replace(/\s+/g, ' ')}'` : ''
  }`

  return (
    <div className="border border-border/50 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center gap-3 hover:bg-secondary/30 transition-colors text-left"
      >
        <span
          className={cn(
            'px-2 py-0.5 text-xs font-mono font-semibold rounded border',
            methodColors[endpoint.method]
          )}
        >
          {endpoint.method}
        </span>
        <code className="text-sm font-mono text-foreground">{endpoint.path}</code>
        {endpoint.auth && (
          <span className="text-xs text-muted-foreground bg-secondary px-2 py-0.5 rounded">
            Auth required
          </span>
        )}
        <span className="ml-auto text-xs text-muted-foreground">
          {expanded ? '−' : '+'}
        </span>
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-border/50 pt-3">
          <p className="text-sm text-muted-foreground">{endpoint.description}</p>

          {endpoint.body && (
            <div>
              <p className="text-xs font-medium text-foreground mb-1">Request Body</p>
              <CodeBlock code={endpoint.body} />
            </div>
          )}

          {endpoint.response && (
            <div>
              <p className="text-xs font-medium text-foreground mb-1">Response</p>
              <CodeBlock code={endpoint.response} />
            </div>
          )}

          <div>
            <p className="text-xs font-medium text-foreground mb-1">cURL Example</p>
            <CodeBlock code={curlCommand} />
          </div>
        </div>
      )}
    </div>
  )
}

export function ApiDocsPage({ username, onLogout }: ApiDocsPageProps) {
  return (
    <div className="min-h-screen bg-background">
      <Header username={username} onLogout={onLogout} />

      <main className="container mx-auto px-4 py-8 max-w-4xl">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-foreground mb-2">API Documentation</h1>
          <p className="text-muted-foreground">
            REST API for the INC-TECCM Correlation Analyzer. All endpoints under{' '}
            <code className="bg-secondary px-2 py-0.5 rounded text-sm">/api</code> require
            authentication via session cookie (except where noted).
          </p>
        </div>

        {/* Interactive Documentation */}
        <Card className="mb-6 border-primary/30 bg-primary/5">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <ExternalLink className="h-4 w-4 text-primary" />
              Interactive Documentation
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-4">
              For a fully interactive experience with live API testing, use the auto-generated OpenAPI documentation:
            </p>
            <div className="flex flex-wrap gap-3">
              <a
                href="/docs"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-lg hover:bg-emerald-500/30 transition-colors"
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
                </svg>
                Swagger UI
                <ExternalLink className="h-3 w-3" />
              </a>
              <a
                href="/redoc"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500/20 text-blue-400 border border-blue-500/30 rounded-lg hover:bg-blue-500/30 transition-colors"
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>
                </svg>
                ReDoc
                <ExternalLink className="h-3 w-3" />
              </a>
              <a
                href="/openapi.json"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 bg-secondary text-muted-foreground border border-border rounded-lg hover:bg-secondary/80 transition-colors"
              >
                <Code2 className="h-4 w-4" />
                OpenAPI JSON
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          </CardContent>
        </Card>

        {/* Base URL */}
        <Card className="mb-6">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Base URL</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <code className="bg-secondary px-3 py-2 rounded text-sm font-mono flex-1">
                {API_BASE}
              </code>
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigator.clipboard.writeText(API_BASE)}
              >
                <Copy className="h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Authentication info */}
        <Card className="mb-6 border-amber-500/30 bg-amber-500/5">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <span className="text-amber-400">Authentication</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground space-y-2">
            <p>
              This API uses session-based authentication. First, call{' '}
              <code className="bg-secondary px-1 rounded">POST /api/auth/login</code> with
              your Jira credentials. The server will set a <code className="bg-secondary px-1 rounded">session_id</code> cookie.
            </p>
            <p>
              Include this cookie in subsequent requests. Sessions expire after 24 hours.
            </p>
          </CardContent>
        </Card>

        {/* Endpoints by category */}
        <div className="space-y-6">
          {Object.entries(endpoints).map(([category, categoryEndpoints]) => (
            <Card key={category}>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">{category}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {categoryEndpoints.map((endpoint, idx) => (
                  <EndpointCard key={idx} endpoint={endpoint} />
                ))}
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Footer */}
        <div className="mt-8 text-center text-sm text-muted-foreground">
          <p>
            You can also import the{' '}
            <a
              href="/openapi.json"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              OpenAPI spec
            </a>{' '}
            into{' '}
            <a
              href="https://www.postman.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline inline-flex items-center gap-1"
            >
              Postman <ExternalLink className="h-3 w-3" />
            </a>{' '}
            or{' '}
            <a
              href="https://insomnia.rest/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline inline-flex items-center gap-1"
            >
              Insomnia <ExternalLink className="h-3 w-3" />
            </a>
          </p>
        </div>
      </main>
    </div>
  )
}
