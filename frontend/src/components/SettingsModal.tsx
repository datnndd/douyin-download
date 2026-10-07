// frontend/src/components/SettingsModal.tsx

import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  Check,
  Cpu,
  Database,
  FileCode,
  Folder,
  Key,
  Loader2,
  Save,
  Settings,
  Sliders,
  X,
} from 'lucide-react';
import { SettingsModel } from '../types/api';
import { api } from '../services/api';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSaved?: (settings: SettingsModel) => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  onSaved,
}) => {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState<SettingsModel | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadSettings();
      setSaveSuccess(false);
      setError(null);
    }
  }, [isOpen]);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const data = await api.getSettings();
      setSettings(data);
    } catch (err: any) {
      setError(err.message || '加载配置失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!settings) return;

    setSaving(true);
    setError(null);
    setSaveSuccess(false);

    try {
      const updated = await api.saveSettings(settings);
      setSettings(updated);
      setSaveSuccess(true);
      if (onSaved) onSaved(updated);
      setTimeout(() => {
        setSaveSuccess(false);
      }, 3000);
    } catch (err: any) {
      setError(err.message || '保存设置失败');
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 animate-fadeIn">
      <div className="bg-[#FAF8F5] border border-[#E5DED4] rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden shadow-2xl flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 bg-white border-b border-[#E5DED4] flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-xl bg-[#F3ECE2] flex items-center justify-center text-[#8D4B00]">
              <Settings className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-[#1F2328]">下载与系统配置</h2>
              <p className="text-[11px] text-[#595E68]">修改并持久化保存至本地 config.yaml</p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[#898174] hover:text-[#1F2328] hover:bg-[#F3ECE2] transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto flex-1 space-y-5">
          {loading ? (
            <div className="py-16 flex flex-col items-center justify-center space-y-2">
              <Loader2 className="w-6 h-6 text-[#8D4B00] animate-spin" />
              <span className="text-xs text-[#595E68]">读取配置中...</span>
            </div>
          ) : settings ? (
            <form id="settings-form" onSubmit={handleSave} className="space-y-5">
              {/* Download Path */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-[#1F2328] flex items-center space-x-1.5">
                  <Folder className="w-3.5 h-3.5 text-[#8D4B00]" />
                  <span>默认下载存储路径 (path)</span>
                </label>
                <input
                  type="text"
                  value={settings.path}
                  onChange={(e) => setSettings({ ...settings, path: e.target.value })}
                  className="w-full px-3.5 py-2 rounded-xl border border-[#E5DED4] bg-white text-xs font-mono text-[#1F2328] focus:outline-none focus:border-[#8D4B00]"
                  placeholder="./Downloaded/"
                />
                <p className="text-[11px] text-[#595E68]">
                  支持相对路径（如 ./Downloaded/）或绝对路径（如 D:\DouyinDownloads\）
                </p>
              </div>

              {/* Filename Template */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-[#1F2328] flex items-center space-x-1.5">
                  <FileCode className="w-3.5 h-3.5 text-[#8D4B00]" />
                  <span>Định dạng tên file mặc định (filename_template)</span>
                </label>
                <input
                  type="text"
                  value={settings.filename_template || '{date}_{title}_{id}'}
                  onChange={(e) =>
                    setSettings({ ...settings, filename_template: e.target.value })
                  }
                  className="w-full px-3.5 py-2 rounded-xl border border-[#E5DED4] bg-white text-xs font-mono text-[#1F2328] focus:outline-none focus:border-[#8D4B00]"
                  placeholder="{date}_{title}_{id}"
                />
                <p className="text-[11px] text-[#595E68]">
                  Các thẻ hỗ trợ: <code>{'{date}'}</code>, <code>{'{title}'}</code>, <code>{'{id}'}</code>, <code>{'{author}'}</code>, <code>{'{likes}'}</code>
                </p>
              </div>

              {/* Thread Concurrency */}
              <div className="space-y-2 p-4 rounded-xl bg-white border border-[#E5DED4]">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-[#1F2328] flex items-center space-x-1.5">
                    <Cpu className="w-3.5 h-3.5 text-[#8D4B00]" />
                    <span>默认下载并发线程数 (thread)</span>
                  </label>
                  <span className="font-mono text-xs font-bold text-[#8D4B00] px-2 py-0.5 rounded bg-[#F3ECE2]">
                    {settings.thread} 线程
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <span className="text-[11px] font-mono text-[#898174]">1</span>
                  <input
                    type="range"
                    min={1}
                    max={32}
                    value={settings.thread}
                    onChange={(e) =>
                      setSettings({ ...settings, thread: Number(e.target.value) })
                    }
                    className="flex-1 accent-[#8D4B00] h-1.5 bg-[#E5DED4] rounded-lg cursor-pointer"
                  />
                  <span className="text-[11px] font-mono text-[#898174]">32</span>
                </div>
              </div>

              {/* Raw Cookie Input */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-[#1F2328] flex items-center space-x-1.5">
                  <Key className="w-3.5 h-3.5 text-[#8D4B00]" />
                  <span>抖音认证 Cookie (cookies)</span>
                </label>
                <textarea
                  rows={4}
                  value={settings.raw_cookie || ''}
                  onChange={(e) => setSettings({ ...settings, raw_cookie: e.target.value })}
                  placeholder="odin_tt=...; sessionid_ss=...; passport_csrf_token=... (可在网页登录后按 F12 网络请求中复制 Cookie 头)"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-[#E5DED4] bg-white text-xs font-mono text-[#1F2328] focus:outline-none focus:border-[#8D4B00] resize-none"
                />
                <p className="text-[11px] text-[#595E68]">
                  下载他人公开作品通常无需登录；若需下载创作者点赞作品或无水印最高画质原片，建议填写有效 Cookie。
                </p>
              </div>

              {/* Default Asset Toggles */}
              <div className="p-4 rounded-xl bg-white border border-[#E5DED4] space-y-3">
                <label className="text-xs font-semibold text-[#1F2328] flex items-center space-x-1.5">
                  <Sliders className="w-3.5 h-3.5 text-[#8D4B00]" />
                  <span>默认下载选项开关</span>
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                  <label className="flex items-center space-x-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={settings.music}
                      onChange={(e) => setSettings({ ...settings, music: e.target.checked })}
                      className="accent-[#8D4B00] w-4 h-4 rounded"
                    />
                    <span>保存背景音频 (music)</span>
                  </label>

                  <label className="flex items-center space-x-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={settings.cover}
                      onChange={(e) => setSettings({ ...settings, cover: e.target.checked })}
                      className="accent-[#8D4B00] w-4 h-4 rounded"
                    />
                    <span>保存封面原图 (cover)</span>
                  </label>

                  <label className="flex items-center space-x-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={settings.avatar}
                      onChange={(e) => setSettings({ ...settings, avatar: e.target.checked })}
                      className="accent-[#8D4B00] w-4 h-4 rounded"
                    />
                    <span>保存作者头像 (avatar)</span>
                  </label>

                  <label className="flex items-center space-x-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={settings.json}
                      onChange={(e) => setSettings({ ...settings, json: e.target.checked })}
                      className="accent-[#8D4B00] w-4 h-4 rounded"
                    />
                    <span>保存作品 JSON 元数据</span>
                  </label>

                  <label className="flex items-center space-x-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={settings.folderstyle}
                      onChange={(e) =>
                        setSettings({ ...settings, folderstyle: e.target.checked })
                      }
                      className="accent-[#8D4B00] w-4 h-4 rounded"
                    />
                    <span>使用子文件夹归档</span>
                  </label>

                  <label className="flex items-center space-x-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={settings.database}
                      onChange={(e) =>
                        setSettings({ ...settings, database: e.target.checked })
                      }
                      className="accent-[#8D4B00] w-4 h-4 rounded"
                    />
                    <span>开启 SQLite 去重缓存</span>
                  </label>
                </div>
              </div>
            </form>
          ) : null}

          {saveSuccess && (
            <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center space-x-2 animate-fadeIn">
              <Check className="w-4 h-4 text-emerald-600" />
              <span>设置已成功持久化保存至 config.yaml</span>
            </div>
          )}

          {error && (
            <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 text-rose-600" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 bg-white border-t border-[#E5DED4] flex items-center justify-between">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-xs font-medium text-[#595E68] hover:text-[#1F2328] hover:bg-[#F3ECE2] border border-[#E5DED4] transition-colors"
          >
            取消
          </button>

          <button
            type="submit"
            form="settings-form"
            disabled={saving || loading}
            className="flex items-center space-x-1.5 px-6 py-2 rounded-xl text-xs font-semibold text-white bg-[#8D4B00] hover:bg-[#743D00] disabled:opacity-50 shadow-md shadow-[#8D4B00]/20 transition-all cursor-pointer"
          >
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>保存中...</span>
              </>
            ) : (
              <>
                <Save className="w-4 h-4" />
                <span>保存配置</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
