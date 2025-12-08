import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Save, RotateCcw, Clock, Layers, Server, Users, Check, ListOrdered, AlertTriangle, Zap, Timer, Tags, FolderTree, Plus, X, ChevronDown, ChevronRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Slider } from '@/components/ui/slider'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Header } from '@/components/Header'
import {
  getAppConfig,
  updateAppConfig,
  resetAppConfig,
  getServiceMappings,
  updateServiceSynonyms,
  updateServiceGroups,
  resetServiceSynonyms,
  resetServiceGroups,
} from '@/api/client'
import type { Weights, Penalties, Bonuses, Thresholds, AppConfig } from '@/types'

// Valores por defecto
const DEFAULT_WEIGHTS: Weights = {
  time: 0.35,
  service: 0.30,
  infra: 0.20,
  org: 0.15,
}

const DEFAULT_PENALTIES: Penalties = {
  no_live_intervals: 0.8,
  no_hosts: 0.95,
  no_services: 0.90,
  generic_change: 0.5,
  long_duration_week: 0.8,
  long_duration_month: 0.6,
  long_duration_quarter: 0.4,
}

const DEFAULT_BONUSES: Bonuses = {
  proximity_exact: 1.5,
  proximity_1h: 1.3,
  proximity_2h: 1.2,
  proximity_4h: 1.1,
}

const DEFAULT_THRESHOLDS: Thresholds = {
  time_decay_hours: 4,
  min_score_to_show: 0,
}

interface SettingsPageProps {
  username?: string
  onLogout: () => void
}

const WEIGHT_CONFIG = [
  {
    key: 'time' as const,
    label: 'Time Score',
    icon: Clock,
    color: 'text-cyan-400',
    description: 'Peso para la correlacion temporal (si el impacto ocurrio durante el cambio)',
  },
  {
    key: 'service' as const,
    label: 'Service Score',
    icon: Layers,
    color: 'text-violet-400',
    description: 'Peso para los servicios afectados en comun',
  },
  {
    key: 'infra' as const,
    label: 'Infra Score',
    icon: Server,
    color: 'text-amber-400',
    description: 'Peso para hosts y tecnologias en comun',
  },
  {
    key: 'org' as const,
    label: 'Org Score',
    icon: Users,
    color: 'text-emerald-400',
    description: 'Peso para el equipo y personas involucradas',
  },
]

const PENALTY_CONFIG = [
  { key: 'no_live_intervals' as const, label: 'Sin live_intervals', description: 'TECCM sin intervalos reales documentados' },
  { key: 'no_hosts' as const, label: 'Sin hosts', description: 'TECCM sin hosts identificados' },
  { key: 'no_services' as const, label: 'Sin services', description: 'TECCM sin servicios identificados' },
  { key: 'generic_change' as const, label: 'Cambio generico', description: 'TECCM afecta >10 servicios' },
  { key: 'long_duration_week' as const, label: 'Duracion >1 semana', description: 'Cambio dura mas de 7 dias' },
  { key: 'long_duration_month' as const, label: 'Duracion >1 mes', description: 'Cambio dura mas de 30 dias' },
  { key: 'long_duration_quarter' as const, label: 'Duracion >3 meses', description: 'Cambio dura mas de 90 dias' },
]

const BONUS_CONFIG = [
  { key: 'proximity_exact' as const, label: 'Proximidad exacta (<30m)', description: 'TECCM empezo menos de 30 min antes del INC' },
  { key: 'proximity_1h' as const, label: 'Proximidad 1h', description: 'TECCM empezo menos de 1 hora antes del INC' },
  { key: 'proximity_2h' as const, label: 'Proximidad 2h', description: 'TECCM empezo menos de 2 horas antes del INC' },
  { key: 'proximity_4h' as const, label: 'Proximidad 4h', description: 'TECCM empezo menos de 4 horas antes del INC' },
]

