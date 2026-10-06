// frontend/src/components/Header.tsx

import React from 'react';
import { Download, Film, FolderOpen, RefreshCw, Settings, Sparkles } from 'lucide-react';

interface HeaderProps {
  activeTab: 'downloader' | 'library';
  setActiveTab: (tab: 'downloader' | 'library') => void;
  onOpenSettings: () => void;
  onOpenFolder: () => void;
  activeTaskCount: number;
  isBackendHealthy: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  onOpenSettings,
  onOpenFolder,
  activeTaskCount,
  isBackendHealthy,
}) => {
  return (
    <header className="sticky top-0 z-30 bg-[#FAF8F5]/90 backdrop-blur-md border-b border-[#E5DED4] px-6 py-3 transition-all">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-[#8D4B00] flex items-center justify-center text-white shadow-md shadow-[#8D4B00]/15">
            <Download className="w-5 h-5 stroke-[2.2]" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-base tracking-tight text-[#1F2328]">
                Douyin Downloader
              </span>
              <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#F3ECE2] text-[#8D4B00] border border-[#E5DED4]">
                Web Edition
              </span>
            </div>
            <p className="text-[11px] text-[#595E68]">抖音音视频与图集多线程批量下载</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center bg-[#F3ECE2] p-1 rounded-xl border border-[#E5DED4]">
          <button
            onClick={() => setActiveTab('downloader')}
            className={`flex items-center space-x-2 px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeTab === 'downloader'
                ? 'bg-[#FAF8F5] text-[#8D4B00] shadow-sm font-semibold'
                : 'text-[#595E68] hover:text-[#1F2328]'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>下载器</span>
            {activeTaskCount > 0 && (
              <span className="ml-1 px-1.5 py-0.2 bg-[#8D4B00] text-white text-[10px] rounded-full font-bold">
                {activeTaskCount}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('library')}
            className={`flex items-center space-x-2 px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeTab === 'library'
                ? 'bg-[#FAF8F5] text-[#8D4B00] shadow-sm font-semibold'
                : 'text-[#595E68] hover:text-[#1F2328]'
            }`}
          >
            <Film className="w-3.5 h-3.5" />
            <span>媒体库</span>
          </button>
        </nav>

        {/* Action Controls */}
        <div className="flex items-center space-x-2">
          {/* Health indicator */}
          <div
            className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-[11px] bg-[#F3ECE2] text-[#595E68] border border-[#E5DED4]"
            title={isBackendHealthy ? '后端引擎运行正常' : '后端连接中断'}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isBackendHealthy ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'
              }`}
            />
            <span className="text-[11px]">{isBackendHealthy ? '在线' : '离线'}</span>
          </div>

          <button
            onClick={onOpenFolder}
            className="flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-[#F3ECE2] hover:bg-[#EDE5DA] text-[#1F2328] border border-[#E5DED4] transition-colors"
            title="在文件资源管理器中打开下载目录"
          >
            <FolderOpen className="w-3.5 h-3.5 text-[#8D4B00]" />
            <span className="hidden sm:inline">打开目录</span>
          </button>

          <button
            onClick={onOpenSettings}
            className="flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-[#F3ECE2] hover:bg-[#EDE5DA] text-[#1F2328] border border-[#E5DED4] transition-colors"
            title="下载与全局配置"
          >
            <Settings className="w-3.5 h-3.5 text-[#8D4B00]" />
            <span className="hidden sm:inline">设置</span>
          </button>
        </div>
      </div>
    </header>
  );
};
