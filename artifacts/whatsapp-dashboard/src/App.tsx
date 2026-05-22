import { Switch, Route, Router as WouterRouter, Redirect } from "wouter";
import QueryProvider from "@/components/QueryProvider";
import { AuthProvider, useAuth } from "@/components/AuthProvider";
import DashboardLayout from "@/layouts/DashboardLayout";
import LoginPage from "@/pages/LoginPage";
import OverviewPage from "@/pages/dashboard/OverviewPage";
import DocumentsPage from "@/pages/dashboard/DocumentsPage";
import HandoffsPage from "@/pages/dashboard/HandoffsPage";
import ConversationsPage from "@/pages/dashboard/ConversationsPage";
import IntegrationPage from "@/pages/dashboard/IntegrationPage";
import SettingsPage from "@/pages/dashboard/SettingsPage";

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
        <GuestGuard><LoginPage /></GuestGuard>
      </Route>

      <Route path="/dashboard/overview">
        <AuthGuard><DashboardLayout><OverviewPage /></DashboardLayout></AuthGuard>
      </Route>

      <Route path="/dashboard/documents">
        <AuthGuard><DashboardLayout><DocumentsPage /></DashboardLayout></AuthGuard>
      </Route>

      <Route path="/dashboard/handoffs">
        <AuthGuard><DashboardLayout><HandoffsPage /></DashboardLayout></AuthGuard>
      </Route>

      <Route path="/dashboard/conversations">
        <AuthGuard><DashboardLayout><ConversationsPage /></DashboardLayout></AuthGuard>
      </Route>

      <Route path="/dashboard/integration">
        <AuthGuard><DashboardLayout><IntegrationPage /></DashboardLayout></AuthGuard>
      </Route>

      <Route path="/dashboard/settings">
        <AuthGuard><DashboardLayout><SettingsPage /></DashboardLayout></AuthGuard>
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
          <AppRoutes />
        </AuthProvider>
      </WouterRouter>
    </QueryProvider>
  );
}

export default App;
