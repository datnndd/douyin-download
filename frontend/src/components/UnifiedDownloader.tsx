// frontend/src/components/UnifiedDownloader.tsx

import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle,
  Calendar,
  Check,
  ChevronDown,
  ChevronUp,
  Clipboard,
  Cpu,
  Download,
  Eye,
  FileCode,
  FileText,
  Film,
  Filter,
  Folder,
  FolderOpen,
  Heart,
  HelpCircle,
  Image as ImageIcon,
  Layers,
  Loader2,
  MessageCircle,
  Music,
  RefreshCw,
  Search,
  Share2,
  Sliders,
  Sparkles,
  User,
  Users,
  Video,
  X,
} from 'lucide-react';
import {
  AssetTypeToggles,
  DownloadRequest,
  FilterOptions,
  ParseResponse,
  PreviewMetadata,
  SettingsModel,
  TaskResponse,
} from '../types/api';
import { api } from '../services/api';

/**
 * Extracts clean Douyin or HTTP URL from raw clipboard text, Kouling tokens, or share messages.
 * e.g. "0.23 C@u.sr :0pm 01/04 TLJ:/ Catching seafood fresh... https://v.douyin.com/meBXuCMU5l0/ Copy this link..."
 */
export const extractDouyinUrl = (text: string): string => {
  if (!text || !text.trim()) return '';
  const douyinMatch = text.match(
    /(?:https?:\/\/)?(?:[a-zA-Z0-9\-]+\.)?(?:douyin\.com|iesdouyin\.com)\/[a-zA-Z0-9_./\-?&=%#+:@!~*]*/i
  );
  const punctuationStrip = /[),.!?，。！？;；:：'"【】（）《》、~\s]+$/;
  if (douyinMatch) {
    let url = douyinMatch[0].replace(punctuationStrip, '');
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      url = 'https://' + url;
    }
    return url;
  }
  const genericMatch = text.match(/https?:\/\/[a-zA-Z0-9_./\-?&=%#+:@!~*]+/i);
  if (genericMatch) {
    return genericMatch[0].replace(punctuationStrip, '');
  }
  return text.trim();
};

interface UnifiedDownloaderProps {
  settings?: SettingsModel | null;
  onDownloadStarted: (task: TaskResponse) => void;
  onOpenFolder?: () => void;
}

const FILENAME_PRESETS = [
  { label: 'Date_Title_ID (Standard)', template: '{date}_{title}_{id}' },
  { label: 'Likes_Date_Title (Legacy default)', template: '{likes}likes_{date}_{title}' },
  { label: 'Title_ID (Compact)', template: '{title}_{id}' },
  { label: 'Author_Title_ID', template: '{author}_{title}_{id}' },
  { label: 'Video ID Only', template: '{id}' },
  { label: 'Custom...', template: 'custom' },
];

export const UnifiedDownloader: React.FC<UnifiedDownloaderProps> = ({
  settings,
  onDownloadStarted,
  onOpenFolder,
}) => {
  // Input & Parse state
  const [urlInput, setUrlInput] = useState('');
  const [parsing, setParsing] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [parsedData, setParsedData] = useState<ParseResponse | null>(null);

  // Download options state
  const [assetTypes, setAssetTypes] = useState<AssetTypeToggles>({
    video: true,
    music: settings?.music ?? true,
    cover: settings?.cover ?? true,
    avatar: settings?.avatar ?? false,
    json: settings?.json ?? true,
  });

  const [downloadPath, setDownloadPath] = useState<string>(
    settings?.path || './Downloaded/'
  );
  const [threadCount, setThreadCount] = useState<number>(settings?.thread ?? 5);
  const [folderStyle, setFolderStyle] = useState<boolean>(
    settings?.folderstyle ?? true
  );

  // Filename template state
  const defaultTpl = settings?.filename_template || '{date}_{title}_{id}';
  const [selectedPreset, setSelectedPreset] = useState<string>(() => {
    const matched = FILENAME_PRESETS.find((p) => p.template === defaultTpl);
    return matched ? defaultTpl : 'custom';
  });
  const [filenameTemplate, setFilenameTemplate] = useState<string>(defaultTpl);

  // User Profile Filter state (start_time, end_time, number)
  const [userModes, setUserModes] = useState<string[]>(['post']);
  const [startTime, setStartTime] = useState<string>(settings?.start_time || '');
  const [endTime, setEndTime] = useState<string>(settings?.end_time || '');
  const [videoLimit, setVideoLimit] = useState<number>(0); // 0 = unlimited

  // UI accordion state
  const [showUserFilters, setShowUserFilters] = useState<boolean>(false);
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);
  const [downloading, setDownloading] = useState<boolean>(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  // Auto-preview debounce ref
  const lastParsedUrlRef = useRef<string>('');

  // Update downloadPath if settings change
  useEffect(() => {
    if (settings?.path && downloadPath === './Downloaded/') {
      setDownloadPath(settings.path);
    }
  }, [settings?.path]);

  // Detect whether link indicates a user profile
  const isUserProfile = useMemo(() => {
    if (parsedData?.key_type === 'user') return true;
    const clean = extractDouyinUrl(urlInput);
    return clean.includes('/user/') || clean.includes('sec_uid=');
  }, [parsedData, urlInput]);

  // Auto-expand user filter section when user profile link is detected
  useEffect(() => {
    if (isUserProfile) {
      setShowUserFilters(true);
    }
  }, [isUserProfile]);

  // Debounced auto-preview when user types or pastes URL
  useEffect(() => {
    const cleanUrl = extractDouyinUrl(urlInput.trim());
    if (!cleanUrl || cleanUrl === lastParsedUrlRef.current) return;

    // Minimum check for Douyin / HTTP format
    if (!cleanUrl.startsWith('http://') && !cleanUrl.startsWith('https://')) return;

    const timer = setTimeout(() => {
      handleParse(cleanUrl, true);
    }, 600);

    return () => clearTimeout(timer);
  }, [urlInput]);

  // Parse handler
  const handleParse = async (targetUrl?: string, isSilent = false) => {
    const raw = targetUrl || urlInput.trim();
    const clean = extractDouyinUrl(raw) || raw;
    if (!clean) {
      if (!isSilent) setParseError('Please enter a Douyin link or share text.');
      return;
    }

    if (!isSilent && clean !== urlInput.trim()) {
      setUrlInput(clean);
    }

    setParsing(true);
    setParseError(null);
    lastParsedUrlRef.current = clean;

    try {
      const res = await api.parseUrl(clean, settings?.raw_cookie);
      if (!res.success) {
        setParseError(res.error || 'Failed to parse link metadata.');
      } else {
        setParsedData(res);
      }
    } catch (err: any) {
      if (!isSilent) {
        setParseError(err.message || 'Connection error with parsing engine.');
      }
    } finally {
      setParsing(false);
    }
  };

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        setUrlInput(text);
        const clean = extractDouyinUrl(text);
        if (clean) {
          handleParse(clean, false);
        }
      }
    } catch {
      // Clipboard read permission might be blocked
    }
  };

  const handleClearUrl = () => {
    setUrlInput('');
    setParsedData(null);
    setParseError(null);
    lastParsedUrlRef.current = '';
  };

  const toggleAsset = (key: keyof AssetTypeToggles) => {
    setAssetTypes((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const toggleUserMode = (mode: string) => {
    if (userModes.includes(mode)) {
      if (userModes.length > 1) {
        setUserModes(userModes.filter((m) => m !== mode));
      }
    } else {
      setUserModes([...userModes, mode]);
    }
  };

  const handlePresetChange = (tpl: string) => {
    setSelectedPreset(tpl);
    if (tpl !== 'custom') {
      setFilenameTemplate(tpl);
    }
  };

  const insertVariableTag = (tag: string) => {
    setSelectedPreset('custom');
    setFilenameTemplate((prev) => prev + tag);
  };

  // Quick date filters
  const applyQuickDate = (days: number | 'all' | 'this_year') => {
    const now = new Date();
    const formatYMD = (d: Date) => d.toISOString().split('T')[0];

    if (days === 'all') {
      setStartTime('');
      setEndTime('');
    } else if (days === 'this_year') {
      setStartTime(`${now.getFullYear()}-01-01`);
      setEndTime(formatYMD(now));
    } else {
      const past = new Date();
      past.setDate(past.getDate() - days);
      setStartTime(formatYMD(past));
      setEndTime(formatYMD(now));
    }
  };

  // Generate a live sample of the filename for user preview
  const sampleFilename = useMemo(() => {
    const tpl = filenameTemplate || '{date}_{title}_{id}';
    const dateVal = parsedData?.preview?.extra?.create_time
      ? String(parsedData.preview.extra.create_time).split(' ')[0]
      : '2024-10-29';
    const titleVal =
      (parsedData?.preview?.title || 'Sample Video Title')
        .replace(/[\\/*?:"<>|\r\n\t]/g, '_')
        .slice(0, 30);
    const idVal = parsedData?.key || '7431234567890';
    const authorVal =
      parsedData?.preview?.author?.nickname || 'CreatorName';
    const likesVal = '000772108';

    let res = tpl
      .replace('{date}', dateVal)
      .replace('{time}', '2024-10-29_16.01.41')
      .replace('{title}', titleVal)
      .replace('{desc}', titleVal)
      .replace('{id}', idVal)
      .replace('{aweme_id}', idVal)
      .replace('{author}', authorVal)
      .replace('{nickname}', authorVal)
      .replace('{likes}', likesVal)
      .replace('{digg_count}', likesVal);

    return res + (assetTypes.video ? '_video.mp4' : '');
  }, [filenameTemplate, parsedData, assetTypes.video]);

  // Main download initiator
  const handleStartDownload = async () => {
    const raw = urlInput.trim();
    const clean = extractDouyinUrl(raw) || raw;
    if (!clean) {
      setDownloadError('Please enter or paste a Douyin link to download.');
      return;
    }

    if (!assetTypes.video && !assetTypes.music && !assetTypes.cover && !assetTypes.avatar && !assetTypes.json) {
      setDownloadError('Please select at least one media asset (Video, Audio, Cover...)');
      return;
    }

    setDownloading(true);
    setDownloadError(null);

    const payload: DownloadRequest = {
      url: clean,
      key_type: parsedData?.key_type || (isUserProfile ? 'user' : 'aweme'),
      key: parsedData?.key || '',
      modes: isUserProfile ? userModes : ['post'],
      asset_types: assetTypes,
      thread_count: threadCount,
      folderstyle: folderStyle,
      download_path: downloadPath,
      filename_template: filenameTemplate || '{date}_{title}_{id}',
      start_time: startTime || '',
      end_time: endTime || '',
      number: {
        post: videoLimit,
        like: videoLimit,
        allmix: 0,
        mix: videoLimit || 5,
        music: 5,
      },
      cookie: settings?.raw_cookie || undefined,
    };

    try {
      const res = await api.startDownload(payload);
      onDownloadStarted(res);
      // Optional: keep URL or clear according to preference
    } catch (err: any) {
      setDownloadError(err.message || 'Failed to start download task.');
    } finally {
      setDownloading(false);
    }
  };

  const formatNumber = (num: number = 0): string => {
    if (num >= 1000000000) return (num / 1000000000).toFixed(1) + 'B';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toLocaleString();
  };

  return (
    <div className="space-y-6">
      {/* ==================================================================== */}
      {/* 1. TOP URL INPUT & INSTANT ACTIONS BAR                               */}
      {/* ==================================================================== */}
      <div className="bg-white border border-[#E5DED4] rounded-2xl p-4 sm:p-5 shadow-sm space-y-3">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
          {/* Main Input Box */}
          <div className="relative flex-1 flex items-center bg-[#FAF8F5] border border-[#E5DED4] rounded-xl focus-within:border-[#8D4B00] focus-within:ring-2 focus-within:ring-[#8D4B00]/15 transition-all">
            <div className="pl-3.5 pr-2 text-[#898174]">
              {parsing ? (
                <Loader2 className="w-4 h-4 animate-spin text-[#8D4B00]" />
              ) : (
                <Search className="w-4 h-4" />
              )}
            </div>

            <input
              type="text"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleStartDownload();
                }
              }}
              placeholder="Paste video link, Kouling share text, or Douyin profile link (https://v.douyin.com/...)"
              className="w-full py-2.5 pr-20 bg-transparent text-xs sm:text-sm text-[#1F2328] placeholder-[#898174] focus:outline-none"
            />

            {/* Quick Input Actions (Clear & Paste) */}
            <div className="absolute right-2 flex items-center space-x-1">
              {urlInput && (
                <button
                  type="button"
                  onClick={handleClearUrl}
                  className="p-1 rounded-md text-[#898174] hover:text-[#1F2328] hover:bg-[#E5DED4]/50 transition-colors"
                  title="Clear input"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
              <button
                type="button"
                onClick={handlePaste}
                className="flex items-center space-x-1 px-2 py-1 rounded-md text-xs font-medium text-[#8D4B00] bg-[#F3ECE2] hover:bg-[#EDE5DA] transition-colors"
                title="Paste from clipboard"
              >
                <Clipboard className="w-3.5 h-3.5" />
                <span className="hidden md:inline">Paste</span>
              </button>
            </div>
          </div>

          {/* Right Action Buttons */}
          <div className="flex items-center gap-2 shrink-0">
            {/* Preview Button */}
            <button
              type="button"
              onClick={() => handleParse()}
              disabled={parsing || !urlInput.trim()}
              className="flex items-center justify-center space-x-1.5 px-3.5 py-2.5 rounded-xl text-xs font-semibold bg-[#F3ECE2] hover:bg-[#EDE5DA] text-[#8D4B00] border border-[#E5DED4] disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              title="Inspect & preview content"
            >
              {parsing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Eye className="w-4 h-4" />
              )}
              <span>Preview</span>
            </button>

            {/* PRIMARY DOWNLOAD BUTTON */}
            <button
              type="button"
              onClick={handleStartDownload}
              disabled={downloading || !urlInput.trim()}
              className="flex-1 sm:flex-none flex items-center justify-center space-x-2 px-5 py-2.5 rounded-xl text-xs sm:text-sm font-bold bg-[#8D4B00] hover:bg-[#723C00] active:scale-[0.98] text-white shadow-md shadow-[#8D4B00]/25 disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer"
            >
              {downloading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Download className="w-4 h-4 stroke-[2.5]" />
              )}
              <span>DOWNLOAD NOW</span>
            </button>
          </div>
        </div>

        {/* Status Alerts */}
        {parseError && (
          <div className="flex items-center space-x-2 px-3 py-2 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs">
            <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
            <span className="flex-1">{parseError}</span>
            <button
              onClick={() => setParseError(null)}
              className="text-amber-700 hover:text-amber-900 text-xs underline"
            >
              Dismiss
            </button>
          </div>
        )}

        {downloadError && (
          <div className="flex items-center space-x-2 px-3 py-2 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span className="flex-1">{downloadError}</span>
            <button
              onClick={() => setDownloadError(null)}
              className="text-rose-700 hover:text-rose-900 text-xs underline"
            >
              Dismiss
            </button>
          </div>
        )}
      </div>

      {/* ==================================================================== */}
      {/* 2. SPLIT LAYOUT: LIVE PREVIEW & DOWNLOAD CONFIGURATION CARD          */}
      {/* ==================================================================== */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* ------------------------------------------------------------------ */}
        {/* LEFT COLUMN: LIVE METADATA PREVIEW (5 cols)                       */}
        {/* ------------------------------------------------------------------ */}
        <div className="lg:col-span-5 bg-white border border-[#E5DED4] rounded-2xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#E5DED4]">
            <div className="flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-[#8D4B00]" />
              <h2 className="text-sm font-bold text-[#1F2328]">Detected Content</h2>
            </div>
            {parsedData && (
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-[#F3ECE2] text-[#8D4B00] border border-[#E5DED4] uppercase">
                {parsedData.key_type}
              </span>
            )}
          </div>

          {parsedData?.preview ? (
            <div className="space-y-4 animate-fadeIn">
              {/* Creator Card */}
              {parsedData.preview.author && (
                <div className="flex items-center space-x-3 p-3 bg-[#FAF8F5] rounded-xl border border-[#E5DED4]">
                  <img
                    src={
                      parsedData.preview.author.avatar_thumb ||
                      parsedData.preview.author.avatar ||
                      '/avatar-placeholder.png'
                    }
                    alt={parsedData.preview.author.nickname}
                    className="w-12 h-12 rounded-full object-cover border border-[#E5DED4] shadow-xs"
                    onError={(e) => {
                      (e.target as HTMLElement).style.display = 'none';
                    }}
                  />
                  <div className="overflow-hidden flex-1">
                    <h4 className="text-xs font-bold text-[#1F2328] truncate">
                      {parsedData.preview.author.nickname}
                    </h4>
                    <p className="text-[11px] text-[#595E68] font-mono truncate">
                      {parsedData.preview.author.unique_id
                        ? `@${parsedData.preview.author.unique_id}`
                        : `ID: ${parsedData.preview.author.short_id || parsedData.key}`}
                    </p>
                    <div className="flex items-center space-x-3 text-[10px] text-[#898174] mt-0.5">
                      <span>
                        Followers:{' '}
                        <strong>
                          {formatNumber(parsedData.preview.author.follower_count || 0)}
                        </strong>
                      </span>
                      <span>
                        Likes:{' '}
                        <strong>
                          {formatNumber(parsedData.preview.author.total_favorited || 0)}
                        </strong>
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Cover & Title */}
              <div className="relative rounded-xl overflow-hidden border border-[#E5DED4] bg-[#FAF8F5] aspect-video flex items-center justify-center group">
                {parsedData.preview.cover_url ? (
                  <img
                    src={parsedData.preview.cover_url}
                    alt={parsedData.preview.title}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                  />
                ) : (
                  <Film className="w-10 h-10 text-[#898174]" />
                )}
                {parsedData.preview.duration ? (
                  <span className="absolute bottom-2 right-2 px-2 py-0.5 bg-black/70 text-white font-mono text-[10px] rounded-md backdrop-blur-xs">
                    {Math.floor(parsedData.preview.duration / 60)}:
                    {(parsedData.preview.duration % 60).toString().padStart(2, '0')}
                  </span>
                ) : null}
              </div>

              {/* Title description */}
              <div>
                <h3 className="text-xs font-semibold text-[#1F2328] line-clamp-3">
                  {parsedData.preview.title || parsedData.preview.desc || 'Douyin Video'}
                </h3>
              </div>

              {/* Statistics Counters */}
              <div className="grid grid-cols-4 gap-2 pt-2 border-t border-[#E5DED4] text-center">
                <div className="p-2 rounded-lg bg-[#FAF8F5] border border-[#E5DED4]/60">
                  <div className="flex items-center justify-center space-x-1 text-rose-600 text-[11px] font-semibold">
                    <Heart className="w-3 h-3 fill-rose-600" />
                    <span>{formatNumber(parsedData.preview.statistics?.digg_count)}</span>
                  </div>
                  <span className="text-[10px] text-[#898174]">Likes</span>
                </div>
                <div className="p-2 rounded-lg bg-[#FAF8F5] border border-[#E5DED4]/60">
                  <div className="flex items-center justify-center space-x-1 text-[#8D4B00] text-[11px] font-semibold">
                    <MessageCircle className="w-3 h-3" />
                    <span>{formatNumber(parsedData.preview.statistics?.comment_count)}</span>
                  </div>
                  <span className="text-[10px] text-[#898174]">Comments</span>
                </div>
                <div className="p-2 rounded-lg bg-[#FAF8F5] border border-[#E5DED4]/60">
                  <div className="flex items-center justify-center space-x-1 text-[#595E68] text-[11px] font-semibold">
                    <Share2 className="w-3 h-3" />
                    <span>{formatNumber(parsedData.preview.statistics?.share_count)}</span>
                  </div>
                  <span className="text-[10px] text-[#898174]">Shares</span>
                </div>
                <div className="p-2 rounded-lg bg-[#FAF8F5] border border-[#E5DED4]/60">
                  <div className="flex items-center justify-center space-x-1 text-amber-600 text-[11px] font-semibold">
                    <Layers className="w-3 h-3" />
                    <span>{formatNumber(parsedData.preview.statistics?.collect_count)}</span>
                  </div>
                  <span className="text-[10px] text-[#898174]">Collects</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="py-10 px-4 text-center space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-[#F3ECE2] text-[#8D4B00] flex items-center justify-center mx-auto">
                <Film className="w-6 h-6" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-[#1F2328]">
                  No preview available
                </h4>
                <p className="text-[11px] text-[#595E68] mt-1 max-w-xs mx-auto">
                  Paste a video link, photo gallery, or user profile above to preview or click <strong>Download Now</strong>.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* ------------------------------------------------------------------ */}
        {/* RIGHT COLUMN: DOWNLOAD OPTIONS & DIRECT CONTROLS (7 cols)         */}
        {/* ------------------------------------------------------------------ */}
        <div className="lg:col-span-7 space-y-5">
          {/* Main Options Box */}
          <div className="bg-white border border-[#E5DED4] rounded-2xl p-5 sm:p-6 shadow-sm space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-[#E5DED4]">
              <div className="flex items-center space-x-2">
                <Sliders className="w-4 h-4 text-[#8D4B00]" />
                <h2 className="text-sm font-bold text-[#1F2328]">Download Options</h2>
              </div>
              <span className="text-[11px] text-[#898174]">
                Automatically applied when starting download
              </span>
            </div>

            {/* 1. ASSET SELECTION TOGGLES */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-[#1F2328]">
                Target Media Assets
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                {/* Video */}
                <button
                  type="button"
                  onClick={() => toggleAsset('video')}
                  className={`flex items-center space-x-2 p-2.5 rounded-xl border text-xs font-medium transition-all text-left ${
                    assetTypes.video
                      ? 'bg-[#F3ECE2] border-[#8D4B00] text-[#8D4B00] font-semibold shadow-xs'
                      : 'bg-[#FAF8F5] border-[#E5DED4] text-[#595E68] hover:bg-[#F3ECE2]/50'
                  }`}
                >
                  <Video className="w-4 h-4 shrink-0" />
                  <span className="truncate">Video (.mp4)</span>
                </button>

                {/* Music */}
                <button
                  type="button"
                  onClick={() => toggleAsset('music')}
                  className={`flex items-center space-x-2 p-2.5 rounded-xl border text-xs font-medium transition-all text-left ${
                    assetTypes.music
                      ? 'bg-[#F3ECE2] border-[#8D4B00] text-[#8D4B00] font-semibold shadow-xs'
                      : 'bg-[#FAF8F5] border-[#E5DED4] text-[#595E68] hover:bg-[#F3ECE2]/50'
                  }`}
                >
                  <Music className="w-4 h-4 shrink-0" />
                  <span className="truncate">Music (.mp3)</span>
                </button>

                {/* Cover */}
                <button
                  type="button"
                  onClick={() => toggleAsset('cover')}
                  className={`flex items-center space-x-2 p-2.5 rounded-xl border text-xs font-medium transition-all text-left ${
                    assetTypes.cover
                      ? 'bg-[#F3ECE2] border-[#8D4B00] text-[#8D4B00] font-semibold shadow-xs'
                      : 'bg-[#FAF8F5] border-[#E5DED4] text-[#595E68] hover:bg-[#F3ECE2]/50'
                  }`}
                >
                  <ImageIcon className="w-4 h-4 shrink-0" />
                  <span className="truncate">Cover (.jpeg)</span>
                </button>

                {/* Avatar */}
                <button
                  type="button"
                  onClick={() => toggleAsset('avatar')}
                  className={`flex items-center space-x-2 p-2.5 rounded-xl border text-xs font-medium transition-all text-left ${
                    assetTypes.avatar
                      ? 'bg-[#F3ECE2] border-[#8D4B00] text-[#8D4B00] font-semibold shadow-xs'
                      : 'bg-[#FAF8F5] border-[#E5DED4] text-[#595E68] hover:bg-[#F3ECE2]/50'
                  }`}
                >
                  <User className="w-4 h-4 shrink-0" />
                  <span className="truncate">Creator avatar</span>
                </button>

                {/* JSON */}
                <button
                  type="button"
                  onClick={() => toggleAsset('json')}
                  className={`flex items-center space-x-2 p-2.5 rounded-xl border text-xs font-medium transition-all text-left ${
                    assetTypes.json
                      ? 'bg-[#F3ECE2] border-[#8D4B00] text-[#8D4B00] font-semibold shadow-xs'
                      : 'bg-[#FAF8F5] border-[#E5DED4] text-[#595E68] hover:bg-[#F3ECE2]/50'
                  }`}
                >
                  <FileText className="w-4 h-4 shrink-0" />
                  <span className="truncate">JSON metadata</span>
                </button>
              </div>
            </div>

            {/* 2. STORAGE DESTINATION PATH */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-[#1F2328] flex items-center space-x-1.5">
                  <Folder className="w-3.5 h-3.5 text-[#8D4B00]" />
                  <span>Download Destination Folder</span>
                </label>
                {onOpenFolder && (
                  <button
                    type="button"
                    onClick={onOpenFolder}
                    className="text-[11px] text-[#8D4B00] hover:underline flex items-center space-x-1"
                  >
                    <FolderOpen className="w-3 h-3" />
                    <span>Open in File Explorer</span>
                  </button>
                )}
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={downloadPath}
                  onChange={(e) => setDownloadPath(e.target.value)}
                  placeholder="./Downloaded/"
                  className="flex-1 px-3 py-2 rounded-xl border border-[#E5DED4] bg-[#FAF8F5] text-xs font-mono text-[#1F2328] focus:outline-none focus:border-[#8D4B00]"
                />
                <button
                  type="button"
                  onClick={() => setDownloadPath('./Downloaded/')}
                  className="px-2.5 py-2 text-xs rounded-xl border border-[#E5DED4] text-[#595E68] hover:bg-[#FAF8F5]"
                  title="Reset to default"
                >
                  Default
                </button>
              </div>
            </div>

            {/* 3. FILENAME NAMING TEMPLATE */}
            <div className="space-y-2 p-3.5 bg-[#FAF8F5] rounded-xl border border-[#E5DED4]">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-[#1F2328] flex items-center space-x-1.5">
                  <FileCode className="w-3.5 h-3.5 text-[#8D4B00]" />
                  <span>Filename Naming Template</span>
                </label>
              </div>

              {/* Preset Selector */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                {FILENAME_PRESETS.map((preset) => (
                  <button
                    key={preset.template}
                    type="button"
                    onClick={() => handlePresetChange(preset.template)}
                    className={`px-2.5 py-1.5 text-[11px] rounded-lg border text-left truncate transition-all ${
                      selectedPreset === preset.template
                        ? 'bg-[#8D4B00] text-white border-[#8D4B00] font-semibold'
                        : 'bg-white border-[#E5DED4] text-[#595E68] hover:bg-[#F3ECE2]'
                    }`}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>

              {/* Custom Input & Tag insertion chips */}
              <div className="space-y-1.5 pt-1">
                <input
                  type="text"
                  value={filenameTemplate}
                  onChange={(e) => {
                    setFilenameTemplate(e.target.value);
                    setSelectedPreset('custom');
                  }}
                  placeholder="{date}_{title}_{id}"
                  className="w-full px-3 py-1.5 rounded-lg border border-[#E5DED4] bg-white text-xs font-mono text-[#1F2328] focus:outline-none focus:border-[#8D4B00]"
                />

                {/* Variable helper tags */}
                <div className="flex flex-wrap items-center gap-1 text-[10px] text-[#898174]">
                  <span>Insert tag:</span>
                  {[
                    { tag: '{date}', label: 'Date' },
                    { tag: '{title}', label: 'Title' },
                    { tag: '{id}', label: 'ID' },
                    { tag: '{author}', label: 'Author' },
                    { tag: '{likes}', label: 'Likes' },
                  ].map((v) => (
                    <button
                      key={v.tag}
                      type="button"
                      onClick={() => insertVariableTag(v.tag)}
                      className="px-1.5 py-0.5 rounded bg-white hover:bg-[#EDE5DA] border border-[#E5DED4] font-mono text-[#8D4B00] cursor-pointer"
                    >
                      {v.tag}
                    </button>
                  ))}
                </div>

                {/* Live Sample Preview */}
                <div className="flex items-center space-x-1.5 text-[11px] text-[#595E68] bg-white p-2 rounded-lg border border-[#E5DED4]/60 font-mono truncate">
                  <span className="text-[#8D4B00] font-semibold shrink-0">Sample filename:</span>
                  <span className="truncate">{sampleFilename}</span>
                </div>
              </div>
            </div>

            {/* 4. USER PROFILE FILTERS (DATE RANGE & VIDEO COUNT) */}
            <div
              className={`rounded-xl border transition-all ${
                isUserProfile
                  ? 'border-[#8D4B00]/40 bg-amber-50/20'
                  : 'border-[#E5DED4] bg-[#FAF8F5]'
              }`}
            >
              {/* Accordion Header */}
              <button
                type="button"
                onClick={() => setShowUserFilters(!showUserFilters)}
                className="w-full px-4 py-3 flex items-center justify-between text-left text-xs font-semibold text-[#1F2328]"
              >
                <div className="flex items-center space-x-2">
                  <Filter className="w-3.5 h-3.5 text-[#8D4B00]" />
                  <span>Creator Profile / User Works Filter</span>
                  {isUserProfile && (
                    <span className="text-[10px] px-2 py-0.5 bg-[#8D4B00] text-white rounded-full font-bold">
                      Active
                    </span>
                  )}
                </div>
                {showUserFilters ? (
                  <ChevronUp className="w-4 h-4 text-[#898174]" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-[#898174]" />
                )}
              </button>

              {/* Accordion Body */}
              {showUserFilters && (
                <div className="px-4 pb-4 pt-1 space-y-3.5 border-t border-[#E5DED4]/60 animate-fadeIn">
                  {/* Mode Select (Post vs Like) */}
                  <div className="space-y-1.5">
                    <label className="text-[11px] font-semibold text-[#595E68]">
                      Works Content Type
                    </label>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => toggleUserMode('post')}
                        className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                          userModes.includes('post')
                            ? 'bg-[#8D4B00] text-white border-[#8D4B00]'
                            : 'bg-white text-[#595E68] border-[#E5DED4]'
                        }`}
                      >
                        <Video className="w-3 h-3" />
                        <span>Published works (post)</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => toggleUserMode('like')}
                        className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                          userModes.includes('like')
                            ? 'bg-[#8D4B00] text-white border-[#8D4B00]'
                            : 'bg-white text-[#595E68] border-[#E5DED4]'
                        }`}
                      >
                        <Heart className="w-3 h-3" />
                        <span>Liked works (like)</span>
                      </button>
                    </div>
                  </div>

                  {/* Video limit */}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between">
                      <label className="text-[11px] font-semibold text-[#595E68]">
                        Video Download Limit
                      </label>
                      <span className="text-[10px] text-[#898174]">
                        {videoLimit === 0 ? 'Unlimited (All)' : `Max ${videoLimit} videos`}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        min={0}
                        max={5000}
                        step={10}
                        value={videoLimit}
                        onChange={(e) => setVideoLimit(Math.max(0, Number(e.target.value)))}
                        className="w-32 px-3 py-1.5 rounded-lg border border-[#E5DED4] bg-white text-xs font-mono text-[#1F2328] focus:outline-none focus:border-[#8D4B00]"
                      />
                      <div className="flex items-center gap-1">
                        {[0, 20, 50, 100].map((count) => (
                          <button
                            key={count}
                            type="button"
                            onClick={() => setVideoLimit(count)}
                            className={`px-2 py-1 text-[11px] rounded-md border ${
                              videoLimit === count
                                ? 'bg-[#F3ECE2] text-[#8D4B00] border-[#8D4B00] font-semibold'
                                : 'bg-white text-[#595E68] border-[#E5DED4]'
                            }`}
                          >
                            {count === 0 ? 'All' : count}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Date Range Picker */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-[11px] font-semibold text-[#595E68] flex items-center space-x-1">
                        <Calendar className="w-3 h-3 text-[#8D4B00]" />
                        <span>Publish Date Range</span>
                      </label>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      <div>
                        <span className="text-[10px] text-[#898174] block mb-0.5">Start Date:</span>
                        <input
                          type="date"
                          value={startTime}
                          onChange={(e) => setStartTime(e.target.value)}
                          className="w-full px-3 py-1.5 rounded-lg border border-[#E5DED4] bg-white text-xs font-mono text-[#1F2328] focus:outline-none focus:border-[#8D4B00]"
                        />
                      </div>

                      <div>
                        <span className="text-[10px] text-[#898174] block mb-0.5">End Date:</span>
                        <input
                          type="date"
                          value={endTime}
                          onChange={(e) => setEndTime(e.target.value)}
                          className="w-full px-3 py-1.5 rounded-lg border border-[#E5DED4] bg-white text-xs font-mono text-[#1F2328] focus:outline-none focus:border-[#8D4B00]"
                        />
                      </div>
                    </div>

                    {/* Quick date shortcuts */}
                    <div className="flex items-center gap-1.5 pt-1">
                      <span className="text-[10px] text-[#898174]">Quick pick:</span>
                      <button
                        type="button"
                        onClick={() => applyQuickDate('all')}
                        className="px-2 py-0.5 text-[10px] rounded bg-white hover:bg-[#F3ECE2] border border-[#E5DED4] text-[#595E68]"
                      >
                        All
                      </button>
                      <button
                        type="button"
                        onClick={() => applyQuickDate(7)}
                        className="px-2 py-0.5 text-[10px] rounded bg-white hover:bg-[#F3ECE2] border border-[#E5DED4] text-[#595E68]"
                      >
                        Last 7 days
                      </button>
                      <button
                        type="button"
                        onClick={() => applyQuickDate(30)}
                        className="px-2 py-0.5 text-[10px] rounded bg-white hover:bg-[#F3ECE2] border border-[#E5DED4] text-[#595E68]"
                      >
                        Last 30 days
                      </button>
                      <button
                        type="button"
                        onClick={() => applyQuickDate('this_year')}
                        className="px-2 py-0.5 text-[10px] rounded bg-white hover:bg-[#F3ECE2] border border-[#E5DED4] text-[#595E68]"
                      >
                        This year
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* 5. ADVANCED SETTINGS (THREADS & FOLDER STRUCTURE) */}
            <div className="rounded-xl border border-[#E5DED4] bg-[#FAF8F5]">
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="w-full px-4 py-3 flex items-center justify-between text-left text-xs font-semibold text-[#1F2328]"
              >
                <div className="flex items-center space-x-2">
                  <Cpu className="w-3.5 h-3.5 text-[#8D4B00]" />
                  <span>Advanced Settings (Workers & Folder Structure)</span>
                </div>
                {showAdvanced ? (
                  <ChevronUp className="w-4 h-4 text-[#898174]" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-[#898174]" />
                )}
              </button>

              {showAdvanced && (
                <div className="px-4 pb-4 pt-1 space-y-3.5 border-t border-[#E5DED4]/60 animate-fadeIn">
                  {/* Thread slider */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-[11px] font-semibold text-[#595E68]">
                        Concurrent Download Workers
                      </label>
                      <span className="font-mono text-xs font-bold text-[#8D4B00]">
                        {threadCount} workers
                      </span>
                    </div>
                    <div className="flex items-center space-x-3">
                      <span className="text-[11px] font-mono text-[#898174]">1</span>
                      <input
                        type="range"
                        min={1}
                        max={16}
                        value={threadCount}
                        onChange={(e) => setThreadCount(Number(e.target.value))}
                        className="flex-1 accent-[#8D4B00] h-1.5 bg-[#E5DED4] rounded-lg cursor-pointer"
                      />
                      <span className="text-[11px] font-mono text-[#898174]">16</span>
                    </div>
                  </div>

                  {/* Folder style */}
                  <div className="pt-1">
                    <label className="flex items-center space-x-2.5 text-xs text-[#1F2328] cursor-pointer">
                      <input
                        type="checkbox"
                        checked={folderStyle}
                        onChange={(e) => setFolderStyle(e.target.checked)}
                        className="accent-[#8D4B00] w-4 h-4 rounded"
                      />
                      <span>Organize each video into separate subfolder</span>
                    </label>
                  </div>
                </div>
              )}
            </div>

            {/* Bottom Actions Bar */}
            <div className="pt-2 flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-[#E5DED4]">
              <span className="text-xs text-[#898174]">
                Click start to begin downloading media files with current configuration.
              </span>

              <button
                type="button"
                onClick={handleStartDownload}
                disabled={downloading || !urlInput.trim()}
                className="w-full sm:w-auto flex items-center justify-center space-x-2 px-6 py-2.5 rounded-xl text-xs sm:text-sm font-bold bg-[#8D4B00] hover:bg-[#723C00] active:scale-[0.98] text-white shadow-md shadow-[#8D4B00]/25 disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer"
              >
                {downloading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Download className="w-4 h-4 stroke-[2.5]" />
                )}
                <span>START DOWNLOAD</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
