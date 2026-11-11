import { createBrowserRouter } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
import { LandingPage } from '@/pages/LandingPage';
import { SchemesPage } from '@/pages/SchemesPage';
import { EligiblePage } from '@/pages/EligiblePage';
import { SchemeDetailsPage } from '@/pages/SchemeDetailsPage';
import { ChatPage } from '@/pages/ChatPage';
import { DocumentsPage } from '@/pages/DocumentsPage';
import { ApplicationsPage } from '@/pages/ApplicationsPage';
import { OnboardingPage } from '@/pages/OnboardingPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { NotFoundPage } from '@/pages/NotFoundPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: 'schemes', element: <SchemesPage /> },
      { path: 'eligible', element: <EligiblePage /> },
      { path: 'schemes/:id', element: <SchemeDetailsPage /> },
      { path: 'chat', element: <ChatPage /> },
      { path: 'documents', element: <DocumentsPage /> },
      { path: 'applications', element: <ApplicationsPage /> },
      { path: 'onboarding', element: <OnboardingPage /> },
      { path: 'dashboard', element: <DashboardPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
