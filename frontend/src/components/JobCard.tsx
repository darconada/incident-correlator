import { AlertCircle, CheckCircle2, Clock, Loader2, Trash2 } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { cn, formatRelativeTime } from '@/lib/utils'
import type { JobInfo } from '@/types'

interface JobCardProps {
  job: JobInfo
  onClick?: () => void
  onDelete?: () => void
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
}

export function JobCard({ job, onClick, onDelete, className, style }: JobCardProps) {
  const config = STATUS_CONFIG[job.status]
  const StatusIcon = config.icon
  const isClickable = job.status === 'completed'

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
              <div className="flex items-center gap-2">
                <span className="mono font-semibold text-foreground">
                  {job.inc}
                </span>
                <span className="text-xs text-muted-foreground bg-secondary px-1.5 py-0.5 rounded">
                  {job.window}
                </span>
              </div>
              <p className="text-sm text-muted-foreground truncate">
                {config.label}
                {job.total_teccms !== null && job.total_teccms !== undefined && (
                  <span className="ml-1">
                    · {job.total_teccms} TECCMs
                  </span>
                )}
              </p>
            </div>
          </div>

          {/* Right: Time and actions */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className="text-xs text-muted-foreground">
              {formatRelativeTime(job.created_at)}
            </span>
            {onDelete && job.status !== 'running' && (
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
