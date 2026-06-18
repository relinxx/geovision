import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Users, Shield } from 'lucide-react';
import { MainLayout } from './layouts/MainLayout/MainLayout';
import { HomePage } from './pages/HomePage/HomePage';
import { WorkbenchPage } from './pages/WorkbenchPage/WorkbenchPage';
import { LayersPage } from './pages/LayersPage/LayersPage';
import { PlanGalleryPage } from './pages/PlanGalleryPage/PlanGalleryPage';
import { PlaceholderPage } from './pages/PlaceholderPage/PlaceholderPage';
import { SettingsPage } from './pages/SettingsPage/SettingsPage';
import { WelcomePage } from './pages/WelcomePage';
import { LoginPage } from './pages/LoginPage/LoginPage';
import { RegisterPage } from './pages/RegisterPage/RegisterPage';
import { Toaster } from './components/ui/sonner';
import { useSimulation } from './hooks/useSimulation';
import { generateInitialZones } from './utils/simulation';
import { ViewType, Metrics } from './types';
import { PlannerSettingsProvider } from './context/PlannerSettingsContext';
import { PlannerWorkspaceProvider } from './context/PlannerWorkspaceContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import { CopilotPage } from './pages/CopilotPage/CopilotPage';

const INITIAL_METRICS: Metrics = {
  population: 5842,
  traffic: 75,
  zoning: 92,
  environmental: 3.2,
  greenArea: 68,
};

/** Catch-all route - redirects based on authentication state */
function CatchAllRoute() {
  const { isAuthenticated, isLoading } = useAuth();
  
  if (isLoading) {
    return (
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center', 
        height: '100vh',
        background: 'var(--color-bg-primary, #0A1630)'
      }}>
        <div style={{ color: '#4FFFA7' }}>Loading...</div>
      </div>
    );
  }
  
  return <Navigate to={isAuthenticated ? '/dashboard' : '/welcome'} replace />;
}

/** Protected route component - redirects to login if not authenticated */
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  
  if (isLoading) {
    return (
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center', 
        height: '100vh',
        background: 'var(--color-bg-primary, #0A1630)'
      }}>
        <div style={{ color: '#4FFFA7' }}>Loading...</div>
      </div>
    );
  }
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  return <>{children}</>;
}

/** Public route component - redirects to dashboard if already authenticated */
function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();
  
  if (isLoading) {
    return (
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center', 
        height: '100vh',
        background: 'var(--color-bg-primary, #0A1630)'
      }}>
        <div style={{ color: '#4FFFA7' }}>Loading...</div>
      </div>
    );
  }
  
  if (isAuthenticated) {
    // Redirect to dashboard, but preserve any intended destination
    const from = location.state?.from?.pathname || '/dashboard';
    return <Navigate to={from} replace />;
  }
  
  return <>{children}</>;
}

/** Main application content with routing */
function AppContent() {
  const [activeView, setActiveView] = useState<ViewType>('workbench');
  const [selectedRegion] = useState<string>('Downtown District');

  const initialZones = generateInitialZones();

  const {
    metrics,
    zones,
    simulationTime,
  } = useSimulation(INITIAL_METRICS, initialZones);

  // Render main dashboard content based on active view
  const renderDashboardContent = () => (
    <>
      <Toaster />

      {activeView === 'workbench' && (
        <WorkbenchPage
          metrics={metrics}
          simulationTime={simulationTime}
          zones={zones}
          selectedRegion={selectedRegion}
          onOpenView={setActiveView}
        />
      )}

      {activeView === 'environmental' && (
        <HomePage
          metrics={metrics}
          simulationTime={simulationTime}
          zones={zones}
          selectedRegion={selectedRegion}
          onOpenView={setActiveView}
        />
      )}

      {activeView === 'layers' && (
        <LayersPage
          metrics={metrics}
          simulationTime={simulationTime}
          zones={zones}
          selectedRegion={selectedRegion}
        />
      )}

      {activeView === 'plans' && (
        <PlanGalleryPage
          metrics={metrics}
          simulationTime={simulationTime}
          zones={zones}
          selectedRegion={selectedRegion}
        />
      )}

      {activeView === 'agents' && (
        <PlaceholderPage
          icon={Users}
          title="AI Agents View"
          description="Configure and monitor AI agents"
          color="#3BC7F5"
        />
      )}

      {activeView === 'constraints' && (
        <PlaceholderPage
          icon={Shield}
          title="Constraints View"
          description="View and manage planning constraints"
          color="#FFB86C"
        />
      )}

      {activeView === 'settings' && (
        <SettingsPage
          metrics={metrics}
          simulationTime={simulationTime}
          zones={zones}
          selectedRegion={selectedRegion}
        />
      )}

      {activeView === 'copilot' && (
        <CopilotPage />
      )}
    </>
  );

  return (
    <>
      <Toaster position="top-center" richColors />
      <Routes>
        {/* Root redirect - based on auth state */}
        <Route path="/" element={<CatchAllRoute />} />

      {/* Public routes */}
      <Route
        path="/welcome"
        element={
          <PublicRoute>
            <WelcomePage onEnterWorkspace={() => {}} />
          </PublicRoute>
        }
      />
      <Route
        path="/login"
        element={
          <PublicRoute>
            <LoginPage />
          </PublicRoute>
        }
      />
      <Route
        path="/register"
        element={
          <PublicRoute>
            <RegisterPage />
          </PublicRoute>
        }
      />

      {/* Protected dashboard routes */}
      <Route
        path="/dashboard/*"
        element={
          <ProtectedRoute>
            <MainLayout
              activeView={activeView}
              onViewChange={setActiveView}
              children={renderDashboardContent()}
            />
          </ProtectedRoute>
        }
      />

      {/* Catch all - check auth and redirect accordingly */}
      <Route path="*" element={<CatchAllRoute />} />
    </Routes>
    </>
  );
}

/** Root App component with providers */
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <PlannerSettingsProvider>
          <PlannerWorkspaceProvider>
            <AppContent />
          </PlannerWorkspaceProvider>
        </PlannerSettingsProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
