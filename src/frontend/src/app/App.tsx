import { useCallback, useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router";

import { getCurrentUser, isAccountApiError } from "@/features/account/api/accountApi";
import { LoginPage } from "@/features/account/components/LoginPage";
import { RegisterPage } from "@/features/account/components/RegisterPage";
import type { AccountUser } from "@/features/account/model/types";
import { SettingsDialog } from "@/features/settings/components/SettingsDialog";
import { ChatPage } from "@/pages/chat/ChatPage";
import { Providers } from "./providers";

function App() {
  return (
    <Providers>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </Providers>
  );
}

export default App;

function AppRoutes() {
  const navigate = useNavigate();
  const [currentUser, setCurrentUser] = useState<AccountUser | null | undefined>(undefined);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const handleUnauthorized = useCallback(() => {
    setSettingsOpen(false);
    setCurrentUser(null);
    navigate("/login", { replace: true });
  }, [navigate]);

  const handleLoggedOut = useCallback(() => {
    setSettingsOpen(false);
    setCurrentUser(null);
    navigate("/login", { replace: true });
  }, [navigate]);

  return (
    <>
      <Routes>
        <Route
          path="/"
          element={
            <ProtectedChatPage
              currentUser={currentUser}
              onCurrentUserChange={setCurrentUser}
              onOpenSettings={() => setSettingsOpen(true)}
              onUnauthorized={handleUnauthorized}
            />
          }
        />
        <Route path="/login" element={<LoginPage onAuthenticated={setCurrentUser} />} />
        <Route path="/register" element={<RegisterPage onAuthenticated={setCurrentUser} />} />
        <Route path="*" element={<Navigate replace to="/" />} />
      </Routes>
      {currentUser ? (
        <SettingsDialog
          open={settingsOpen}
          user={currentUser}
          onLoggedOut={handleLoggedOut}
          onOpenChange={setSettingsOpen}
          onUserChange={setCurrentUser}
        />
      ) : null}
    </>
  );
}

function ProtectedChatPage({
  currentUser,
  onCurrentUserChange,
  onOpenSettings,
  onUnauthorized,
}: {
  currentUser: AccountUser | null | undefined;
  onCurrentUserChange: (user: AccountUser | null) => void;
  onOpenSettings: () => void;
  onUnauthorized: () => void;
}) {
  const navigate = useNavigate();

  useEffect(() => {
    if (currentUser !== undefined) {
      return;
    }

    let cancelled = false;
    void getCurrentUser()
      .then((authenticatedUser) => {
        if (!cancelled) {
          onCurrentUserChange(authenticatedUser);
        }
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        onCurrentUserChange(null);
        if (isAccountApiError(error) && error.status !== 401) {
          return;
        }
        navigate("/login", { replace: true });
      });

    return () => {
      cancelled = true;
    };
  }, [currentUser, navigate, onCurrentUserChange]);

  if (currentUser === undefined) {
    return <div className="p-8 text-sm text-[var(--dc-muted)]">ログイン状態を確認しています。</div>;
  }

  if (currentUser === null) {
    return <Navigate replace to="/login" />;
  }

  return (
    <ChatPage
      currentUser={currentUser}
      onOpenAccountSettings={onOpenSettings}
      onUnauthorized={onUnauthorized}
    />
  );
}
