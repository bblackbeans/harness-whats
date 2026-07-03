"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { login } from "@/lib/api";
import { FieldLabel } from "@/components/HelpTip";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const tokens = await login(email, password);
      localStorage.setItem("access_token", tokens.access_token);
      router.push("/");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Falha no login";
      setError(
        msg === "Credenciais inválidas"
          ? "Email ou senha incorretos. Se você é cliente, use o Portal do Cliente (link abaixo)."
          : msg
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="card w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 text-lg font-bold text-white">
            H
          </div>
          <h1 className="text-2xl font-semibold text-gray-900">Harness Admin</h1>
          <p className="mt-1 text-sm text-gray-500">Plataforma SaaS de Agentes IA</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4" autoComplete="off">
          <div>
            <FieldLabel
              label="Email"
              help="Email do administrador da plataforma. Ex.: admin@harness.local"
            />
            <input
              type="email"
              name="admin-email"
              className="input-field"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="off"
              required
            />
          </div>
          <div>
            <FieldLabel label="Senha" help="Senha definida na configuração do servidor (ADMIN_PASSWORD)." />
            <input
              type="password"
              name="admin-password"
              className="input-field"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              required
            />
          </div>
          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
          )}
          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? "Entrando..." : "Entrar"}
          </button>
        </form>
        <p className="mt-6 text-center text-sm text-gray-500">
          É cliente?{" "}
          <Link href="/portal/login" className="font-medium text-brand-600 hover:text-brand-700">
            Acessar portal do cliente
          </Link>
        </p>
      </div>
    </div>
  );
}
