import React from 'react';
import type { Connector } from '../types/api';

interface LlmModalProps {
  open: boolean;
  provider: string;
  model: string;
  apiKey: string;
  onChangeProvider: (provider: string, defaultModel: string) => void;
  onChangeModel: (model: string) => void;
  onChangeApiKey: (key: string) => void;
  onClose: () => void;
  onSave: () => void;
}

export const LlmSettingsModal: React.FC<LlmModalProps> = ({
  open,
  provider,
  model,
  apiKey,
  onChangeProvider,
  onChangeModel,
  onChangeApiKey,
  onClose,
  onSave,
}) => {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-bold text-slate-900 dark:text-white">
            Configure AI Copilot Model & API Key
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-sm">
            ✕
          </button>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
          All physical fault localization, OTDR binary parsing, and SRLG graph audits run
          deterministically. Provide an Anthropic or OpenAI key to enable live LLM narrative
          generation on top of the verified evidence bundle.
        </p>
        <div className="space-y-3 text-xs">
          <div>
            <label className="block font-semibold mb-1">Provider</label>
            <select
              value={provider}
              onChange={(e) => {
                const next = e.target.value;
                onChangeProvider(next, next === 'anthropic' ? 'claude-sonnet-4-20250514' : 'gpt-4o');
              }}
              className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2"
            >
              <option value="anthropic">Anthropic Claude</option>
              <option value="openai">OpenAI GPT</option>
            </select>
          </div>
          <div>
            <label className="block font-semibold mb-1">Model Name</label>
            <input
              type="text"
              value={model}
              onChange={(e) => onChangeModel(e.target.value)}
              className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2 font-mono"
            />
          </div>
          <div>
            <label className="block font-semibold mb-1">API Key</label>
            <input
              type="password"
              placeholder="sk-ant-... or sk-..."
              value={apiKey}
              onChange={(e) => onChangeApiKey(e.target.value)}
              className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2 font-mono"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-xs font-medium"
          >
            Cancel
          </button>
          <button
            onClick={onSave}
            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold"
          >
            Save & Regenerate Brief
          </button>
        </div>
      </div>
    </div>
  );
};

interface ConnectorEditorModalProps {
  connector: Connector | null;
  endpointUrl: string;
  mode: string;
  onChangeEndpointUrl: (url: string) => void;
  onChangeMode: (mode: string) => void;
  onClose: () => void;
  onSave: () => void;
}

export const ConnectorEditorModal: React.FC<ConnectorEditorModalProps> = ({
  connector,
  endpointUrl,
  mode,
  onChangeEndpointUrl,
  onChangeMode,
  onClose,
  onSave,
}) => {
  if (!connector) return null;
  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-xl space-y-4">
        <h3 className="text-base font-bold text-slate-900 dark:text-white">
          Configure {connector.name}
        </h3>
        <div className="space-y-3 text-xs">
          <div>
            <label className="block font-semibold mb-1">Connection Mode</label>
            <select
              value={mode}
              onChange={(e) => onChangeMode(e.target.value)}
              className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2"
            >
              <option value="emulator">Protocol-Authentic Local Emulator</option>
              <option value="live">Live Customer Production / Lab Endpoint</option>
            </select>
          </div>
          <div>
            <label className="block font-semibold mb-1">Endpoint Base URL</label>
            <input
              type="text"
              value={endpointUrl}
              onChange={(e) => onChangeEndpointUrl(e.target.value)}
              className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2 font-mono"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-xs font-medium"
          >
            Cancel
          </button>
          <button
            onClick={onSave}
            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold"
          >
            Save & Sync Connector
          </button>
        </div>
      </div>
    </div>
  );
};
