import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Clock, Plus, Loader2, RefreshCw, Check, Settings2 } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Header } from '@/components/Header'
import { JobCard } from '@/components/JobCard'
import { startExtraction, getJobs, deleteJob } from '@/api/client'
import type { JobInfo, SearchOptions } from '@/types'

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

const DEFAULT_SEARCH_OPTIONS: SearchOptions = {
  window_before: '48h',
  window_after: '2h',
  include_active: true,
  include_no_end: true,
  max_results: 500,
  extra_jql: '',
  project: 'TECCM',
}

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

  // Advanced search modal state
  const [showAdvancedModal, setShowAdvancedModal] = useState(false)
  const [advancedOptions, setAdvancedOptions] = useState<SearchOptions>(DEFAULT_SEARCH_OPTIONS)

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

  const handleAdvancedSubmit = () => {
    if (!incInput.trim()) return

    const inc = incInput.toUpperCase().trim()
    if (!inc.startsWith('INC-')) {
      return
    }

    extractMutation.mutate({
      inc,
      window: advancedOptions.window_before,
      search_options: advancedOptions,
    })
    setShowAdvancedModal(false)
  }

  const openAdvancedModal = () => {
    // Sync current window setting with advanced options
    setAdvancedOptions({
      ...advancedOptions,
      window_before: getEffectiveWindow(),
    })
    setShowAdvancedModal(true)
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

                <div className="flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={openAdvancedModal}
                    disabled={
                      extractMutation.isPending ||
                      !incInput.trim() ||
                      !incInput.toUpperCase().startsWith('INC-')
                    }
                  >
                    <Settings2 className="w-4 h-4" />
                    Avanzado
                  </Button>
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

      {/* Advanced Search Modal */}
      <Dialog open={showAdvancedModal} onOpenChange={setShowAdvancedModal}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Settings2 className="w-5 h-5" />
              Busqueda Avanzada
            </DialogTitle>
            <DialogDescription>
              Personaliza los parametros de busqueda de TECCMs para {incInput.toUpperCase() || 'el incidente'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 py-4">
            {/* Time Windows */}
            <div className="space-y-4">
              <h4 className="text-sm font-medium">Ventana Temporal</h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="window_before" className="text-xs text-muted-foreground">
                    Antes del INC
                  </Label>
                  <Select
                    value={advancedOptions.window_before}
                    onValueChange={(v) => setAdvancedOptions({ ...advancedOptions, window_before: v })}
                  >
                    <SelectTrigger id="window_before">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="12h">12 horas</SelectItem>
                      <SelectItem value="24h">24 horas</SelectItem>
                      <SelectItem value="48h">48 horas</SelectItem>
                      <SelectItem value="72h">72 horas</SelectItem>
                      <SelectItem value="7d">7 dias</SelectItem>
                      <SelectItem value="14d">14 dias</SelectItem>
                      <SelectItem value="30d">30 dias</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="window_after" className="text-xs text-muted-foreground">
                    Despues del INC
                  </Label>
                  <Select
                    value={advancedOptions.window_after}
                    onValueChange={(v) => setAdvancedOptions({ ...advancedOptions, window_after: v })}
                  >
                    <SelectTrigger id="window_after">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="0h">Sin margen</SelectItem>
                      <SelectItem value="1h">1 hora</SelectItem>
                      <SelectItem value="2h">2 horas</SelectItem>
                      <SelectItem value="4h">4 horas</SelectItem>
                      <SelectItem value="8h">8 horas</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>

            {/* Search Types */}
            <div className="space-y-4">
              <h4 className="text-sm font-medium">Tipos de Busqueda</h4>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <Label htmlFor="include_active" className="text-sm">TECCMs activos</Label>
                    <p className="text-xs text-muted-foreground">Cambios que estaban en curso al momento del INC</p>
                  </div>
                  <Switch
                    id="include_active"
                    checked={advancedOptions.include_active}
                    onCheckedChange={(v) => setAdvancedOptions({ ...advancedOptions, include_active: v })}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <Label htmlFor="include_no_end" className="text-sm">TECCMs sin cerrar</Label>
                    <p className="text-xs text-muted-foreground">Cambios que empezaron antes y siguen abiertos</p>
                  </div>
                  <Switch
                    id="include_no_end"
                    checked={advancedOptions.include_no_end}
                    onCheckedChange={(v) => setAdvancedOptions({ ...advancedOptions, include_no_end: v })}
                  />
                </div>
              </div>
            </div>

            {/* Limits */}
            <div className="space-y-4">
              <h4 className="text-sm font-medium">Limites</h4>
              <div className="space-y-2">
                <Label htmlFor="max_results" className="text-xs text-muted-foreground">
                  Maximo de resultados por busqueda
                </Label>
                <Select
                  value={String(advancedOptions.max_results)}
                  onValueChange={(v) => setAdvancedOptions({ ...advancedOptions, max_results: parseInt(v) })}
                >
                  <SelectTrigger id="max_results">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="100">100</SelectItem>
                    <SelectItem value="250">250</SelectItem>
                    <SelectItem value="500">500</SelectItem>
                    <SelectItem value="1000">1000</SelectItem>
                    <SelectItem value="2000">2000</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Extra JQL */}
            <div className="space-y-2">
              <Label htmlFor="extra_jql" className="text-sm font-medium">Filtro JQL adicional</Label>
              <Input
                id="extra_jql"
                placeholder='AND assignee = "usuario" AND summary ~ "deploy"'
                value={advancedOptions.extra_jql}
                onChange={(e) => setAdvancedOptions({ ...advancedOptions, extra_jql: e.target.value })}
                className="font-mono text-xs"
              />
              <p className="text-xs text-muted-foreground">
                Filtro JQL que se anadira a todas las busquedas. Debe empezar con AND.
              </p>
            </div>

            {/* Project */}
            <div className="space-y-2">
              <Label htmlFor="project" className="text-xs text-muted-foreground">
                Proyecto Jira
              </Label>
              <Input
                id="project"
                value={advancedOptions.project}
                onChange={(e) => setAdvancedOptions({ ...advancedOptions, project: e.target.value })}
                className="font-mono"
              />
            </div>

            {/* JQL Preview */}
            <div className="space-y-3 pt-4 border-t">
              <h4 className="text-sm font-medium flex items-center gap-2">
                <span className="text-muted-foreground">Vista previa de consultas JQL</span>
                <span className="text-xs bg-secondary px-2 py-0.5 rounded">
                  {1 + (advancedOptions.include_active ? 1 : 0) + (advancedOptions.include_no_end ? 1 : 0)} búsquedas
                </span>
              </h4>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {/* Query 1: Window */}
                <div className="space-y-1">
                  <p className="text-xs font-medium text-cyan-400">1. TECCMs en ventana temporal</p>
                  <code className="block p-2 rounded bg-secondary/50 text-xs font-mono break-all text-muted-foreground">
                    project = {advancedOptions.project} AND
                    "Start Date/Time" &gt;= "<span className="text-cyan-400">[INC - {advancedOptions.window_before}]</span>" AND
                    "Start Date/Time" &lt;= "<span className="text-cyan-400">[INC + {advancedOptions.window_after}]</span>"
                    {advancedOptions.extra_jql && <span className="text-amber-400"> {advancedOptions.extra_jql}</span>}
                  </code>
                </div>

                {/* Query 2: Active */}
                {advancedOptions.include_active && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-violet-400">2. TECCMs activos al momento del INC</p>
                    <code className="block p-2 rounded bg-secondary/50 text-xs font-mono break-all text-muted-foreground">
                      project = {advancedOptions.project} AND
                      "Start Date/Time" &lt;= "<span className="text-violet-400">[INC]</span>" AND
                      "End Date/Time" &gt;= "<span className="text-violet-400">[INC]</span>"
                      {advancedOptions.extra_jql && <span className="text-amber-400"> {advancedOptions.extra_jql}</span>}
                    </code>
                  </div>
                )}

                {/* Query 3: No end */}
                {advancedOptions.include_no_end && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-emerald-400">
                      {advancedOptions.include_active ? '3' : '2'}. TECCMs sin fecha de fin
                    </p>
                    <code className="block p-2 rounded bg-secondary/50 text-xs font-mono break-all text-muted-foreground">
                      project = {advancedOptions.project} AND
                      "Start Date/Time" &lt;= "<span className="text-emerald-400">[INC]</span>" AND
                      "End Date/Time" IS EMPTY
                      {advancedOptions.extra_jql && <span className="text-amber-400"> {advancedOptions.extra_jql}</span>}
                    </code>
                  </div>
                )}
              </div>
              <p className="text-xs text-muted-foreground">
                Cada búsqueda devuelve hasta {advancedOptions.max_results} resultados. Los duplicados se eliminan automáticamente.
              </p>
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={() => setAdvancedOptions(DEFAULT_SEARCH_OPTIONS)}
            >
              Restaurar
            </Button>
            <Button
              onClick={handleAdvancedSubmit}
              disabled={extractMutation.isPending}
            >
              {extractMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Iniciando...
                </>
              ) : (
                <>
                  <Search className="w-4 h-4" />
                  Analizar con opciones
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
