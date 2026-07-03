"use client";

import { FormEvent, useEffect, useState } from "react";
import { Pencil } from "lucide-react";
import { AppShell } from "@/components/Sidebar";
import { FieldLabel, HelpTip } from "@/components/HelpTip";
import { PasswordInput } from "@/components/PasswordInput";
import {
  createLlmModel,
  createLlmProvider,
  listLlmModels,
  listLlmProviders,
  updateLlmModel,
  updateLlmProvider,
} from "@/lib/api";

type Provider = { id: number; name: string; provider_type: string; active: boolean; api_key_preview: string };
type Model = {
  id: number;
  provider_id: number;
  model_id: string;
  display_name: string;
  cost_per_1m_input: number;
  cost_per_1m_output: number;
};

export default function LlmSettingsPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [providerName, setProviderName] = useState("OpenAI");
  const [apiKey, setApiKey] = useState("");
  const [modelId, setModelId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [providerId, setProviderId] = useState<number | "">("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [editingProvider, setEditingProvider] = useState<Provider | null>(null);
  const [editProviderName, setEditProviderName] = useState("");
  const [editProviderKey, setEditProviderKey] = useState("");
  const [editProviderKeyPreview, setEditProviderKeyPreview] = useState("");
  const [editProviderActive, setEditProviderActive] = useState(true);

  const [editingModel, setEditingModel] = useState<Model | null>(null);
  const [editModelRef, setEditModelRef] = useState("");
  const [editProviderId, setEditProviderId] = useState<number | "">("");
  const [editDisplayName, setEditDisplayName] = useState("");
  const [editCostIn, setEditCostIn] = useState("");
  const [editCostOut, setEditCostOut] = useState("");

  async function refresh() {
    const [p, m] = await Promise.all([listLlmProviders(), listLlmModels()]);
    setProviders(p);
    setModels(m);
    if (p.length && providerId === "") setProviderId(p[0].id);
  }

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      window.location.href = "/login";
      return;
    }
    refresh().catch(() => {});
  }, []);

  async function handleProvider(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await createLlmProvider(providerName, apiKey);
      setMessage("Provedor criado");
      setApiKey("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar provedor");
    }
  }

  async function handleModel(e: FormEvent) {
    e.preventDefault();
    if (!providerId) return;
    setError("");
    try {
      await createLlmModel({
        provider_id: Number(providerId),
        model_id: modelId,
        display_name: displayName || modelId,
      });
      setMessage("Modelo criado");
      setModelId("");
      setDisplayName("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar modelo");
    }
  }

  async function saveProviderEdit(e: FormEvent) {
    e.preventDefault();
    if (!editingProvider) return;
    await updateLlmProvider(editingProvider.id, {
      name: editProviderName,
      api_key: editProviderKey || undefined,
      active: editProviderActive,
    });
    setEditingProvider(null);
    setMessage("Provedor atualizado");
    await refresh();
  }

  async function saveModelEdit(e: FormEvent) {
    e.preventDefault();
    if (!editingModel) return;
    await updateLlmModel(editingModel.id, {
      provider_id: editProviderId === "" ? undefined : Number(editProviderId),
      model_id: editModelRef,
      display_name: editDisplayName,
      cost_per_1m_input: parseFloat(editCostIn) || 0,
      cost_per_1m_output: parseFloat(editCostOut) || 0,
    });
    setEditingModel(null);
    setMessage("Modelo atualizado");
    await refresh();
  }

  function getProviderName(providerId: number) {
    return providers.find((p) => p.id === providerId)?.name ?? "—";
  }

  return (
    <AppShell>
      <h1 className="mb-2 text-xl font-semibold text-gray-900 sm:text-2xl">Modelos LLM</h1>
      <p className="mb-8 text-sm text-gray-500">
        Cadastre provedores (OpenAI, etc.) e os modelos que os clientes podem usar.
      </p>

      {message && <p className="mb-4 text-sm text-green-700">{message}</p>}
      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      <div className="grid gap-8 lg:grid-cols-2">
        <form onSubmit={handleProvider} className="card space-y-4">
          <h2 className="flex items-center gap-2 font-semibold text-gray-900">
            Novo provedor
            <HelpTip text="Provedor de IA que fornece os modelos. Ex.: OpenAI com sua API Key em platform.openai.com." />
          </h2>
          <div>
            <FieldLabel label="Nome" help="Nome exibido no painel. Ex.: OpenAI, Anthropic." />
            <input className="input-field" value={providerName} onChange={(e) => setProviderName(e.target.value)} />
          </div>
          <div>
            <FieldLabel label="API Key" help="Chave secreta do provedor. Fica criptografada no banco." />
            <PasswordInput value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
          </div>
          <button type="submit" className="btn-primary">
            Adicionar provedor
          </button>
        </form>

        <form onSubmit={handleModel} className="card space-y-4">
          <h2 className="flex items-center gap-2 font-semibold text-gray-900">
            Novo modelo
            <HelpTip text="Cada modelo corresponde a um ID da API do provedor, ex.: gpt-4o-mini." />
          </h2>
          <div>
            <FieldLabel label="Provedor" help="Provedor ao qual este modelo pertence." />
            <select className="input-field" value={providerId} onChange={(e) => setProviderId(Number(e.target.value))}>
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <FieldLabel label="ID do modelo" help="Identificador exato na API. Ex.: gpt-4o-mini, gpt-4.1." />
            <input className="input-field" value={modelId} onChange={(e) => setModelId(e.target.value)} placeholder="gpt-4o-mini" />
          </div>
          <div>
            <FieldLabel label="Nome de exibição" help="Nome amigável mostrado nos selects do painel." />
            <input className="input-field" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="GPT-4o Mini" />
          </div>
          <button type="submit" className="btn-primary">
            Adicionar modelo
          </button>
        </form>
      </div>

      <div className="card mt-8">
        <h2 className="mb-4 flex items-center gap-2 font-semibold text-gray-900">
          Provedores cadastrados
          <HelpTip text="Clique em Editar para alterar nome, API Key ou desativar o provedor." />
        </h2>
        <div className="table-wrap">
        <table className="mb-8 w-full min-w-[400px] text-sm">
          <thead className="text-left text-xs uppercase text-gray-500">
            <tr>
              <th className="pb-2">Nome</th>
              <th className="pb-2">Tipo</th>
              <th className="pb-2">Status</th>
              <th className="pb-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {providers.map((p) => (
              <tr key={p.id}>
                <td className="py-2 font-medium">{p.name}</td>
                <td className="py-2 text-gray-500">{p.provider_type}</td>
                <td className="py-2">{p.active ? "Ativo" : "Inativo"}</td>
                <td className="py-2 text-right">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 text-brand-600"
                    onClick={() => {
                      setEditingProvider(p);
                      setEditProviderName(p.name);
                      setEditProviderKey("");
                      setEditProviderKeyPreview(p.api_key_preview || "");
                      setEditProviderActive(p.active);
                    }}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                    Editar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>

        <h2 className="mb-4 flex items-center gap-2 font-semibold text-gray-900">
          Modelos cadastrados
          <HelpTip text="Modelos disponíveis para associar aos clientes. Edite custos para métricas mais precisas." />
        </h2>
        <div className="table-wrap">
        <table className="w-full min-w-[560px] text-sm">
          <thead className="text-left text-xs uppercase text-gray-500">
            <tr>
              <th className="pb-2">Nome</th>
              <th className="pb-2">Provedor</th>
              <th className="pb-2">ID</th>
              <th className="pb-2">Custo in/out (1M)</th>
              <th className="pb-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {models.map((m) => (
              <tr key={m.id}>
                <td className="py-2">{m.display_name}</td>
                <td className="py-2 text-gray-600">{getProviderName(m.provider_id)}</td>
                <td className="py-2 text-gray-500">{m.model_id}</td>
                <td className="py-2 text-gray-500">
                  ${m.cost_per_1m_input} / ${m.cost_per_1m_output}
                </td>
                <td className="py-2 text-right">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 text-brand-600"
                    onClick={() => {
                      setEditingModel(m);
                      setEditProviderId(m.provider_id);
                      setEditModelRef(m.model_id);
                      setEditDisplayName(m.display_name);
                      setEditCostIn(String(m.cost_per_1m_input));
                      setEditCostOut(String(m.cost_per_1m_output));
                    }}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                    Editar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      {editingProvider && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <form onSubmit={saveProviderEdit} className="card mx-4 max-h-[90vh] w-full max-w-md space-y-4 overflow-y-auto">
            <h3 className="font-semibold">Editar provedor</h3>
            <div>
              <FieldLabel label="Nome" help="Nome exibido no painel." />
              <input className="input-field" value={editProviderName} onChange={(e) => setEditProviderName(e.target.value)} />
            </div>
            <div>
              <FieldLabel label="API Key atual" help="Chave configurada no provedor (parcialmente mascarada por segurança)." />
              <input
                className="input-field bg-gray-50 font-mono text-sm"
                value={editProviderKeyPreview || "Nenhuma chave cadastrada"}
                readOnly
              />
            </div>
            <div>
              <FieldLabel label="Nova API Key" help="Deixe em branco para manter a chave atual." />
              <PasswordInput value={editProviderKey} onChange={(e) => setEditProviderKey(e.target.value)} />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={editProviderActive} onChange={(e) => setEditProviderActive(e.target.checked)} />
              Provedor ativo
            </label>
            <div className="flex gap-2">
              <button type="button" className="btn-secondary flex-1" onClick={() => setEditingProvider(null)}>
                Cancelar
              </button>
              <button type="submit" className="btn-primary flex-1">
                Salvar
              </button>
            </div>
          </form>
        </div>
      )}

      {editingModel && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <form onSubmit={saveModelEdit} className="card mx-4 max-h-[90vh] w-full max-w-md space-y-4 overflow-y-auto">
            <h3 className="font-semibold">Editar modelo</h3>
            <div>
              <FieldLabel label="Provedor" help="Provedor ao qual este modelo pertence." />
              <select
                className="input-field"
                value={editProviderId}
                onChange={(e) => setEditProviderId(Number(e.target.value))}
              >
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <FieldLabel label="ID do modelo" help="Identificador na API do provedor." />
              <input className="input-field" value={editModelRef} onChange={(e) => setEditModelRef(e.target.value)} />
            </div>
            <div>
              <FieldLabel label="Nome de exibição" help="Nome mostrado nos selects." />
              <input className="input-field" value={editDisplayName} onChange={(e) => setEditDisplayName(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <FieldLabel label="Custo input/1M" help="USD por 1 milhão de tokens de entrada." />
                <input className="input-field" value={editCostIn} onChange={(e) => setEditCostIn(e.target.value)} />
              </div>
              <div>
                <FieldLabel label="Custo output/1M" help="USD por 1 milhão de tokens de saída." />
                <input className="input-field" value={editCostOut} onChange={(e) => setEditCostOut(e.target.value)} />
              </div>
            </div>
            <div className="flex gap-2">
              <button type="button" className="btn-secondary flex-1" onClick={() => setEditingModel(null)}>
                Cancelar
              </button>
              <button type="submit" className="btn-primary flex-1">
                Salvar
              </button>
            </div>
          </form>
        </div>
      )}
    </AppShell>
  );
}
