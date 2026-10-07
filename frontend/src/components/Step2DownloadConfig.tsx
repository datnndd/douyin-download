// frontend/src/components/Step2DownloadConfig.tsx

import React, { useState } from 'react';
import {
  AlertCircle,
  ArrowLeft,
  Check,
  Cpu,
  Download,
  FileCode,
  Film,
  Folder,
  Image as ImageIcon,
  Loader2,
  Music,
  Sliders,
  Sparkles,
  User,
} from 'lucide-react';
import {
  AssetTypeToggles,
  DownloadRequest,
  FilterOptions,
  ParseResponse,
  SettingsModel,
  TaskResponse,
} from '../types/api';
import { api } from '../services/api';

interface Step2DownloadConfigProps {
  parseData: ParseResponse;
  settings?: SettingsModel | null;
  onBack: () => void;
  onDownloadStarted: (task: TaskResponse) => void;
}

export const Step2DownloadConfig: React.FC<Step2DownloadConfigProps> = ({
  parseData,
  settings,
  onBack,
  onDownloadStarted,
}) => {
  const isUserProfile = parseData.key_type === 'user';

  // State
  const [modes, setModes] = useState<string[]>(
    isUserProfile ? ['post'] : ['post']
  );

  const [assetTypes, setAssetTypes] = useState<AssetTypeToggles>({
    video: true,
    music: settings?.music ?? true,
    cover: settings?.cover ?? true,
    avatar: settings?.avatar ?? false,
    json: settings?.json ?? true,
  });

  const [threadCount, setThreadCount] = useState<number>(settings?.thread ?? 5);

  const [filter, setFilter] = useState<FilterOptions>({
    sort_by: settings?.filter?.sort_by ?? 'create_time',
    reverse: settings?.filter?.reverse ?? true,
    limit: settings?.filter?.limit ?? 0,
  });

  const [folderStyle, setFolderStyle] = useState<boolean>(settings?.folderstyle ?? true);
  const [downloadPath, setDownloadPath] = useState<string>(settings?.path ?? './Downloaded/');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleMode = (mode: string) => {
    if (modes.includes(mode)) {
      if (modes.length > 1) {
        setModes(modes.filter((m) => m !== mode));
      }
    } else {
      setModes([...modes, mode]);
    }
  };

  const toggleAsset = (key: keyof AssetTypeToggles) => {
    setAssetTypes((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handleStartDownload = async () => {
    // Validate at least one asset selected
    if (!assetTypes.video && !assetTypes.music && !assetTypes.cover && !assetTypes.avatar && !assetTypes.json) {
      setError('Please select at least one resource type to download (e.g. video or audio)');
      return;
    }

    setSubmitting(true);
    setError(null);

    const payload: DownloadRequest = {
      url: parseData.url,
      key_type: parseData.key_type,
      key: parseData.key,
      modes: isUserProfile ? modes : ['post'],
      asset_types: assetTypes,
      thread_count: threadCount,
      filter: filter,
      folderstyle: folderStyle,
      download_path: downloadPath,
      cookie: settings?.raw_cookie || undefined,
    };

    try {
      const res = await api.startDownload(payload);
      onDownloadStarted(res);
    } catch (err: any) {
      setError(err.message || 'Failed to start download task');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner: Selected Target Summary */}
      <div className="bg-[#FFFFFF] border border-[#E5DED4] rounded-2xl p-5 shadow-sm flex items-center justify-between">
        <div className="flex items-center space-x-3 overflow-hidden">
          <button
            onClick={onBack}
            className="p-2 rounded-xl text-[#595E68] hover:text-[#1F2328] hover:bg-[#F3ECE2] border border-[#E5DED4] transition-colors"
            title="Back to Step 1"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="overflow-hidden">
            <div className="flex items-center space-x-2">
              <span className="text-[11px] font-semibold text-[#8D4B00] uppercase tracking-wider">
                Current Download Target
              </span>
              <span className="text-[11px] px-2 py-0.2 rounded-full bg-[#F3ECE2] text-[#595E68] border border-[#E5DED4]">
                {parseData.key_type}
              </span>
            </div>
            <h3 className="text-xs font-bold text-[#1F2328] truncate mt-0.5">
              {parseData.preview?.title || parseData.preview?.author?.nickname || parseData.url}
            </h3>
          </div>
        </div>

        <button
          onClick={onBack}
          className="text-xs text-[#8D4B00] font-semibold hover:underline shrink-0 ml-4"
        >
          Change Link
        </button>
      </div>

      {/* Main Configuration Card */}
      <div className="bg-[#FFFFFF] border border-[#E5DED4] rounded-2xl p-6 shadow-sm space-y-6">
        <div>
          <h2 className="text-sm font-semibold text-[#1F2328] flex items-center space-x-2">
            <Sliders className="w-4 h-4 text-[#8D4B00]" />
            <span>Step 2: Configure Download Options</span>
          </h2>
          <p className="text-xs text-[#595E68] mt-1">
            Customize media asset types, concurrency workers, sorting filters, and destination folder
          </p>
        </div>

        {/* User Profile Mode Switch (Only shown if key_type is user) */}
        {isUserProfile && (
          <div className="p-4 rounded-xl bg-[#FAF8F5] border border-[#E5DED4] space-y-2">
            <label className="text-xs font-semibold text-[#1F2328] block">
              Profile Works Download Scope
            </label>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => toggleMode('post')}
                className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-medium border transition-all cursor-pointer ${
                  modes.includes('post')
                    ? 'bg-[#8D4B00] text-white border-[#8D4B00] shadow-sm'
                    : 'bg-white text-[#595E68] border-[#E5DED4] hover:bg-[#F3ECE2]'
                }`}
              >
                <div
                  className={`w-4 h-4 rounded flex items-center justify-center text-[10px] ${
                    modes.includes('post') ? 'bg-white/20' : 'border border-[#898174]'
                  }`}
                >
                  {modes.includes('post') && <Check className="w-3 h-3 text-white" />}
                </div>
                <span>Author published works (post)</span>
              </button>

              <button
                type="button"
                onClick={() => toggleMode('like')}
                className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-medium border transition-all cursor-pointer ${
                  modes.includes('like')
                    ? 'bg-[#8D4B00] text-white border-[#8D4B00] shadow-sm'
                    : 'bg-white text-[#595E68] border-[#E5DED4] hover:bg-[#F3ECE2]'
                }`}
              >
                <div
                  className={`w-4 h-4 rounded flex items-center justify-center text-[10px] ${
                    modes.includes('like') ? 'bg-white/20' : 'border border-[#898174]'
                  }`}
                >
                  {modes.includes('like') && <Check className="w-3 h-3 text-white" />}
                </div>
                <span>Author liked works (like)</span>
              </button>
            </div>
            <p className="text-[11px] text-[#595E68]">
              Note: Downloading liked works requires public likes on the profile or valid cookies
            </p>
          </div>
        )}

        {/* Asset Selection Toggles */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-[#1F2328] block">
            Select Media Assets (Asset Toggles)
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            {/* Video */}
            <button
              type="button"
              onClick={() => toggleAsset('video')}
              className={`flex flex-col items-center justify-center p-3.5 rounded-xl border transition-all cursor-pointer ${
                assetTypes.video
                  ? 'bg-[#FAF8F5] border-[#8D4B00] text-[#8D4B00] shadow-sm font-semibold ring-1 ring-[#8D4B00]/30'
                  : 'bg-white border-[#E5DED4] text-[#898174] hover:bg-[#FAF8F5]'
              }`}
            >
              <Film className="w-5 h-5 mb-1.5" />
              <span className="text-xs">Watermark-free video</span>
              <span className="text-[10px] opacity-75 mt-0.5">MP4</span>
            </button>

            {/* Music */}
            <button
              type="button"
              onClick={() => toggleAsset('music')}
              className={`flex flex-col items-center justify-center p-3.5 rounded-xl border transition-all cursor-pointer ${
                assetTypes.music
                  ? 'bg-[#FAF8F5] border-[#8D4B00] text-[#8D4B00] shadow-sm font-semibold ring-1 ring-[#8D4B00]/30'
                  : 'bg-white border-[#E5DED4] text-[#898174] hover:bg-[#FAF8F5]'
              }`}
            >
              <Music className="w-5 h-5 mb-1.5" />
              <span className="text-xs">Background audio</span>
              <span className="text-[10px] opacity-75 mt-0.5">MP3</span>
            </button>

            {/* Cover */}
            <button
              type="button"
              onClick={() => toggleAsset('cover')}
              className={`flex flex-col items-center justify-center p-3.5 rounded-xl border transition-all cursor-pointer ${
                assetTypes.cover
                  ? 'bg-[#FAF8F5] border-[#8D4B00] text-[#8D4B00] shadow-sm font-semibold ring-1 ring-[#8D4B00]/30'
                  : 'bg-white border-[#E5DED4] text-[#898174] hover:bg-[#FAF8F5]'
              }`}
            >
              <ImageIcon className="w-5 h-5 mb-1.5" />
              <span className="text-xs">HD Cover image</span>
              <span className="text-[10px] opacity-75 mt-0.5">JPG / PNG</span>
            </button>

            {/* Avatar */}
            <button
              type="button"
              onClick={() => toggleAsset('avatar')}
              className={`flex flex-col items-center justify-center p-3.5 rounded-xl border transition-all cursor-pointer ${
                assetTypes.avatar
                  ? 'bg-[#FAF8F5] border-[#8D4B00] text-[#8D4B00] shadow-sm font-semibold ring-1 ring-[#8D4B00]/30'
                  : 'bg-white border-[#E5DED4] text-[#898174] hover:bg-[#FAF8F5]'
              }`}
            >
              <User className="w-5 h-5 mb-1.5" />
              <span className="text-xs">Creator avatar</span>
              <span className="text-[10px] opacity-75 mt-0.5">JPG</span>
            </button>

            {/* JSON Metadata */}
            <button
              type="button"
              onClick={() => toggleAsset('json')}
              className={`flex flex-col items-center justify-center p-3.5 rounded-xl border transition-all cursor-pointer ${
                assetTypes.json
                  ? 'bg-[#FAF8F5] border-[#8D4B00] text-[#8D4B00] shadow-sm font-semibold ring-1 ring-[#8D4B00]/30'
                  : 'bg-white border-[#E5DED4] text-[#898174] hover:bg-[#FAF8F5]'
              }`}
            >
              <FileCode className="w-5 h-5 mb-1.5" />
              <span className="text-xs">Metadata document</span>
              <span className="text-[10px] opacity-75 mt-0.5">JSON</span>
            </button>
          </div>
        </div>

        {/* Concurrency Thread Slider */}
        <div className="p-4 rounded-xl bg-[#FAF8F5] border border-[#E5DED4] space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Cpu className="w-4 h-4 text-[#8D4B00]" />
              <span className="text-xs font-semibold text-[#1F2328]">
                Concurrent Download Workers
              </span>
            </div>
            <div className="flex items-center space-x-1.5">
              <span className="text-sm font-mono font-bold text-[#8D4B00] px-2.5 py-0.5 rounded-md bg-[#F3ECE2] border border-[#E5DED4]">
                {threadCount} workers
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <span className="text-[11px] text-[#898174] font-mono">1</span>
            <input
              type="range"
              min={1}
              max={32}
              value={threadCount}
              onChange={(e) => setThreadCount(Number(e.target.value))}
              className="flex-1 accent-[#8D4B00] h-1.5 bg-[#E5DED4] rounded-lg cursor-pointer"
            />
            <span className="text-[11px] text-[#898174] font-mono">32</span>
          </div>

          <p className="text-[11px] text-[#595E68]">
            Thread pool manages multi-file concurrent downloads and range resumption. 5~10 threads recommended for balance.
          </p>
        </div>

        {/* Filter and Sorting (For Profiles and Mixes) */}
        {isUserProfile && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="text-xs font-semibold text-[#1F2328] block mb-1.5">
                Sort By
              </label>
              <select
                value={filter.sort_by}
                onChange={(e) => setFilter({ ...filter, sort_by: e.target.value })}
                className="w-full px-3 py-2 rounded-xl border border-[#E5DED4] bg-[#FAF8F5] text-xs text-[#1F2328] focus:outline-none focus:border-[#8D4B00]"
              >
                <option value="create_time">Publish Time (create_time)</option>
                <option value="digg_count">Like Count (digg_count)</option>
                <option value="comment_count">Comment Count (comment_count)</option>
                <option value="play_count">Play Count (play_count)</option>
                <option value="share_count">Share Count (share_count)</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-[#1F2328] block mb-1.5">
                Sort Order
              </label>
              <select
                value={filter.reverse ? 'desc' : 'asc'}
                onChange={(e) =>
                  setFilter({ ...filter, reverse: e.target.value === 'desc' })
                }
                className="w-full px-3 py-2 rounded-xl border border-[#E5DED4] bg-[#FAF8F5] text-xs text-[#1F2328] focus:outline-none focus:border-[#8D4B00]"
              >
                <option value="desc">Descending (Newest / Highest)</option>
                <option value="asc">Ascending (Oldest / Lowest)</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-[#1F2328] block mb-1.5">
                Download Limit (0 for all)
              </label>
              <input
                type="number"
                min={0}
                value={filter.limit}
                onChange={(e) =>
                  setFilter({ ...filter, limit: Math.max(0, parseInt(e.target.value) || 0) })
                }
                className="w-full px-3 py-2 rounded-xl border border-[#E5DED4] bg-[#FAF8F5] text-xs text-[#1F2328] focus:outline-none focus:border-[#8D4B00]"
              />
            </div>
          </div>
        )}

        {/* Directory & Folder Structure Options */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
          <div>
            <label className="text-xs font-semibold text-[#1F2328] block mb-1.5">
              Destination Download Path
            </label>
            <div className="relative">
              <input
                type="text"
                value={downloadPath}
                onChange={(e) => setDownloadPath(e.target.value)}
                className="w-full px-3 py-2 pl-9 rounded-xl border border-[#E5DED4] bg-[#FAF8F5] text-xs font-mono text-[#1F2328] focus:outline-none focus:border-[#8D4B00]"
              />
              <Folder className="w-4 h-4 text-[#8D4B00] absolute left-3 top-2.5 pointer-events-none" />
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-[#1F2328] block mb-1.5">
              Directory Organization Structure
            </label>
            <div className="flex items-center space-x-3 pt-1">
              <button
                type="button"
                onClick={() => setFolderStyle(true)}
                className={`flex-1 py-2 px-3 rounded-xl text-xs font-medium border text-center transition-all ${
                  folderStyle
                    ? 'bg-[#FAF8F5] border-[#8D4B00] text-[#8D4B00] font-semibold'
                    : 'bg-white border-[#E5DED4] text-[#595E68] hover:bg-[#FAF8F5]'
                }`}
              >
                Individual subfolders (Recommended)
              </button>
              <button
                type="button"
                onClick={() => setFolderStyle(false)}
                className={`flex-1 py-2 px-3 rounded-xl text-xs font-medium border text-center transition-all ${
                  !folderStyle
                    ? 'bg-[#FAF8F5] border-[#8D4B00] text-[#8D4B00] font-semibold'
                    : 'bg-white border-[#E5DED4] text-[#595E68] hover:bg-[#FAF8F5]'
                }`}
              >
                Flat in root directory
              </button>
            </div>
          </div>
        </div>

        {error && (
          <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start space-x-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <span className="flex-1">{error}</span>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex items-center justify-between pt-4 border-t border-[#E5DED4]">
          <button
            type="button"
            onClick={onBack}
            className="flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-medium text-[#595E68] bg-[#FAF8F5] hover:bg-[#F3ECE2] border border-[#E5DED4] transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Preview</span>
          </button>

          <button
            type="button"
            onClick={handleStartDownload}
            disabled={submitting}
            className="flex items-center space-x-2 px-8 py-2.5 rounded-xl text-xs font-semibold text-white bg-[#8D4B00] hover:bg-[#743D00] disabled:opacity-50 shadow-md shadow-[#8D4B00]/20 transition-all cursor-pointer"
          >
            {submitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Initializing download task...</span>
              </>
            ) : (
              <>
                <Download className="w-4 h-4" />
                <span>Start High-Speed Download</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
