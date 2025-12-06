import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Save, RotateCcw, Clock, Layers, Server, Users, Check, ListOrdered } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Slider } from '@/components/ui/slider'
import { Label } from '@/components/ui/label'
import { Header } from '@/components/Header'
import { getAppConfig, updateAppConfig, resetAppConfig } from '@/api/client'
import type { Weights, AppConfig } from '@/types'

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
    description: 'Peso para la correlación temporal (si el impacto ocurrió durante el cambio)',
  },
  {
    key: 'service' as const,
    label: 'Service Score',
    icon: Layers,
    color: 'text-violet-400',
    description: 'Peso para los servicios afectados en común',
  },
  {
    key: 'infra' as const,
    label: 'Infra Score',
    icon: Server,
    color: 'text-amber-400',
    description: 'Peso para hosts y tecnologías en común',
  },
  {
    key: 'org' as const,
    label: 'Org Score',
    icon: Users,
    color: 'text-emerald-400',
    description: 'Peso para el equipo y personas involucradas',
  },
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

  // Initialize local state when data loads
  if (configData && !localConfig) {
    setLocalConfig(configData)
  }

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

  const handleWeightChange = (key: keyof Weights, value: number) => {
    if (localConfig) {
      setLocalConfig({
        ...localConfig,
        weights: { ...localConfig.weights, [key]: value }
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

  const weights = localConfig?.weights || configData?.weights
  const topResults = localConfig?.top_results || configData?.top_results || 20
  const totalWeight = weights
    ? Object.values(weights).reduce((a, b) => a + b, 0)
    : 0

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
            <div>
              <h1 className="text-2xl font-bold">Configuración</h1>
              <p className="text-muted-foreground">
                Ajusta los pesos por defecto para el scoring
              </p>
            </div>
          </div>

          {/* Weights Card */}
          <Card className="animate-fade-in" style={{ animationDelay: '100ms' }}>
            <CardHeader>
              <CardTitle>Pesos de Scoring</CardTitle>
              <CardDescription>
                Estos pesos se usarán por defecto en todos los nuevos análisis.
                Los pesos se normalizan automáticamente para sumar 100%.
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
                    <div key={key} className="space-y-3">
                      <div className="flex items-center justify-between">
                        <Label className="flex items-center gap-2">
                          <Icon className={`w-4 h-4 ${color}`} />
                          {label}
                        </Label>
                        <span className="mono text-sm font-semibold">
                          {weights ? (weights[key] * 100).toFixed(0) : 0}%
                        </span>
                      </div>
                      <Slider
                        value={weights ? [weights[key] * 100] : [0]}
                        min={0}
                        max={100}
                        step={5}
                        onValueChange={([value]) =>
                          handleWeightChange(key, value / 100)
                        }
                      />
                      <p className="text-xs text-muted-foreground">
                        {description}
                      </p>
                    </div>
                  ))}

                  {/* Total and actions */}
                  <div className="pt-4 border-t border-border space-y-4">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Total:</span>
                      <span
                        className={
                          Math.abs(totalWeight - 1) < 0.01
                            ? 'text-emerald-400 font-medium'
                            : 'text-amber-400 font-medium'
                        }
                      >
                        {(totalWeight * 100).toFixed(0)}%
                      </span>
                    </div>

                    {Math.abs(totalWeight - 1) > 0.01 && (
                      <p className="text-xs text-amber-400/80">
                        Los pesos se normalizarán al guardar
                      </p>
                    )}

                    <div className="flex items-center justify-between gap-3">
                      <Button
                        variant="outline"
                        onClick={handleReset}
                        disabled={resetMutation.isPending}
                      >
                        <RotateCcw className="w-4 h-4 mr-1" />
                        Restaurar defaults
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
                            Guardar cambios
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* Top Results Card */}
          <Card className="animate-fade-in" style={{ animationDelay: '150ms' }}>
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
                  <span className="mono text-sm font-semibold">
                    {topResults}
                  </span>
                </div>
                <Slider
                  value={[topResults]}
                  min={5}
                  max={100}
                  step={5}
                  onValueChange={([value]) => handleTopResultsChange(value)}
                />
                <p className="text-xs text-muted-foreground">
                  Define cuántos TECCMs se muestran inicialmente en la página de resultados.
                  Siempre puedes expandir para ver más.
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Info Card */}
          <Card
            className="border-dashed animate-fade-in"
            style={{ animationDelay: '250ms' }}
          >
            <CardHeader>
              <CardTitle className="text-base">Sobre el Scoring</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground space-y-2">
              <p>
                El score final de cada TECCM se calcula como la suma ponderada de
                los 4 sub-scores:
              </p>
              <code className="block p-3 rounded-lg bg-secondary/50 mono text-xs">
                final = (time × w₁) + (service × w₂) + (infra × w₃) + (org × w₄)
              </code>
              <p>
                Además se aplican penalizaciones si el TECCM no tiene
                live_intervals (-20%), hosts (-5%) o services (-10%).
              </p>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  )
}
