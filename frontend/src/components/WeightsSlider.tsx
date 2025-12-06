import { useState, useEffect } from 'react'
import { Clock, Layers, Server, Users, RotateCcw } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Slider } from '@/components/ui/slider'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import type { Weights } from '@/types'

interface WeightsSliderProps {
  weights: Weights
  onChange: (weights: Weights) => void
  onRecalculate: () => void
  isLoading?: boolean
}

const DEFAULT_WEIGHTS: Weights = {
  time: 0.35,
  service: 0.30,
  infra: 0.20,
  org: 0.15,
}

const WEIGHT_CONFIG = [
  { key: 'time' as const, label: 'Time', icon: Clock, color: 'text-cyan-400' },
  { key: 'service' as const, label: 'Service', icon: Layers, color: 'text-violet-400' },
  { key: 'infra' as const, label: 'Infra', icon: Server, color: 'text-amber-400' },
  { key: 'org' as const, label: 'Org', icon: Users, color: 'text-emerald-400' },
]

export function WeightsSlider({
  weights,
  onChange,
  onRecalculate,
  isLoading,
}: WeightsSliderProps) {
  const [localWeights, setLocalWeights] = useState(weights)
  const [hasChanges, setHasChanges] = useState(false)

  useEffect(() => {
    setLocalWeights(weights)
    setHasChanges(false)
  }, [weights])

  const handleWeightChange = (key: keyof Weights, value: number) => {
    const newWeights = { ...localWeights, [key]: value }
    setLocalWeights(newWeights)
    setHasChanges(true)
  }

  const handleReset = () => {
    setLocalWeights(DEFAULT_WEIGHTS)
    onChange(DEFAULT_WEIGHTS)
    setHasChanges(true)
  }

  const handleRecalculate = () => {
    onChange(localWeights)
    onRecalculate()
    setHasChanges(false)
  }

  const totalWeight = Object.values(localWeights).reduce((a, b) => a + b, 0)

  return (
    <Card className="border-dashed">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
            Ajustar Pesos
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleReset}
            className="h-8 px-2 text-muted-foreground hover:text-foreground"
          >
            <RotateCcw className="w-4 h-4 mr-1" />
            Reset
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-x-6 gap-y-4">
          {WEIGHT_CONFIG.map(({ key, label, icon: Icon, color }) => (
            <div key={key} className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="flex items-center gap-2 text-sm">
                  <Icon className={`w-4 h-4 ${color}`} />
                  {label}
                </Label>
                <span className="mono text-sm font-medium text-muted-foreground">
                  {(localWeights[key] * 100).toFixed(0)}%
                </span>
              </div>
              <Slider
                value={[localWeights[key] * 100]}
                min={0}
                max={100}
                step={5}
                onValueChange={([value]) => handleWeightChange(key, value / 100)}
              />
            </div>
          ))}
        </div>

        {/* Total indicator */}
        <div className="flex items-center justify-between pt-2 border-t border-border/50">
          <span className="text-sm text-muted-foreground">
            Total:{' '}
            <span
              className={
                Math.abs(totalWeight - 1) < 0.01
                  ? 'text-emerald-400'
                  : 'text-amber-400'
              }
            >
              {(totalWeight * 100).toFixed(0)}%
            </span>
          </span>

          <Button
            onClick={handleRecalculate}
            disabled={!hasChanges || isLoading}
            size="sm"
            className="px-4"
          >
            {isLoading ? (
              <span className="animate-subtle-pulse">Calculando...</span>
            ) : (
              'Recalcular'
            )}
          </Button>
        </div>

        {Math.abs(totalWeight - 1) > 0.01 && (
          <p className="text-xs text-amber-400/80">
            Los pesos se normalizarán automáticamente al recalcular
          </p>
        )}
      </CardContent>
    </Card>
  )
}
