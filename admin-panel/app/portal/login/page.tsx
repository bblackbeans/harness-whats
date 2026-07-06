"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { portalLogin } from "@/lib/portal-api";
import { FieldLabel } from "@/components/HelpTip";
import { PasswordInput } from "@/components/PasswordInput";

export default function PortalLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    localStorage.removeItem("access_token");
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const tokens = await portalLogin(email.trim(), password);
      localStorage.setItem("portal_access_token", tokens.access_token);
      router.replace("/portal");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Falha no login";
      setError(
        msg.includes("Credenciais") || msg.includes("Acesso não encontrado")
          ? "Email ou senha incorretos. Se o cliente foi criado antes da atualização, peça ao admin para cadastrar o acesso em Clientes → Acesso ao portal."
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
          <h1 className="text-2xl font-semibold text-gray-900">Portal do Cliente</h1>
          <p className="mt-1 text-sm text-gray-500">
            Personalize como seu chatbot responde e o conteúdo que ele usa nas conversas
          </p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4" autoComplete="off">
          <div>
            <FieldLabel
              label="Email"
              help="Email cadastrado pelo administrador ao criar o cliente ou na aba Acesso ao portal."
            />
            <input
              type="email"
              name="portal-email"
              className="input-field"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="off"
              placeholder="seu@email.com"
              required
            />
          </div>
          <div>
            <FieldLabel label="Senha" help="Senha definida pelo administrador no cadastro do cliente." />
            <PasswordInput
              name="portal-password"
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
          É administrador?{" "}
          <Link href="/login" className="font-medium text-brand-600 hover:text-brand-700">
            Acessar painel admin
          </Link>
        </p>
      </div>
    </div>
  );
}
