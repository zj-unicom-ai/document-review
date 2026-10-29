// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { Button } from "../components/Button";
import { Field, TextInput } from "../components/Field";
import { ErrorBanner } from "../components/StateBlocks";
import { useAuth } from "./AuthProvider";

export function LoginPage() {
  const { loading, user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  const redirectTo =
    location.state && typeof location.state === "object" && "from" in location.state
      ? String((location.state as { from?: unknown }).from ?? "/")
      : "/";

  if (!loading && user) {
    return <Navigate to={redirectTo} replace />;
  }

  return (
    <main className="login-page">
      <div className="login-panel">
        <span className="login-seal" aria-hidden="true">
          审
        </span>
        <header className="login-head">
          <h1>文档智能审查平台</h1>
          <p>规则驱动的文档审查引擎</p>
        </header>
        <div className="login-rule" aria-hidden="true" />
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            setPending(true);
            setError("");
            try {
              await login(username, password);
              navigate(redirectTo, { replace: true });
            } catch (loginError) {
              setError(loginError instanceof Error ? loginError.message : String(loginError));
            } finally {
              setPending(false);
            }
          }}
        >
          <ErrorBanner error={error} title="登录失败" />
          <Field label="用户名">
            <TextInput
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
            />
          </Field>
          <Field label="密码">
            <TextInput
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
            />
          </Field>
          <Button type="submit" variant="primary" className="login-submit" disabled={pending || loading}>
            {pending ? "登录中" : "登录"}
          </Button>
        </form>
        <p className="login-note">平台管理员与租户用户均由此入口登录</p>
      </div>
    </main>
  );
}
