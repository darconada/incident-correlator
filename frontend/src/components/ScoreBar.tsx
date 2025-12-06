import { cn } from '@/lib/utils'

interface ScoreBarProps {
  score: number
  maxScore?: number
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
  animated?: boolean
  className?: string
}

function getScoreGradient(score: number): string {
  if (score >= 70) {
    return 'from-emerald-500 to-emerald-400'
  }
  if (score >= 40) {
    return 'from-amber-500 to-yellow-400'
  }
  if (score >= 20) {
    return 'from-orange-500 to-orange-400'
  }
  return 'from-red-500 to-red-400'
}

function getScoreGlow(score: number): string {
  if (score >= 70) {
    return 'shadow-emerald-500/30'
  }
  if (score >= 40) {
    return 'shadow-amber-500/30'
  }
  if (score >= 20) {
    return 'shadow-orange-500/30'
  }
  return 'shadow-red-500/30'
}

export function ScoreBar({
  score,
  maxScore = 100,
  size = 'md',
  showLabel = false,
  animated = true,
  className,
}: ScoreBarProps) {
  const percentage = Math.min((score / maxScore) * 100, 100)

  const heightClass = {
    sm: 'h-1.5',
    md: 'h-2.5',
    lg: 'h-4',
  }[size]

  return (
    <div className={cn('flex items-center gap-3', className)}>
      <div
        className={cn(
          'relative flex-1 overflow-hidden rounded-full bg-secondary/50',
          heightClass
        )}
      >
        {/* Track pattern */}
        <div className="absolute inset-0 opacity-20">
          <div
            className="h-full w-full"
            style={{
              backgroundImage: `repeating-linear-gradient(
                90deg,
                transparent,
                transparent 8px,
                rgba(255,255,255,0.03) 8px,
                rgba(255,255,255,0.03) 16px
              )`,
            }}
          />
        </div>

        {/* Score fill */}
        <div
          className={cn(
            'h-full rounded-full bg-gradient-to-r shadow-lg transition-all duration-500',
            getScoreGradient(score),
            getScoreGlow(score),
            animated && 'score-bar-animated'
          )}
          style={{ width: `${percentage}%` }}
        >
          {/* Shine effect */}
          <div className="absolute inset-0 bg-gradient-to-b from-white/20 to-transparent" />
        </div>
      </div>

      {showLabel && (
        <span
          className={cn(
            'mono text-sm font-semibold tabular-nums',
            score >= 70 && 'text-emerald-400',
            score >= 40 && score < 70 && 'text-amber-400',
            score >= 20 && score < 40 && 'text-orange-400',
            score < 20 && 'text-red-400'
          )}
        >
          {score.toFixed(1)}
        </span>
      )}
    </div>
  )
}
