import { createContext, useContext, useEffect, useState, ReactNode } from 'react'

export type Theme = 'deep-space' | 'solar' | 'arctic'

interface ThemeContextType {
  theme: Theme
  setTheme: (theme: Theme) => void
  themes: { id: Theme; name: string; description: string }[]
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

const THEMES: ThemeContextType['themes'] = [
  {
    id: 'deep-space',
    name: 'Deep Space',
    description: 'Tema oscuro con acentos cian y violeta',
  },
  {
    id: 'solar',
    name: 'Solar',
    description: 'Tema claro cálido con acentos ámbar',
  },
  {
    id: 'arctic',
    name: 'Arctic',
    description: 'Tema claro frío con acentos azul hielo',
  },
]

const STORAGE_KEY = 'inc-teccm-theme'

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => {
    // Check localStorage first
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem(STORAGE_KEY) as Theme | null
      if (stored && THEMES.some(t => t.id === stored)) {
        return stored
      }
    }
    return 'deep-space'
  })

  useEffect(() => {
    // Apply theme to document
    document.documentElement.setAttribute('data-theme', theme)

    // Save to localStorage
    localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme)
  }

  return (
    <ThemeContext.Provider value={{ theme, setTheme, themes: THEMES }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
