import React, { useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { BottomNav } from './components/BottomNav';
import { ProtectedRoute } from './components/ProtectedRoute';
import { NotificationDrawer } from './components/NotificationDrawer';

import { LoginView } from './views/LoginView';
import { RegisterView } from './views/RegisterView';
import { ChatView } from './views/ChatView';
import { SchemesView } from './views/SchemesView';
import { SchemeDetailView } from './views/SchemeDetailView';
import { DocumentsView } from './views/DocumentsView';
import { ApplicationsView } from './views/ApplicationsView';
import { TrackingView } from './views/TrackingView';
import { ProfileView } from './views/ProfileView';

export const App: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const [isNotificationOpen, setIsNotificationOpen] = useState(false);

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900 antialiased font-sans">
      {/* Top Navigation Bar */}
      <Navbar onOpenNotifications={() => setIsNotificationOpen(true)} />

      {/* Main Content Area with responsive padding for mobile bottom bar */}
      <main className="flex-1 w-full pb-16 md:pb-6">
        <Routes>
          {/* Public Authentication Routes */}
          <Route
            path="/login"
            element={isAuthenticated ? <Navigate to="/" replace /> : <LoginView />}
          />
          <Route
            path="/register"
            element={isAuthenticated ? <Navigate to="/" replace /> : <RegisterView />}
          />

          {/* Protected Citizen Routes */}
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<ChatView />} />
            <Route path="/schemes" element={<SchemesView />} />
            <Route path="/schemes/:id" element={<SchemeDetailView />} />
            <Route path="/documents" element={<DocumentsView />} />
            <Route path="/applications" element={<ApplicationsView />} />
            <Route path="/tracking" element={<TrackingView />} />
            <Route path="/profile" element={<ProfileView />} />
          </Route>

          {/* Catch-all fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      {/* Mobile Bottom Tab Bar */}
      {isAuthenticated && <BottomNav />}

      {/* Slide-out Notification Center Drawer */}
      {isAuthenticated && (
        <NotificationDrawer
          isOpen={isNotificationOpen}
          onClose={() => setIsNotificationOpen(false)}
        />
      )}
    </div>
  );
};

export default App;
