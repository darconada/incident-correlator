import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Clock, Plus, Loader2, RefreshCw, Check } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Header } from '@/components/Header'
import { JobCard } from '@/components/JobCard'
import { startExtraction, getJobs, deleteJob } from '@/api/client'
import type { JobInfo } from '@/types'

interface DashboardPageProps {
  username?: string
  onLogout: () => void
}

const WINDOW_OPTIONS = [
  { value: '24h', label: '24 horas' },
  { value: '48h', label: '48 horas' },
  { value: '72h', label: '72 horas' },
  { value: '7d', label: '7 dias' },
  { value: 'custom', label: 'Personalizado...' },
]

export function DashboardPage({ username, onLogout }: DashboardPageProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [incInput, setIncInput] = useState('')
  const [window, setWindow] = useState('48h')
  const [customHours, setCustomHours] = useState('')
  const [showCustomInput, setShowCustomInput] = useState(false)
  const [pollingJobIds, setPollingJobIds] = useState<string[]>([])
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [showRefreshSuccess, setShowRefreshSuccess] = useState(false)

  // Fetch jobs list
  const { data: jobsData, refetch: refetchJobs } = useQuery({
    queryKey: ['jobs'],
    queryFn: getJobs,
    refetchInterval: pollingJobIds.length > 0 ? 3000 : false,
  })

  // Poll individual running jobs
  useEffect(() => {
    if (!jobsData?.jobs) return

    const runningJobs = jobsData.jobs
      .filter((j) => j.status === 'running' || j.status === 'pending')
      .map((j) => j.job_id)

    setPollingJobIds(runningJobs)
  }, [jobsData?.jobs])

  // Start extraction mutation
  const extractMutation = useMutation({
    mutationFn: startExtraction,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      setIncInput('')
    },
  })

  // Delete job mutation
  const deleteMutation = useMutation({
    mutationFn: deleteJob,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  const handleRefresh = async () => {
    setIsRefreshing(true)
    setShowRefreshSuccess(false)
    await refetchJobs()
    setIsRefreshing(false)
    setShowRefreshSuccess(true)
    setTimeout(() => setShowRefreshSuccess(false), 2000)
  }

  const handleWindowChange = (value: string) => {
    if (value === 'custom') {
      setShowCustomInput(true)
    } else {
      setShowCustomInput(false)
      setWindow(value)
    }
  }

  const getEffectiveWindow = () => {
    if (showCustomInput && customHours) {
      return `${customHours}h`
    }
    return window
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!incInput.trim()) return

    const inc = incInput.toUpperCase().trim()
    if (!inc.startsWith('INC-')) {
      return
    }

    extractMutation.mutate({ inc, window: getEffectiveWindow() })
  }

  const handleJobClick = (job: JobInfo) => {
    if (job.status === 'completed') {
      navigate(`/analysis/${job.job_id}`)
    }
  }

  const jobs = jobsData?.jobs || []
  const runningJobs = jobs.filter((j) => j.status === 'running' || j.status === 'pending')
  const completedJobs = jobs.filter((j) => j.status === 'completed')
  const failedJobs = jobs.filter((j) => j.status === 'failed')

  return (
    <div className="min-h-screen bg-background">
      <Header username={username} onLogout={onLogout} />

      <main className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto space-y-8">
          {/* New Analysis Card */}
          <Card className="border-primary/20 shadow-lg shadow-primary/5 animate-fade-in">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Plus className="w-5 h-5 text-primary" />
                Nuevo Análisis
              </CardTitle>
              <CardDescription>
                Introduce el ID del incidente y la ventana temporal para buscar
                TECCMs relacionados
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="md:col-span-2 space-y-2">
                    <Label htmlFor="inc">Incidente</Label>
                    <div className="relative">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                      <Input
                        id="inc"
                        type="text"
                        placeholder="INC-117346"
                        value={incInput}
                        onChange={(e) => setIncInput(e.target.value)}
                        className="pl-10 mono"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>Ventana temporal</Label>
                    {showCustomInput ? (
                      <div className="flex gap-2">
                        <div className="relative flex-1">
                          <Input
                            type="number"
                            min="1"
                            max="720"
                            placeholder="Horas"
                            value={customHours}
                            onChange={(e) => setCustomHours(e.target.value)}
                            className="pr-8"
                          />
                          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
                            h
                          </span>
                        </div>
                        <Button
                          type="button"
                          variant="outline"
                          size="icon"
                          onClick={() => {
                            setShowCustomInput(false)
                            setCustomHours('')
                          }}
                          title="Volver a opciones predefinidas"
                        >
                          <Clock className="w-4 h-4" />
                        </Button>
                      </div>
                    ) : (
                      <Select value={window} onValueChange={handleWindowChange}>
                        <SelectTrigger>
                          <Clock className="w-4 h-4 mr-2 text-muted-foreground" />
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {WINDOW_OPTIONS.map((opt) => (
                            <SelectItem key={opt.value} value={opt.value}>
                              {opt.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  </div>
                </div>

                <div className="flex justify-end">
                  <Button
                    type="submit"
                    disabled={
                      extractMutation.isPending ||
                      !incInput.trim() ||
                      !incInput.toUpperCase().startsWith('INC-') ||
                      (showCustomInput && (!customHours || parseInt(customHours) < 1))
                    }
                  >
                    {extractMutation.isPending ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Iniciando...
                      </>
                    ) : (
                      <>
                        <Search className="w-4 h-4" />
                        Analizar
                      </>
                    )}
                  </Button>
                </div>

                {extractMutation.isError && (
                  <p className="text-sm text-destructive">
                    {extractMutation.error instanceof Error
                      ? extractMutation.error.message
                      : 'Error al iniciar análisis'}
                  </p>
                )}
              </form>
            </CardContent>
          </Card>

          {/* Running Jobs */}
          {runningJobs.length > 0 && (
            <section
              className="space-y-4 animate-fade-in"
              style={{ animationDelay: '100ms' }}
            >
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-primary" />
                  En curso
                </h2>
              </div>
              <div className="space-y-3">
                {runningJobs.map((job) => (
                  <JobCard key={job.job_id} job={job} />
                ))}
              </div>
            </section>
          )}

          {/* Recent Analysis */}
          <section
            className="space-y-4 animate-fade-in"
            style={{ animationDelay: '200ms' }}
          >
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Analisis Recientes</h2>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleRefresh}
                disabled={isRefreshing}
                className={showRefreshSuccess ? "text-green-500" : "text-muted-foreground"}
              >
                {isRefreshing ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                    Actualizando...
                  </>
                ) : showRefreshSuccess ? (
                  <>
                    <Check className="w-4 h-4 mr-1" />
                    Actualizado
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4 mr-1" />
                    Actualizar
                  </>
                )}
              </Button>
            </div>

            {completedJobs.length === 0 && failedJobs.length === 0 ? (
              <Card className="border-dashed">
                <CardContent className="py-12 text-center text-muted-foreground">
                  <Search className="w-10 h-10 mx-auto mb-4 opacity-40" />
                  <p>No hay análisis completados</p>
                  <p className="text-sm mt-1">
                    Inicia un nuevo análisis para ver los resultados aquí
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-3">
                {completedJobs.map((job, i) => (
                  <JobCard
                    key={job.job_id}
                    job={job}
                    onClick={() => handleJobClick(job)}
                    onDelete={() => deleteMutation.mutate(job.job_id)}
                    className="animate-fade-in"
                    style={{ animationDelay: `${i * 50}ms` }}
                  />
                ))}
                {failedJobs.map((job, i) => (
                  <JobCard
                    key={job.job_id}
                    job={job}
                    onDelete={() => deleteMutation.mutate(job.job_id)}
                    className="animate-fade-in"
                    style={{
                      animationDelay: `${(completedJobs.length + i) * 50}ms`,
                    }}
                  />
                ))}
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  )
}
