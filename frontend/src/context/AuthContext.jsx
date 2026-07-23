import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { demoLoginRequest, fetchCurrentUser, loginRequest, registerRequest } from '../api/client';
import { clearSession, readSession, writeSession } from '../auth/session';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(() => readSession());
  const [restoring, setRestoring] = useState(Boolean(readSession()));

  useEffect(() => {
    if (!session) {
      setRestoring(false);
      return;
    }
    let active = true;
    fetchCurrentUser()
      .then((user) => active && setSession((current) => current ? { ...current, user } : current))
      .catch(() => {
        clearSession();
        if (active) setSession(null);
      })
      .finally(() => active && setRestoring(false));
    return () => { active = false; };
  }, []);

  const acceptToken = useCallback((response) => {
    const next = writeSession(response);
    setSession(next);
    return next.user;
  }, []);

  const login = useCallback(async (credentials) => acceptToken(await loginRequest(credentials)), [acceptToken]);
  const enterDemo = useCallback(async (role) => acceptToken(await demoLoginRequest(role)), [acceptToken]);
  const register = useCallback(async (details) => {
    await registerRequest(details);
    return login({ email: details.email, password: details.password });
  }, [login]);
  const logout = useCallback(() => {
    clearSession();
    setSession(null);
  }, []);

  const value = useMemo(() => ({
    user: session?.user || null,
    accessToken: session?.accessToken || null,
    isAuthenticated: Boolean(session?.accessToken),
    restoring,
    login,
    register,
    enterDemo,
    logout,
  }), [session, restoring, login, register, enterDemo, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used within AuthProvider');
  return value;
}
