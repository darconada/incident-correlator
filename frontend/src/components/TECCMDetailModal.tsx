import { ExternalLink, Clock, Layers, Server, Users, Check, X, AlertTriangle } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ScoreBar } from '@/components/ScoreBar'
import { cn, formatDate } from '@/lib/utils'
import type { TECCMDetail } from '@/types'

interface TECCMDetailModalProps {
  detail: TECCMDetail | null
  open: boolean
  onClose: () => void
}

export function TECCMDetailModal({ detail, open, onClose }: TECCMDetailModalProps) {
  if (!detail) return null

  const subScores = [
    {
      key: 'time',
      label: 'Time Score',
      icon: Clock,
      color: 'text-cyan-400',
      bgColor: 'bg-cyan-500/10',
    },
    {
      key: 'service',
      label: 'Service Score',
      icon: Layers,
      color: 'text-violet-400',
      bgColor: 'bg-violet-500/10',
    },
    {
      key: 'infra',
      label: 'Infra Score',
      icon: Server,
      color: 'text-amber-400',
      bgColor: 'bg-amber-500/10',
    },
    {
      key: 'org',
      label: 'Org Score',
      icon: Users,
      color: 'text-emerald-400',
      bgColor: 'bg-emerald-500/10',
    },
  ] as const

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-start justify-between gap-4">
            <div>
              <DialogTitle className="flex items-center gap-2 text-xl">
                <span className="mono">{detail.issue_key}</span>
                <a
                  href={detail.jira_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:text-primary/80"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              </DialogTitle>
              <p className="text-sm text-muted-foreground mt-1">
                {detail.summary}
              </p>
            </div>
            <div
              className={cn(
                'flex-shrink-0 px-4 py-2 rounded-xl mono text-2xl font-bold',
                detail.final_score >= 70 && 'bg-emerald-500/20 text-emerald-400',
                detail.final_score >= 40 && detail.final_score < 70 && 'bg-amber-500/20 text-amber-400',
                detail.final_score >= 20 && detail.final_score < 40 && 'bg-orange-500/20 text-orange-400',
                detail.final_score < 20 && 'bg-red-500/20 text-red-400'
              )}
            >
              {detail.final_score.toFixed(1)}
            </div>
          </div>
        </DialogHeader>

        {/* Sub-scores detail */}
        <div className="space-y-4 mt-6">
          <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
            Sub-scores
          </h4>

          <div className="space-y-3">
            {subScores.map(({ key, label, icon: Icon, color, bgColor }) => {
              const scoreData = detail.sub_scores[key]
              return (
                <div
                  key={key}
                  className={cn(
                    'p-4 rounded-lg border border-border/50',
                    bgColor
                  )}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Icon className={cn('w-4 h-4', color)} />
                      <span className="font-medium">{label}</span>
                    </div>
                    <span className={cn('mono font-bold', color)}>
                      {scoreData.score.toFixed(1)}
                    </span>
                  </div>

                  <ScoreBar score={scoreData.score} size="sm" className="mb-2" />

                  <p className="text-sm text-muted-foreground">
                    {scoreData.reason}
                  </p>

                  {scoreData.matches.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {scoreData.matches.map((match, i) => (
                        <span
                          key={i}
                          className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-background/50 border border-border/50"
                        >
                          <Check className="w-3 h-3 text-emerald-400" />
                          {match}
                        </span>
                      ))}
                    </div>
                  )}

                  {scoreData.matches.length === 0 && scoreData.score === 0 && (
                    <div className="flex items-center gap-1 mt-2 text-xs text-muted-foreground">
                      <X className="w-3 h-3 text-red-400" />
                      Sin coincidencias
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Penalties */}
        {detail.penalties.length > 0 && (
          <div className="mt-6">
            <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wide mb-3">
              Penalizaciones
            </h4>
            <div className="flex flex-wrap gap-2">
              {detail.penalties.map((penalty, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20"
                >
                  <AlertTriangle className="w-3 h-3" />
                  {penalty}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* TECCM Info */}
        <div className="mt-6 pt-6 border-t border-border">
          <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wide mb-3">
            Información del Cambio
          </h4>

          <div className="grid grid-cols-2 gap-4 text-sm">
            {detail.teccm_info.assignee && (
              <div>
                <span className="text-muted-foreground">Assignee:</span>{' '}
                <span className="font-medium">{detail.teccm_info.assignee}</span>
              </div>
            )}
            {detail.teccm_info.team && (
              <div>
                <span className="text-muted-foreground">Team:</span>{' '}
                <span className="font-medium">{detail.teccm_info.team}</span>
              </div>
            )}
            {detail.teccm_info.resolution && (
              <div>
                <span className="text-muted-foreground">Resolution:</span>{' '}
                <span
                  className={cn(
                    'font-medium',
                    detail.teccm_info.resolution.toLowerCase().includes('roll') &&
                      'text-amber-400'
                  )}
                >
                  {detail.teccm_info.resolution}
                </span>
              </div>
            )}
          </div>

          {/* Live intervals */}
          {detail.teccm_info.live_intervals.length > 0 && (
            <div className="mt-4">
              <span className="text-sm text-muted-foreground">Live Intervals:</span>
              <div className="mt-1 space-y-1">
                {detail.teccm_info.live_intervals.map((interval, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm mono">
                    <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                    {formatDate(interval.start)} — {formatDate(interval.end)}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Planned times */}
          {(detail.teccm_info.planned_start || detail.teccm_info.planned_end) && (
            <div className="mt-4 text-sm">
              <span className="text-muted-foreground">Planned:</span>{' '}
              <span className="mono">
                {formatDate(detail.teccm_info.planned_start)} —{' '}
                {formatDate(detail.teccm_info.planned_end)}
              </span>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
