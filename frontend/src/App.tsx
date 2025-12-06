import { useState, useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { TooltipProvider } from '@/components/ui/tooltip'
import { LoginPage } from '@/pages/LoginPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { RankingPage } from '@/pages/RankingPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { ApiDocsPage } from '@/pages/ApiDocsPage'
import { getSession } from '@/api/client'

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null)

  const { data: session, isLoading } = useQuery({
    queryKey: ['session'],
    queryFn: getSession,
    retry: false,
  })

  useEffect(() => {
    if (session) {
      setIsAuthenticated(session.authenticated)
    }
  }, [session])

  const handleLogin = () => {
    setIsAuthenticated(true)
  }

  const handleLogout = () => {
    setIsAuthenticated(false)
  }

  // Loading state
  if (isLoading || isAuthenticated === null) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    )
  }

  return (
    <TooltipProvider>
      <Routes>
        <Route
          path="/login"
          element={
            isAuthenticated ? (
              <Navigate to="/" replace />
            ) : (
              <LoginPage onLogin={handleLogin} />
            )
          }
        />
        <Route
          path="/"
          element={
            isAuthenticated ? (
              <DashboardPage
                username={session?.username}
                onLogout={handleLogout}
              />
            ) : (
              <Navigate to="/login" replace />
            )
          }
        />
        <Route
          path="/analysis/:jobId"
          element={
            isAuthenticated ? (
              <RankingPage
                username={session?.username}
                onLogout={handleLogout}
              />
            ) : (
              <Navigate to="/login" replace />
            )
          }
        />
        <Route
          path="/settings"
          element={
            isAuthenticated ? (
              <SettingsPage
                username={session?.username}
                onLogout={handleLogout}
              />
            ) : (
              <Navigate to="/login" replace />
            )
          }
        />
        <Route
          path="/api-docs"
          element={
            isAuthenticated ? (
              <ApiDocsPage
                username={session?.username}
                onLogout={handleLogout}
              />
            ) : (
              <Navigate to="/login" replace />
            )
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </TooltipProvider>
  )
}

export default App