export function SettingsPage({ username, onLogout }: SettingsPageProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [localConfig, setLocalConfig] = useState<AppConfig | null>(null)
  const [saved, setSaved] = useState(false)

  // Fetch current config
  const { data: configData, isLoading } = useQuery({
    queryKey: ['appConfig'],
    queryFn: getAppConfig,
  })

  // Initialize local state when data loads - use useEffect to avoid render loop
  useEffect(() => {
    if (configData && !localConfig) {
      // Merge with defaults in case API returns incomplete data
      setLocalConfig({
        weights: { ...DEFAULT_WEIGHTS, ...configData.weights },
        penalties: { ...DEFAULT_PENALTIES, ...configData.penalties },
        bonuses: { ...DEFAULT_BONUSES, ...configData.bonuses },
        thresholds: { ...DEFAULT_THRESHOLDS, ...configData.thresholds },
        top_results: configData.top_results ?? 20,
      })
    }
  }, [configData, localConfig])

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: updateAppConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appConfig'] })
      queryClient.invalidateQueries({ queryKey: ['weights'] })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    },
  })

  // Reset mutation
  const resetMutation = useMutation({
    mutationFn: resetAppConfig,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['appConfig'] })
      queryClient.invalidateQueries({ queryKey: ['weights'] })
      setLocalConfig(data)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    },
  })

  // Service mappings
  const [localSynonyms, setLocalSynonyms] = useState<Record<string, string[]> | null>(null)
  const [localGroups, setLocalGroups] = useState<Record<string, string[]> | null>(null)
  const [expandedSynonyms, setExpandedSynonyms] = useState<Set<string>>(new Set())
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())
  const [newSynonymService, setNewSynonymService] = useState('')
  const [newGroupName, setNewGroupName] = useState('')
  const [synonymsSaved, setSynonymsSaved] = useState(false)
  const [synonymsReset, setSynonymsReset] = useState(false)
  const [groupsSaved, setGroupsSaved] = useState(false)
  const [groupsReset, setGroupsReset] = useState(false)

  const { data: mappingsData } = useQuery({
    queryKey: ['serviceMappings'],
    queryFn: getServiceMappings,
  })

  useEffect(() => {
    if (mappingsData && !localSynonyms) {
      setLocalSynonyms(mappingsData.synonyms)
    }
    if (mappingsData && !localGroups) {
      setLocalGroups(mappingsData.groups)
    }
  }, [mappingsData, localSynonyms, localGroups])

  const updateSynonymsMutation = useMutation({
    mutationFn: updateServiceSynonyms,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['serviceMappings'] })
      setSynonymsSaved(true)
      setTimeout(() => setSynonymsSaved(false), 2000)
    },
  })

  const updateGroupsMutation = useMutation({
    mutationFn: updateServiceGroups,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['serviceMappings'] })
      setGroupsSaved(true)
      setTimeout(() => setGroupsSaved(false), 2000)
    },
  })

  const resetSynonymsMutation = useMutation({
    mutationFn: resetServiceSynonyms,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['serviceMappings'] })
      setLocalSynonyms(data.synonyms)
      setSynonymsReset(true)
      setTimeout(() => setSynonymsReset(false), 2000)
    },
  })

  const resetGroupsMutation = useMutation({
    mutationFn: resetServiceGroups,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['serviceMappings'] })
      setLocalGroups(data.groups)
      setGroupsReset(true)
      setTimeout(() => setGroupsReset(false), 2000)
    },
  })

  // Synonym handlers
  const handleAddSynonymAlias = (service: string, alias: string) => {
    if (!localSynonyms || !alias.trim()) return
    const aliases = localSynonyms[service] || []
    if (aliases.includes(alias.trim().toLowerCase())) return
    setLocalSynonyms({
      ...localSynonyms,
      [service]: [...aliases, alias.trim().toLowerCase()]
    })
  }

  const handleRemoveSynonymAlias = (service: string, alias: string) => {
    if (!localSynonyms) return
    setLocalSynonyms({
      ...localSynonyms,
      [service]: localSynonyms[service].filter(a => a !== alias)
    })
  }

  const handleAddSynonymService = () => {
    if (!localSynonyms || !newSynonymService.trim()) return
    const serviceName = newSynonymService.trim().toLowerCase()
    if (localSynonyms[serviceName]) return
    setLocalSynonyms({
      ...localSynonyms,
      [serviceName]: []
    })
    setNewSynonymService('')
    setExpandedSynonyms(new Set([...expandedSynonyms, serviceName]))
  }

  const handleRemoveSynonymService = (service: string) => {
    if (!localSynonyms) return
    const { [service]: _, ...rest } = localSynonyms
    setLocalSynonyms(rest)
  }

  const handleSaveSynonyms = () => {
    if (localSynonyms) {
      updateSynonymsMutation.mutate(localSynonyms)
    }
  }

  // Group handlers
  const handleAddGroupService = (group: string, service: string) => {
    if (!localGroups || !service.trim()) return
    const services = localGroups[group] || []
    if (services.includes(service.trim().toLowerCase())) return
    setLocalGroups({
      ...localGroups,
      [group]: [...services, service.trim().toLowerCase()]
    })
  }

  const handleRemoveGroupService = (group: string, service: string) => {
    if (!localGroups) return
    setLocalGroups({
      ...localGroups,
      [group]: localGroups[group].filter(s => s !== service)
    })
  }

  const handleAddGroup = () => {
    if (!localGroups || !newGroupName.trim()) return
    const groupName = newGroupName.trim().toLowerCase()
    if (localGroups[groupName]) return
    setLocalGroups({
      ...localGroups,
      [groupName]: []
    })
    setNewGroupName('')
    setExpandedGroups(new Set([...expandedGroups, groupName]))
  }

  const handleRemoveGroup = (group: string) => {
    if (!localGroups) return
    const { [group]: _, ...rest } = localGroups
    setLocalGroups(rest)
  }

  const handleSaveGroups = () => {
    if (localGroups) {
      updateGroupsMutation.mutate(localGroups)
    }
  }

  const handleWeightChange = (key: keyof Weights, value: number) => {
    if (localConfig) {
      setLocalConfig({
        ...localConfig,
        weights: { ...localConfig.weights, [key]: value }
      })
    }
  }

  const handlePenaltyChange = (key: keyof Penalties, value: number) => {
    if (localConfig) {
      setLocalConfig({
        ...localConfig,
        penalties: { ...localConfig.penalties, [key]: value }
      })
    }
  }

  const handleBonusChange = (key: keyof Bonuses, value: number) => {
    if (localConfig) {
      setLocalConfig({
        ...localConfig,
        bonuses: { ...localConfig.bonuses, [key]: value }
      })
    }
  }

  const handleThresholdChange = (key: keyof Thresholds, value: number) => {
    if (localConfig) {
      setLocalConfig({
        ...localConfig,
        thresholds: { ...localConfig.thresholds, [key]: value }
      })
    }
  }

  const handleTopResultsChange = (value: number) => {
    if (localConfig) {
      setLocalConfig({ ...localConfig, top_results: value })
    }
  }

  const handleSave = () => {
    if (localConfig) {
      updateMutation.mutate(localConfig)
    }
  }

  const handleReset = () => {
    resetMutation.mutate()
  }

  // Use localConfig with defaults as fallback
  const weights = localConfig?.weights ?? configData?.weights ?? DEFAULT_WEIGHTS
  const penalties = localConfig?.penalties ?? configData?.penalties ?? DEFAULT_PENALTIES
  const bonuses = localConfig?.bonuses ?? configData?.bonuses ?? DEFAULT_BONUSES
  const thresholds = localConfig?.thresholds ?? configData?.thresholds ?? DEFAULT_THRESHOLDS
  const topResults = localConfig?.top_results ?? configData?.top_results ?? 20
  const totalWeight = Object.values(weights).reduce((a, b) => a + b, 0)

  const hasChanges =
    localConfig &&
    configData &&
    JSON.stringify(localConfig) !== JSON.stringify(configData)

  return (
    <div className="min-h-screen bg-background">
      <Header username={username} onLogout={onLogout} />

      <main className="container mx-auto px-4 py-8">
        <div className="max-w-2xl mx-auto space-y-6">
          {/* Header */}
          <div className="flex items-center gap-4 animate-fade-in">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate('/')}
            >
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div className="flex-1">
              <h1 className="text-2xl font-bold">Configuracion</h1>
              <p className="text-muted-foreground">
                Ajusta los parametros del algoritmo de scoring
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={handleReset}
                disabled={resetMutation.isPending}
              >
                <RotateCcw className="w-4 h-4 mr-1" />
                Reset
              </Button>
              <Button
                onClick={handleSave}
                disabled={!hasChanges || updateMutation.isPending}
              >
                {saved ? (
                  <>
                    <Check className="w-4 h-4 mr-1" />
                    Guardado
                  </>
                ) : updateMutation.isPending ? (
                  'Guardando...'
                ) : (
                  <>
                    <Save className="w-4 h-4 mr-1" />
                    Guardar
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* Weights Card */}
          <Card className="animate-fade-in" style={{ animationDelay: '100ms' }}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Layers className="w-5 h-5 text-primary" />
                Pesos de Scoring
              </CardTitle>
              <CardDescription>
                Importancia relativa de cada dimension. Se normalizan automaticamente.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {isLoading ? (
                <div className="space-y-4">
                  {[...Array(4)].map((_, i) => (
                    <div key={i} className="h-16 rounded-lg shimmer" />
                  ))}
                </div>
              ) : (
                <>
                  {WEIGHT_CONFIG.map(({ key, label, icon: Icon, color, description }) => (
                    <div key={key} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label className="flex items-center gap-2">
                          <Icon className={`w-4 h-4 ${color}`} />
                          {label}
                        </Label>
                        <span className="mono text-sm font-semibold">
                          {(weights[key] * 100).toFixed(0)}%
                        </span>
                      </div>
                      <Slider
                        value={[weights[key] * 100]}
                        min={0}
                        max={100}
                        step={5}
                        onValueChange={([value]) =>
                          handleWeightChange(key, value / 100)
                        }
                      />
                      <p className="text-xs text-muted-foreground">{description}</p>
                    </div>
                  ))}

                  <div className="pt-2 border-t border-border">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Total:</span>
                      <span className={Math.abs(totalWeight - 1) < 0.01 ? 'text-emerald-400 font-medium' : 'text-amber-400 font-medium'}>
                        {(totalWeight * 100).toFixed(0)}%
                        {Math.abs(totalWeight - 1) > 0.01 && ' (se normalizara)'}
                      </span>
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* Penalties Card */}
          <Card className="animate-fade-in" style={{ animationDelay: '150ms' }}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-400" />
                Penalizaciones
              </CardTitle>
              <CardDescription>
                Multiplicadores que reducen el score (0 = elimina, 1 = sin efecto).
                Las penalizaciones por duracion no aplican si service+infra &gt; 80.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {isLoading ? (
                <div className="space-y-4">
                  {[...Array(7)].map((_, i) => (
                    <div key={i} className="h-12 rounded-lg shimmer" />
                  ))}
                </div>
              ) : (
                <div className="grid gap-4">
                  {PENALTY_CONFIG.map(({ key, label, description }) => (
                    <div key={key} className="flex items-center gap-4">
                      <div className="flex-1 min-w-0">
                        <Label className="text-sm">{label}</Label>
                        <p className="text-xs text-muted-foreground truncate">{description}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Slider
                          className="w-24"
                          value={[penalties[key] * 100]}
                          min={0}
                          max={100}
                          step={5}
                          onValueChange={([value]) => handlePenaltyChange(key, value / 100)}
                        />
                        <span className="mono text-sm w-12 text-right">
                          x{penalties[key].toFixed(2)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Bonuses Card */}
          <Card className="animate-fade-in" style={{ animationDelay: '200ms' }}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="w-5 h-5 text-emerald-400" />
                Bonificaciones
              </CardTitle>
              <CardDescription>
                Multiplicadores que aumentan el score por proximidad temporal (1 = sin efecto).
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {isLoading ? (
                <div className="space-y-4">
                  {[...Array(4)].map((_, i) => (
                    <div key={i} className="h-12 rounded-lg shimmer" />
                  ))}
                </div>
              ) : (
                <div className="grid gap-4">
                  {BONUS_CONFIG.map(({ key, label, description }) => (
                    <div key={key} className="flex items-center gap-4">
                      <div className="flex-1 min-w-0">
                        <Label className="text-sm">{label}</Label>
                        <p className="text-xs text-muted-foreground truncate">{description}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Slider
                          className="w-24"
                          value={[bonuses[key] * 100]}
                          min={100}
                          max={300}
                          step={10}
                          onValueChange={([value]) => handleBonusChange(key, value / 100)}
                        />
                        <span className="mono text-sm w-12 text-right">
                          x{bonuses[key].toFixed(2)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Thresholds Card */}
          <Card className="animate-fade-in" style={{ animationDelay: '250ms' }}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Timer className="w-5 h-5 text-cyan-400" />
                Umbrales
              </CardTitle>
              <CardDescription>
                Parametros adicionales del algoritmo de scoring.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {isLoading ? (
                <div className="space-y-4">
                  {[...Array(2)].map((_, i) => (
                    <div key={i} className="h-12 rounded-lg shimmer" />
                  ))}
                </div>
              ) : (
                <div className="grid gap-4">
                  <div className="flex items-center gap-4">
                    <div className="flex-1">
                      <Label className="text-sm">Time decay (horas)</Label>
                      <p className="text-xs text-muted-foreground">Horas para que el time_score decaiga a 0</p>
                    </div>
                    <Input
                      type="number"
                      className="w-20 text-right"
                      min={1}
                      max={48}
                      value={thresholds?.time_decay_hours || 4}
                      onChange={(e) => handleThresholdChange('time_decay_hours', parseFloat(e.target.value) || 4)}
                    />
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="flex-1">
                      <Label className="text-sm">Score minimo</Label>
                      <p className="text-xs text-muted-foreground">Score minimo para mostrar en ranking</p>
                    </div>
                    <Input
                      type="number"
                      className="w-20 text-right"
                      min={0}
                      max={100}
                      value={thresholds?.min_score_to_show || 0}
                      onChange={(e) => handleThresholdChange('min_score_to_show', parseFloat(e.target.value) || 0)}
                    />
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Top Results Card */}
          <Card className="animate-fade-in" style={{ animationDelay: '300ms' }}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ListOrdered className="w-5 h-5 text-primary" />
                Resultados del Ranking
              </CardTitle>
              <CardDescription>
                Cantidad de TECCMs a mostrar por defecto en el ranking.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label>Top resultados</Label>
                  <span className="mono text-sm font-semibold">{topResults}</span>
                </div>
                <Slider
                  value={[topResults]}
                  min={5}
                  max={100}
                  step={5}
                  onValueChange={([value]) => handleTopResultsChange(value)}
                />
              </div>
            </CardContent>
          </Card>

          {/* Service Synonyms Card */}
          <Card className="animate-fade-in" style={{ animationDelay: '350ms' }}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Tags className="w-5 h-5 text-violet-400" />
                    Sinonimos de Servicios
                  </CardTitle>
                  <CardDescription>
                    Mapeo de nombres canonicos a sus alias. Cuando se detecta un alias, se normaliza al nombre canonico.
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      if (window.confirm('¿Restaurar sinonimos a valores por defecto?\n\nEsto eliminara todos los cambios personalizados y afectara a todos los usuarios.')) {
                        resetSynonymsMutation.mutate()
                      }
                    }}
                    disabled={resetSynonymsMutation.isPending || synonymsReset}
                  >
                    {synonymsReset ? (
                      <><Check className="w-3 h-3 mr-1 text-emerald-400" />Reseteado</>
                    ) : resetSynonymsMutation.isPending ? (
                      <><RotateCcw className="w-3 h-3 mr-1 animate-spin" />Reseteando...</>
                    ) : (
                      <><RotateCcw className="w-3 h-3 mr-1" />Reset</>
                    )}
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleSaveSynonyms}
                    disabled={updateSynonymsMutation.isPending || !localSynonyms || synonymsSaved}
                  >
                    {synonymsSaved ? (
                      <><Check className="w-3 h-3 mr-1" />Guardado</>
                    ) : updateSynonymsMutation.isPending ? (
                      <><Save className="w-3 h-3 mr-1 animate-pulse" />Guardando...</>
                    ) : (
                      <><Save className="w-3 h-3 mr-1" />Guardar</>
                    )}
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {/* Add new service */}
              <div className="flex gap-2">
                <Input
                  placeholder="Nuevo servicio canonico..."
                  value={newSynonymService}
                  onChange={(e) => setNewSynonymService(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddSynonymService()}
                  className="flex-1"
                />
                <Button size="sm" onClick={handleAddSynonymService}>
                  <Plus className="w-4 h-4" />
                </Button>
              </div>

              {/* List of services */}
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {localSynonyms && Object.entries(localSynonyms).sort(([a], [b]) => a.localeCompare(b)).map(([service, aliases]) => {
                  const isExpanded = expandedSynonyms.has(service)
                  return (
                    <div key={service} className="border border-border rounded-lg overflow-hidden">
                      <div
                        className="flex items-center gap-2 px-3 py-2 bg-secondary/30 cursor-pointer hover:bg-secondary/50"
                        onClick={() => {
                          const newExpanded = new Set(expandedSynonyms)
                          if (isExpanded) newExpanded.delete(service)
                          else newExpanded.add(service)
                          setExpandedSynonyms(newExpanded)
                        }}
                      >
                        {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                        <span className="font-medium text-sm flex-1">{service}</span>
                        <span className="text-xs text-muted-foreground">{aliases.length} alias</span>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6"
                          onClick={(e) => { e.stopPropagation(); handleRemoveSynonymService(service) }}
                        >
                          <X className="w-3 h-3" />
                        </Button>
                      </div>
                      {isExpanded && (
                        <div className="px-3 py-2 space-y-2">
                          <div className="flex flex-wrap gap-1">
                            {aliases.map(alias => (
                              <span
                                key={alias}
                                className="inline-flex items-center gap-1 px-2 py-0.5 bg-secondary rounded text-xs"
                              >
                                {alias}
                                <button
                                  onClick={() => handleRemoveSynonymAlias(service, alias)}
                                  className="hover:text-destructive"
                                >
                                  <X className="w-3 h-3" />
                                </button>
                              </span>
                            ))}
                          </div>
                          <Input
                            placeholder="Añadir alias..."
                            className="h-7 text-xs"
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                handleAddSynonymAlias(service, (e.target as HTMLInputElement).value)
                                ;(e.target as HTMLInputElement).value = ''
                              }
                            }}
                          />
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>

          {/* Service Groups Card */}
          <Card className="animate-fade-in" style={{ animationDelay: '400ms' }}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <FolderTree className="w-5 h-5 text-emerald-400" />
                    Grupos de Servicios (Ecosistemas)
                  </CardTitle>
                  <CardDescription>
                    Servicios del mismo ecosistema. Si no hay match exacto, un match de ecosistema da 25 puntos.
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      if (window.confirm('¿Restaurar ecosistemas a valores por defecto?\n\nEsto eliminara todos los cambios personalizados y afectara a todos los usuarios.')) {
                        resetGroupsMutation.mutate()
                      }
                    }}
                    disabled={resetGroupsMutation.isPending || groupsReset}
                  >
                    {groupsReset ? (
                      <><Check className="w-3 h-3 mr-1 text-emerald-400" />Reseteado</>
                    ) : resetGroupsMutation.isPending ? (
                      <><RotateCcw className="w-3 h-3 mr-1 animate-spin" />Reseteando...</>
                    ) : (
                      <><RotateCcw className="w-3 h-3 mr-1" />Reset</>
                    )}
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleSaveGroups}
                    disabled={updateGroupsMutation.isPending || !localGroups || groupsSaved}
                  >
                    {groupsSaved ? (
                      <><Check className="w-3 h-3 mr-1" />Guardado</>
                    ) : updateGroupsMutation.isPending ? (
                      <><Save className="w-3 h-3 mr-1 animate-pulse" />Guardando...</>
                    ) : (
                      <><Save className="w-3 h-3 mr-1" />Guardar</>
                    )}
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {/* Add new group */}
              <div className="flex gap-2">
                <Input
                  placeholder="Nuevo ecosistema..."
                  value={newGroupName}
                  onChange={(e) => setNewGroupName(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddGroup()}
                  className="flex-1"
                />
                <Button size="sm" onClick={handleAddGroup}>
                  <Plus className="w-4 h-4" />
                </Button>
              </div>

              {/* List of groups */}
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {localGroups && Object.entries(localGroups).sort(([a], [b]) => a.localeCompare(b)).map(([group, services]) => {
                  const isExpanded = expandedGroups.has(group)
                  return (
                    <div key={group} className="border border-border rounded-lg overflow-hidden">
                      <div
                        className="flex items-center gap-2 px-3 py-2 bg-secondary/30 cursor-pointer hover:bg-secondary/50"
                        onClick={() => {
                          const newExpanded = new Set(expandedGroups)
                          if (isExpanded) newExpanded.delete(group)
                          else newExpanded.add(group)
                          setExpandedGroups(newExpanded)
                        }}
                      >
                        {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                        <span className="font-medium text-sm flex-1">{group}</span>
                        <span className="text-xs text-muted-foreground">{services.length} servicios</span>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6"
                          onClick={(e) => { e.stopPropagation(); handleRemoveGroup(group) }}
                        >
                          <X className="w-3 h-3" />
                        </Button>
                      </div>
                      {isExpanded && (
                        <div className="px-3 py-2 space-y-2">
                          <div className="flex flex-wrap gap-1">
                            {services.map(service => (
                              <span
                                key={service}
                                className="inline-flex items-center gap-1 px-2 py-0.5 bg-secondary rounded text-xs"
                              >
                                {service}
                                <button
                                  onClick={() => handleRemoveGroupService(group, service)}
                                  className="hover:text-destructive"
                                >
                                  <X className="w-3 h-3" />
                                </button>
                              </span>
                            ))}
                          </div>
                          <Input
                            placeholder="Añadir servicio al ecosistema..."
                            className="h-7 text-xs"
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                handleAddGroupService(group, (e.target as HTMLInputElement).value)
                                ;(e.target as HTMLInputElement).value = ''
                              }
                            }}
                          />
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>

          {/* Info Card */}
          <Card className="border-dashed animate-fade-in" style={{ animationDelay: '350ms' }}>
            <CardHeader>
              <CardTitle className="text-base">Como funciona el Scoring</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground space-y-4">
              {/* Formula principal */}
              <div>
                <p className="font-medium text-foreground mb-2">1. Formula base</p>
                <code className="block p-3 rounded-lg bg-secondary/50 mono text-xs">
                  score = (time*w1 + service*w2 + infra*w3 + org*w4) * penalties * bonuses
                </code>
                <p className="mt-2 text-xs">
                  Los pesos (w1-w4) se normalizan automaticamente para sumar 100%.
                </p>
              </div>

              {/* Time Score y Decay */}
              <div>
                <p className="font-medium text-foreground mb-2">2. Time Score y Time Decay</p>
                <p className="mb-2">
                  El <span className="text-cyan-400">time_score</span> mide cuanto coincide temporalmente el TECCM con el incidente.
                  El <span className="text-cyan-400">time_decay</span> controla como decae esta puntuacion segun la distancia temporal:
                </p>
                <code className="block p-3 rounded-lg bg-secondary/50 mono text-xs">
                  time_score = max(0, 100 - (horas_diferencia / time_decay_hours) * 100)
                </code>
                <div className="mt-2 text-xs space-y-1">
                  <p>Con time_decay = {thresholds.time_decay_hours}h:</p>
                  <ul className="list-disc list-inside ml-2 space-y-0.5">
                    <li>0h de diferencia → 100 puntos</li>
                    <li>{thresholds.time_decay_hours / 2}h de diferencia → 50 puntos</li>
                    <li>{thresholds.time_decay_hours}h o mas → 0 puntos</li>
                  </ul>
                  <p className="text-amber-400 mt-1">
                    Importante: Un time_score de 0 NO elimina el TECCM. Los otros scores (service, infra, org)
                    pueden seguir aportando puntuacion.
                  </p>
                </div>
              </div>

              {/* Penalizaciones */}
              <div>
                <p className="font-medium text-foreground mb-2">3. Penalizaciones (multiplicadores &lt;1)</p>
                <p className="mb-2">
                  Reducen el score final. Se multiplican entre si (acumulativas).
                </p>
                <div className="text-xs space-y-1">
                  <p>Ejemplo: TECCM sin hosts (x{penalties.no_hosts.toFixed(2)}) y sin services (x{penalties.no_services.toFixed(2)}):</p>
                  <code className="block p-2 rounded bg-secondary/50 mono">
                    score_final = score_base * {penalties.no_hosts.toFixed(2)} * {penalties.no_services.toFixed(2)} = score_base * {(penalties.no_hosts * penalties.no_services).toFixed(2)}
                  </code>
                </div>
                <p className="text-xs text-emerald-400 mt-2">
                  Excepcion: Si service_score + infra_score &gt; 80, las penalizaciones por duracion larga NO se aplican
                  (el TECCM tiene fuerte correlacion con el incidente).
                </p>
              </div>

              {/* Bonificaciones */}
              <div>
                <p className="font-medium text-foreground mb-2">4. Bonificaciones (multiplicadores &gt;1)</p>
                <p className="mb-2">
                  Aumentan el score si el TECCM empezo muy cerca del momento del incidente.
                  Solo se aplica la bonificacion mas alta (no son acumulativas).
                </p>
                <div className="text-xs space-y-1">
                  <ul className="list-disc list-inside ml-2 space-y-0.5">
                    <li>&lt;30 min antes del INC → x{bonuses.proximity_exact.toFixed(2)}</li>
                    <li>&lt;1 hora antes → x{bonuses.proximity_1h.toFixed(2)}</li>
                    <li>&lt;2 horas antes → x{bonuses.proximity_2h.toFixed(2)}</li>
                    <li>&lt;4 horas antes → x{bonuses.proximity_4h.toFixed(2)}</li>
                  </ul>
                </div>
              </div>

              {/* Score minimo */}
              <div>
                <p className="font-medium text-foreground mb-2">5. Filtro de resultados</p>
                <p className="text-xs">
                  Solo se muestran TECCMs con score &gt;= {thresholds.min_score_to_show}.
                  Se muestran los top {topResults} resultados ordenados por score.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  )
}
