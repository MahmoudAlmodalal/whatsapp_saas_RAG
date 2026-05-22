import { Switch, Route, Router as WouterRouter, Redirect } from "wouter";
import QueryProvider from "@/components/QueryProvider";
import { AuthProvider, useAuth } from "@/components/AuthProvider";
import { SuperAdminProvider, useSuperAdmin } from "@/components/SuperAdminProvider";
import DashboardLayout from "@/layouts/DashboardLayout";
import SuperAdminLayout from "@/layouts/SuperAdminLayout";
import LoginPage from "@/pages/LoginPage";
import OverviewPage from "@/pages/dashboard/OverviewPage";
import ConversationsPage from "@/pages/dashboard/ConversationsPage";
import ConversationDetailPage from "@/pages/dashboard/ConversationDetailPage";
import DocumentsPage from "@/pages/dashboard/DocumentsPage";
import IntegrationPage from "@/pages/dashboard/IntegrationPage";
import SettingsPage from "@/pages/dashboard/SettingsPage";
import TenantsPage from "@/pages/superadmin/TenantsPage";
import AccountsPage from "@/pages/superadmin/AccountsPage";
import SystemSettingsPage from "@/pages/superadmin/SystemSettingsPage";

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Redirect to="/login" />;
  return <>{children}</>;
}

function GuestGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Redirect to="/dashboard/overview" />;
  return <>{children}</>;
}


function AppRoutes() {
  return (
    <Switch>
      <Route path="/login">
        <GuestGuard>
          <LoginPage />
        </GuestGuard>
      </Route>

      <Route path="/super-admin/dashboard/tenants">
        <SuperAdminLayout>
          <TenantsPage />
        </SuperAdminLayout>
      </Route>

      <Route path="/super-admin/dashboard/accounts">
        <SuperAdminLayout>
          <AccountsPage />
        </SuperAdminLayout>
      </Route>

      <Route path="/super-admin/dashboard/settings">
        <SuperAdminLayout>
          <SystemSettingsPage />
        </SuperAdminLayout>
      </Route>

      <Route path="/super-admin/dashboard">
        <Redirect to="/super-admin/dashboard/tenants" />
      </Route>

      <Route path="/super-admin">
        <Redirect to="/login" />
      </Route>

      <Route path="/dashboard/overview">
        <AuthGuard>
          <DashboardLayout>
            <OverviewPage />
          </DashboardLayout>
        </AuthGuard>
      </Route>

      <Route path="/dashboard/conversations">
        <AuthGuard>
          <DashboardLayout>
            <ConversationsPage />
          </DashboardLayout>
        </AuthGuard>
      </Route>

      <Route path="/dashboard/conversations/:id">
        {(params) => (
          <AuthGuard>
            <DashboardLayout>
              <ConversationDetailPage convId={params.id} />
            </DashboardLayout>
          </AuthGuard>
        )}
      </Route>

      <Route path="/dashboard/documents">
        <AuthGuard>
          <DashboardLayout>
            <DocumentsPage />
          </DashboardLayout>
        </AuthGuard>
      </Route>

      <Route path="/dashboard/integration">
        <AuthGuard>
          <DashboardLayout>
            <IntegrationPage />
          </DashboardLayout>
        </AuthGuard>
      </Route>

      <Route path="/dashboard/settings">
        <AuthGuard>
          <DashboardLayout>
            <SettingsPage />
          </DashboardLayout>
        </AuthGuard>
      </Route>

      <Route path="/dashboard">
        <Redirect to="/dashboard/overview" />
      </Route>

      <Route>
        <Redirect to="/dashboard/overview" />
      </Route>
    </Switch>
  );
}

function App() {
  return (
    <QueryProvider>
      <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, "")}>
        <AuthProvider>
          <SuperAdminProvider>
            <AppRoutes />
          </SuperAdminProvider>
        </AuthProvider>
      </WouterRouter>
    </QueryProvider>
  );
}

export default App;
