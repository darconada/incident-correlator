import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  ExternalLink,
  AlertTriangle,
  Clock,
  Layers,
  Server,
  Settings,
  ChevronDown,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Header } from '@/components/Header'
import { TECCMCard } from '@/components/TECCMCard'
import { WeightsSlider } from '@/components/WeightsSlider'
import { TECCMDetailModal } from '@/components/TECCMDetailModal'
import { getRanking, recalculateScore, getTECCMDetail, getAppConfig } from '@/api/client'
import { formatDate, getJiraUrl } from '@/lib/utils'
import type { Weights, TECCMDetail } from '@/types'

interface RankingPageProps {
  username?: string
  onLogout: () => void
}

export function RankingPage({ username, onLogout }: RankingPageProps) {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [showWeights, setShowWeights] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const [selectedTeccm, setSelectedTeccm] = useState<string | null>(null)
  const [detailData, setDetailData] = useState<TECCMDetail | null>(null)

  // Fetch ranking
  const {
    data: rankingData,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['ranking', jobId],
    queryFn: () => getRanking(jobId!, showAll ? 200 : 20),
    enabled: !!jobId,
  })

  // Fetch app config (weights + top_results)
  const { data: appConfig } = useQuery({
    queryKey: ['appConfig'],
    queryFn: getAppConfig,
  })

  // Fetch TECCM detail
  const detailQuery = useQuery({
    queryKey: ['teccm-detail', jobId, selectedTeccm],
    queryFn: () => getTECCMDetail(jobId!, selectedTeccm!),
    enabled: !!jobId && !!selectedTeccm,
  })

  // Update detail data when query completes
  if (detailQuery.data && detailQuery.data !== detailData) {
    setDetailData(detailQuery.data)
  }

  // Recalculate mutation
  const recalculateMutation = useMutation({
    mutationFn: (weights: Weights) => recalculateScore(jobId!, weights),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ranking', jobId] })
    },
  })

  const handleWeightsChange = (weights: Weights) => {
    // Just update local state, actual recalculation happens on button click
  }

  const handleRecalculate = () => {
    if (appConfig?.weights) {
      recalculateMutation.mutate(appConfig.weights)
    }
  }

  const topResults = appConfig?.top_results || 20

  const handleTeccmClick = (issueKey: string) => {
    setSelectedTeccm(issueKey)
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <Header username={username} onLogout={onLogout} />
        <main className="container mx-auto px-4 py-8">
          <div className="max-w-5xl mx-auto">
            <div className="space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-32 rounded-xl shimmer" />
              ))}
            </div>
          </div>
        </main>
      </div>
    )
  }

  if (isError || !rankingData) {
    return (
      <div className="min-h-screen bg-background">
        <Header username={username} onLogout={onLogout} />
        <main className="container mx-auto px-4 py-8">
          <div className="max-w-5xl mx-auto text-center py-16">
            <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-destructive" />
            <h2 className="text-xl font-semibold mb-2">Error loading ranking</h2>
            <p className="text-muted-foreground mb-4">
              Could not load analysis data
            </p>
            <Button variant="outline" onClick={() => navigate('/')}>
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Dashboard
            </Button>
          </div>
        </main>
      </div>
    )
  }

  const { incident, analysis, ranking } = rankingData
  const displayedRanking = showAll ? ranking : ranking.slice(0, topResults)

  return (
    <div className="min-h-screen bg-background">
      <Header username={username} onLogout={onLogout} />

      <main className="container mx-auto px-4 py-8">
        <div className="max-w-5xl mx-auto space-y-6">
          {/* Back button and incident header */}
          <div className="flex items-start justify-between gap-4 animate-fade-in">
            <div className="flex items-start gap-4">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => navigate('/')}
                className="mt-1"
              >
                <ArrowLeft className="w-5 h-5" />
              </Button>

              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-2xl font-bold mono">{incident.issue_key}</h1>
                  <a
                    href={getJiraUrl(incident.issue_key)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:text-primary/80"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </div>
                <p className="text-muted-foreground mt-1 line-clamp-2">
                  {incident.summary}
                </p>

                {/* Incident metadata */}
                <div className="flex flex-wrap items-center gap-4 mt-3 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <Clock className="w-4 h-4" />
                    First impact:{' '}
                    <span className="mono">
                      {formatDate(incident.first_impact_time || incident.created_at)}
                    </span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Layers className="w-4 h-4" />
                    {analysis.teccm_analyzed} TECCMs
                  </span>
                </div>

                {/* Incident tags */}
                {(incident.services.length > 0 || incident.technologies.length > 0) && (
                  <div className="flex flex-wrap gap-1.5 mt-3">
                    {incident.services.map((s) => (
                      <span
                        key={s}
                        className="px-2 py-0.5 text-xs rounded-full bg-primary/10 text-primary border border-primary/20"
                      >
                        {s}
                      </span>
                    ))}
                    {incident.technologies.map((t) => (
                      <span
                        key={t}
                        className="px-2 py-0.5 text-xs rounded-full bg-accent/10 text-accent border border-accent/20 mono"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Settings button */}
            <Button
              variant={showWeights ? 'secondary' : 'outline'}
              size="sm"
              onClick={() => setShowWeights(!showWeights)}
            >
              <Settings className="w-4 h-4 mr-1" />
              Pesos
            </Button>
          </div>

          {/* Weights slider */}
          {showWeights && appConfig && (
            <div className="animate-fade-in">
              <WeightsSlider
                weights={appConfig.weights}
                onChange={handleWeightsChange}
                onRecalculate={handleRecalculate}
                isLoading={recalculateMutation.isPending}
              />
            </div>
          )}

          {/* Ranking list */}
          <section className="space-y-4">
            <h2 className="text-lg font-semibold">Ranking</h2>

            {ranking.length === 0 ? (
              <Card className="border-dashed">
                <CardContent className="py-12 text-center text-muted-foreground">
                  <Server className="w-10 h-10 mx-auto mb-4 opacity-40" />
                  <p>No TECCMs found matching the criteria</p>
                </CardContent>
              </Card>
            ) : (
              <>
                <div className="space-y-3">
                  {displayedRanking.map((item, i) => (
                    <TECCMCard
                      key={item.issue_key}
                      item={item}
                      onClick={() => handleTeccmClick(item.issue_key)}
                      className="animate-fade-in"
                      style={{ animationDelay: `${i * 30}ms` }}
                    />
                  ))}
                </div>

                {ranking.length > topResults && !showAll && (
                  <div className="text-center pt-4">
                    <Button
                      variant="outline"
                      onClick={() => setShowAll(true)}
                    >
                      <ChevronDown className="w-4 h-4 mr-1" />
                      Mostrar {ranking.length - topResults} más
                    </Button>
                  </div>
                )}
              </>
            )}
          </section>
        </div>
      </main>

      {/* Detail Modal */}
      <TECCMDetailModal
        detail={detailData}
        open={!!selectedTeccm}
        onClose={() => {
          setSelectedTeccm(null)
          setDetailData(null)
        }}
      />
    </div>
  )
}
