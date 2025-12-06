import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Activity, LogOut, Settings } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ThemeSwitcher } from '@/components/ThemeSwitcher'
import { cn } from '@/lib/utils'
import { logout } from '@/api/client'

interface HeaderProps {
  username?: string
  onLogout?: () => void
}

export function Header({ username, onLogout }: HeaderProps) {
  const location = useLocation()
  const navigate = useNavigate()

  const handleLogout = async () => {
    try {
      await logout()
      onLogout?.()
      navigate('/login')
    } catch (error) {
      console.error('Logout failed:', error)
    }
  }

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/50 bg-background/80 backdrop-blur-lg">
      <div className="container mx-auto px-4">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-3 group">
            <div className="relative">
              <div className="absolute inset-0 bg-primary/20 blur-lg rounded-full group-hover:bg-primary/30 transition-colors" />
              <div className="relative p-2 rounded-lg bg-gradient-to-br from-primary to-primary/70 shadow-lg shadow-primary/20">
                <Activity className="w-5 h-5 text-primary-foreground" />
              </div>
            </div>
            <div>
              <h1 className="font-semibold text-foreground leading-none">
                INC-TECCM
              </h1>
              <p className="text-xs text-muted-foreground">
                Correlation Analyzer
              </p>
            </div>
          </Link>

          {/* Navigation */}
          <nav className="hidden md:flex items-center gap-1">
            <NavLink href="/" active={location.pathname === '/'}>
              Dashboard
            </NavLink>
            <NavLink
              href="/settings"
              active={location.pathname === '/settings'}
            >
              <Settings className="w-4 h-4 mr-1" />
              Config
            </NavLink>
          </nav>

          {/* User section */}
          <div className="flex items-center gap-2">
            {/* Theme Switcher */}
            <ThemeSwitcher />

            {username && (
              <>
                <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-secondary ml-1">
                  <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-sm text-muted-foreground">
                    {username}
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleLogout}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <LogOut className="w-4 h-4" />
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}

interface NavLinkProps {
  href: string
  active?: boolean
  children: React.ReactNode
}

function NavLink({ href, active, children }: NavLinkProps) {
  return (
    <Link
      to={href}
      className={cn(
        'flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-colors',
        active
          ? 'text-foreground bg-secondary'
          : 'text-muted-foreground hover:text-foreground hover:bg-secondary/50'
      )}
    >
      {children}
    </Link>
  )
}

