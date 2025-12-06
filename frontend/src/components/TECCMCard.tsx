import { ExternalLink, Clock, Server, Users, Layers } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { ScoreBar } from '@/components/ScoreBar'
import { cn, getRankMedal, getJiraUrl } from '@/lib/utils'
import type { TECCMRankingItem } from '@/types'

interface TECCMCardProps {
  item: TECCMRankingItem
  onClick?: () => void
  className?: string
  style?: React.CSSProperties
}

export function TECCMCard({ item, onClick, className, style }: TECCMCardProps) {
  const isTopThree = item.rank <= 3

  return (
    <Card
      className={cn(
        'group relative cursor-pointer overflow-hidden transition-all duration-300',
        'hover:border-primary/50 hover-lift',
        isTopThree && 'border-primary/30',
        className
      )}
      style={style}
      onClick={onClick}
    >
      {/* Gradient overlay for top items */}
      {isTopThree && (
        <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent pointer-events-none" />
      )}

      <div className="relative p-5">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex items-center gap-3">
            <span className="text-2xl" role="img" aria-label={`Rank ${item.rank}`}>
              {getRankMedal(item.rank)}
            </span>
            <div>
              <a
                href={getJiraUrl(item.issue_key)}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="inline-flex items-center gap-1.5 text-primary hover:text-primary/80 transition-colors"
              >
                <span className="mono font-semibold">{item.issue_key}</span>
                <ExternalLink className="w-3.5 h-3.5 opacity-50" />
              </a>
              <p className="text-sm text-muted-foreground line-clamp-1 mt-0.5">
                {item.summary}
              </p>
            </div>
          </div>

          {/* Score badge */}
          <div
            className={cn(
              'flex-shrink-0 px-3 py-1.5 rounded-lg mono text-lg font-bold',
              item.final_score >= 70 && 'bg-emerald-500/20 text-emerald-400',
              item.final_score >= 40 && item.final_score < 70 && 'bg-amber-500/20 text-amber-400',
              item.final_score >= 20 && item.final_score < 40 && 'bg-orange-500/20 text-orange-400',
              item.final_score < 20 && 'bg-red-500/20 text-red-400'
            )}
          >
            {item.final_score.toFixed(1)}
          </div>
        </div>

        {/* Main score bar */}
        <ScoreBar score={item.final_score} size="md" className="mb-4" />

        {/* Sub-scores grid */}
        <div className="grid grid-cols-4 gap-3">
          <SubScoreItem
            icon={Clock}
            label="Time"
            score={item.sub_scores.time}
          />
          <SubScoreItem
            icon={Layers}
            label="Service"
            score={item.sub_scores.service}
          />
          <SubScoreItem
            icon={Server}
            label="Infra"
            score={item.sub_scores.infra}
          />
          <SubScoreItem
            icon={Users}
            label="Org"
            score={item.sub_scores.org}
          />
        </div>

        {/* Matches preview */}
        {(item.details.service_matches.length > 0 ||
          item.details.infra_matches.length > 0) && (
          <div className="mt-4 pt-4 border-t border-border/50">
            <div className="flex flex-wrap gap-1.5">
              {item.details.service_matches.slice(0, 3).map((match) => (
                <span
                  key={match}
                  className="px-2 py-0.5 text-xs rounded-full bg-primary/10 text-primary border border-primary/20"
                >
                  {match}
                </span>
              ))}
              {item.details.infra_matches.slice(0, 3).map((match) => (
                <span
                  key={match}
                  className="px-2 py-0.5 text-xs rounded-full bg-accent/10 text-accent border border-accent/20 mono"
                >
                  {match}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}

interface SubScoreItemProps {
  icon: React.ElementType
  label: string
  score: number
}

function SubScoreItem({ icon: Icon, label, score }: SubScoreItemProps) {
  return (
    <div className="text-center">
      <div className="flex items-center justify-center gap-1 mb-1">
        <Icon className="w-3.5 h-3.5 text-muted-foreground" />
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <div className="relative h-1 bg-secondary rounded-full overflow-hidden mb-1">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500',
            score >= 70 && 'bg-emerald-500',
            score >= 40 && score < 70 && 'bg-amber-500',
            score >= 20 && score < 40 && 'bg-orange-500',
            score < 20 && 'bg-red-500'
          )}
          style={{ width: `${score}%` }}
        />
      </div>
      <span
        className={cn(
          'mono text-xs font-medium',
          score >= 70 && 'text-emerald-400',
          score >= 40 && score < 70 && 'text-amber-400',
          score >= 20 && score < 40 && 'text-orange-400',
          score < 20 && 'text-red-400'
        )}
      >
        {score.toFixed(0)}
      </span>
    </div>
  )
}
