import { useState } from 'react'
import { Moon, Sun, Snowflake, Check } from 'lucide-react'
import { useTheme, Theme } from '@/contexts/ThemeContext'
import { cn } from '@/lib/utils'

const THEME_ICONS: Record<Theme, React.ElementType> = {
  'deep-space': Moon,
  'solar': Sun,
  'arctic': Snowflake,
}

export function ThemeSwitcher() {
  const { theme, setTheme, themes } = useTheme()
  const [isOpen, setIsOpen] = useState(false)
  const [isAnimating, setIsAnimating] = useState(false)

  const CurrentIcon = THEME_ICONS[theme]

  const handleThemeChange = (newTheme: Theme) => {
    if (newTheme === theme) {
      setIsOpen(false)
      return
    }

    setIsAnimating(true)
    setTheme(newTheme)

    setTimeout(() => {
      setIsAnimating(false)
      setIsOpen(false)
    }, 300)
  }

  return (
    <div className="relative">
      {/* Toggle button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'relative flex items-center justify-center w-9 h-9 rounded-lg',
          'bg-secondary/50 hover:bg-secondary transition-all duration-200',
          'border border-border/50 hover:border-primary/30',
          'focus:outline-none focus:ring-2 focus:ring-primary/20',
          isAnimating && 'theme-switch-animate'
        )}
        aria-label="Cambiar tema"
      >
        <CurrentIcon className="w-4 h-4 text-foreground" />

        {/* Active indicator dot */}
        <span
          className={cn(
            'absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-background',
            `theme-dot-${theme}`
          )}
        />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />

          {/* Menu */}
          <div
            className={cn(
              'absolute right-0 top-full mt-2 z-50',
              'w-56 p-2 rounded-xl',
              'bg-popover border border-border shadow-xl',
              'animate-fade-in'
            )}
          >
            <div className="px-2 py-1.5 mb-1">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Tema de visualización
              </p>
            </div>

            {themes.map((t) => {
              const Icon = THEME_ICONS[t.id]
              const isActive = theme === t.id

              return (
                <button
                  key={t.id}
                  onClick={() => handleThemeChange(t.id)}
                  className={cn(
                    'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg',
                    'transition-all duration-150',
                    isActive
                      ? 'bg-primary/10 text-primary'
                      : 'hover:bg-secondary text-foreground'
                  )}
                >
                  {/* Theme preview dot */}
                  <div
                    className={cn(
                      'w-8 h-8 rounded-lg flex items-center justify-center',
                      'border border-border/50',
                      isActive && 'border-primary/50'
                    )}
                  >
                    <Icon className={cn(
                      'w-4 h-4',
                      isActive ? 'text-primary' : 'text-muted-foreground'
                    )} />
                  </div>

                  {/* Text */}
                  <div className="flex-1 text-left">
                    <p className="text-sm font-medium">{t.name}</p>
                    <p className="text-xs text-muted-foreground line-clamp-1">
                      {t.description}
                    </p>
                  </div>

                  {/* Check mark */}
                  {isActive && (
                    <Check className="w-4 h-4 text-primary flex-shrink-0" />
                  )}
                </button>
              )
            })}

            {/* Theme preview strip */}
            <div className="mt-2 pt-2 border-t border-border">
              <div className="flex gap-1.5 px-2">
                {themes.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => handleThemeChange(t.id)}
                    className={cn(
                      'flex-1 h-6 rounded-md transition-all duration-200',
                      `theme-dot-${t.id}`,
                      theme === t.id
                        ? 'ring-2 ring-primary ring-offset-2 ring-offset-popover'
                        : 'opacity-60 hover:opacity-100'
                    )}
                    aria-label={t.name}
                  />
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
