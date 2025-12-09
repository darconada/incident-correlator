import { AlertCircle, CheckCircle2, Clock, Loader2, Trash2, Settings2, User, FileEdit, XCircle, X } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { cn, formatRelativeTime } from '@/lib/utils'
import type { JobInfo } from '@/types'

const JOB_TYPE_CONFIG = {
  standard: {
    label: null,  // No badge for standard
    icon: null,
    className: '',
  },
  custom: {
    label: 'Personalizado',
    icon: Settings2,
    className: 'bg-violet-500/20 text-violet-400',
  },
  manual: {
    label: 'Manual',
    icon: FileEdit,
    className: 'bg-amber-500/20 text-amber-400',
  },
}

interface JobCardProps {
  job: JobInfo
  onClick?: () => void
  onDelete?: () => void
  onCancel?: () => void
  isCancelling?: boolean
  className?: string
  style?: React.CSSProperties
}

const STATUS_CONFIG = {
  pending: {
    icon: Clock,
    label: 'Pendiente',
    color: 'text-muted-foreground',
    bgColor: 'bg-muted/50',
    animate: false,
  },
  running: {
    icon: Loader2,
    label: 'En curso',
    color: 'text-primary',
    bgColor: 'bg-primary/10',
    animate: true,
  },
  completed: {
    icon: CheckCircle2,
    label: 'Completado',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    animate: false,
  },
  failed: {
    icon: AlertCircle,
    label: 'Error',
    color: 'text-red-400',
    bgColor: 'bg-red-500/10',
    animate: false,
  },
  cancelled: {
    icon: XCircle,
    label: 'Cancelado',
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/10',
    animate: false,
  },
}

export function JobCard({ job, onClick, onDelete, onCancel, isCancelling, className, style }: JobCardProps) {
  const config = STATUS_CONFIG[job.status]
  const StatusIcon = config.icon
  const isClickable = job.status === 'completed'
  const isCancellable = job.status === 'running' || job.status === 'pending'
  const jobTypeConfig = JOB_TYPE_CONFIG[job.job_type || 'standard']
  const JobTypeIcon = jobTypeConfig.icon

  return (
    <Card
      className={cn(
        'group relative overflow-hidden transition-all duration-200',
        isClickable && 'cursor-pointer hover:border-primary/50 hover-lift',
        className
      )}
      style={style}
      onClick={isClickable ? onClick : undefined}
    >
      <div className="p-4">
        <div className="flex items-center justify-between gap-4">
          {/* Left: Status and INC */}
          <div className="flex items-center gap-3 min-w-0">
            <div className={cn('p-2 rounded-lg', config.bgColor)}>
              <StatusIcon
                className={cn(
                  'w-4 h-4',
                  config.color,
                  config.animate && 'animate-spin'
                )}
              />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="mono font-semibold text-foreground">
                  {job.inc}
                </span>
                <span className="text-xs text-muted-foreground bg-secondary px-1.5 py-0.5 rounded">
                  {job.window}
                </span>
                {jobTypeConfig.label && (
                  <span className={cn('text-xs px-1.5 py-0.5 rounded flex items-center gap-1', jobTypeConfig.className)}>
                    {JobTypeIcon && <JobTypeIcon className="w-3 h-3" />}
                    {jobTypeConfig.label}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <span className="truncate">
                  {config.label}
                  {job.total_teccms !== null && job.total_teccms !== undefined && (
                    <span className="ml-1">
                      · {job.total_teccms} TECCMs
                    </span>
                  )}
                </span>
                {job.username && (
                  <span className="flex items-center gap-1 text-xs opacity-70">
                    <User className="w-3 h-3" />
                    {job.username}
                  </span>
                )}
              </div>
              {job.search_summary && (
                <p className="text-xs text-muted-foreground/70 truncate mt-0.5">
                  {job.search_summary}
                </p>
              )}
            </div>
          </div>

          {/* Right: Time and actions */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className="text-xs text-muted-foreground">
              {formatRelativeTime(job.created_at)}
            </span>
            {onCancel && isCancellable && (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-red-500 hover:text-red-600 hover:bg-red-500/10"
                onClick={(e) => {
                  e.stopPropagation()
                  onCancel()
                }}
                disabled={isCancelling}
                title="Cancelar tarea"
              >
                {isCancelling ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <X className="w-5 h-5" />
                )}
              </Button>
            )}
            {onDelete && !isCancellable && (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                onClick={(e) => {
                  e.stopPropagation()
                  onDelete()
                }}
              >
                <Trash2 className="w-4 h-4 text-muted-foreground hover:text-destructive" />
              </Button>
            )}
          </div>
        </div>

        {/* Progress bar for running jobs */}
        {job.status === 'running' && (
          <div className="mt-3">
            <Progress value={job.progress} className="h-1.5" />
            <p className="text-xs text-muted-foreground mt-1">
              {job.progress}% completado
            </p>
          </div>
        )}

        {/* Error message */}
        {job.status === 'failed' && job.error && (
          <p className="mt-2 text-sm text-red-400/80 truncate">
            {job.error}
          </p>
        )}
      </div>
    </Card>
  )
}
