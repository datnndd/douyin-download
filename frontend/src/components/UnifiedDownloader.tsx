// frontend/src/components/UnifiedDownloader.tsx

import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle,
  Calendar,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Clipboard,
  Cpu,
  Disc,
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
  Play,
  Radio,
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

  // Photo gallery active index state
  const [selectedPhotoIdx, setSelectedPhotoIdx] = useState<number>(0);

  // Focus ref for date range pickers
  const startDateInputRef = useRef<HTMLInputElement>(null);

  // UI accordion state
  const [showUserFilters, setShowUserFilters] = useState<boolean>(false);
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);
  const [downloading, setDownloading] = useState<boolean>(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  // Auto-preview debounce ref
  const lastParsedUrlRef = useRef<string>('');

  // Reset selected photo when parsed content changes
  useEffect(() => {
    setSelectedPhotoIdx(0);
  }, [parsedData?.key]);

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

  const handleUrlChange = (val: string) => {
    setUrlInput(val);
    if (parseError) {
      setParseError(null);
    }
    if (parsedData) {
      setParsedData(null);
      lastParsedUrlRef.current = '';
    }
  };

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        setUrlInput(text.trim());
        setParseError(null);
        if (parsedData) {
          setParsedData(null);
          lastParsedUrlRef.current = '';
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

  const handleSetAllVideos = () => {
    setVideoLimit(0);
  };

  const handleSetRecent20 = () => {
    setVideoLimit(20);
  };

  const handleFocusDateFilter = () => {
    setShowUserFilters(true);
    setTimeout(() => {
      startDateInputRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      startDateInputRef.current?.focus();
    }, 120);
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
        allmix: videoLimit,
        mix: videoLimit,
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
    if (!num || isNaN(num) || num < 0) return '0';
    if (num >= 1000000000) return (num / 1000000000).toFixed(1) + 'B';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toLocaleString();
  };

  // ---------------------------------------------------------------------------
  // TAILORED PREVIEW CARDS RENDERERS
  // ---------------------------------------------------------------------------

  // 1. Creator Hero Profile Card (for key_type === 'user')
  const renderCreatorHeroCard = (preview: PreviewMetadata) => {
    const author = preview.author;
    const workCount = preview.work_count ?? 0;
    const followerCount =
      author?.follower_count ?? preview.statistics?.follower_count ?? 0;
    const totalLikes =
      author?.total_favorited ?? preview.statistics?.total_favorited ?? 0;
    const followingCount =
      author?.following_count ?? preview.statistics?.following_count ?? 0;
    const uniqueHandle =
      author?.unique_id || author?.short_id || '';
    const displaySecUid = author?.sec_uid || parsedData?.key || '';

    return (
      <div className="space-y-4 animate-fadeIn">
        {/* Creator Hero Header */}
        <div className="p-4 bg-[#FAF8F5] rounded-2xl border border-[#E5DED4] space-y-3.5">
          <div className="flex items-start gap-3.5">
            <div className="relative shrink-0">
              <img
                src={
                  author?.avatar ||
                  author?.avatar_thumb ||
                  preview.cover_url ||
                  '/avatar-placeholder.png'
                }
                alt={author?.nickname || 'Creator Avatar'}
                className="w-16 h-16 sm:w-20 sm:h-20 rounded-full object-cover border-2 border-[#8D4B00]/25 shadow-sm bg-white"
                onError={(e) => {
                  (e.target as HTMLElement).style.display = 'none';
                }}
              />
              <span className="absolute -bottom-1 -right-1 px-1.5 py-0.5 rounded-full bg-[#8D4B00] text-white text-[9px] font-bold uppercase tracking-wider shadow-xs">
                Creator
              </span>
            </div>

            <div className="overflow-hidden flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-sm sm:text-base font-bold text-[#1F2328] truncate">
                  {author?.nickname || preview.title || 'Douyin Creator'}
                </h3>
              </div>
              <div className="flex items-center gap-2 mt-0.5 text-[11px] text-[#595E68] font-mono">
                {uniqueHandle ? (
                  <span className="truncate bg-white px-2 py-0.5 rounded-md border border-[#E5DED4]">
                    {uniqueHandle.startsWith('@') ? uniqueHandle : `@${uniqueHandle}`}
                  </span>
                ) : null}
                {displaySecUid && (
                  <span
                    className="hidden sm:inline text-[10px] text-[#898174] truncate"
                    title={displaySecUid}
                  >
                    sec_uid: {displaySecUid.slice(0, 12)}...
                  </span>
                )}
              </div>

              {/* Bio quote box */}
              <div className="mt-2 p-2.5 rounded-xl bg-white border border-[#E5DED4] text-xs text-[#595E68] italic leading-relaxed line-clamp-3">
                "{author?.signature || preview.desc || 'No bio available'}"
              </div>
            </div>
          </div>

          {/* 4 Key Metric Badges */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
            {/* Total Videos / Works - Highlighted in Terracotta Accent */}
            <div className="p-2.5 rounded-xl bg-[#F3ECE2] border border-[#8D4B00]/40 text-center shadow-xs">
              <div className="flex items-center justify-center space-x-1 text-[#8D4B00] mb-0.5">
                <Video className="w-3.5 h-3.5 stroke-[2.5]" />
                <span className="text-sm sm:text-base font-extrabold font-mono">
                  {formatNumber(workCount)}
                </span>
              </div>
              <span className="text-[10px] sm:text-[11px] font-bold text-[#8D4B00] uppercase tracking-wide">
                Total Videos
              </span>
            </div>

            {/* Followers */}
            <div className="p-2.5 rounded-xl bg-white border border-[#E5DED4] text-center">
              <div className="flex items-center justify-center space-x-1 text-[#1F2328] mb-0.5">
                <Users className="w-3.5 h-3.5 text-[#898174]" />
                <span className="text-sm sm:text-base font-bold font-mono">
                  {formatNumber(followerCount)}
                </span>
              </div>
              <span className="text-[10px] sm:text-[11px] text-[#898174]">Followers</span>
            </div>

            {/* Total Likes */}
            <div className="p-2.5 rounded-xl bg-white border border-[#E5DED4] text-center">
              <div className="flex items-center justify-center space-x-1 text-rose-600 mb-0.5">
                <Heart className="w-3.5 h-3.5 fill-rose-600" />
                <span className="text-sm sm:text-base font-bold font-mono">
                  {formatNumber(totalLikes)}
                </span>
              </div>
              <span className="text-[10px] sm:text-[11px] text-[#898174]">Total Likes</span>
            </div>

            {/* Following */}
            <div className="p-2.5 rounded-xl bg-white border border-[#E5DED4] text-center">
              <div className="flex items-center justify-center space-x-1 text-[#595E68] mb-0.5">
                <User className="w-3.5 h-3.5 text-[#898174]" />
                <span className="text-sm sm:text-base font-bold font-mono">
                  {formatNumber(followingCount)}
                </span>
              </div>
              <span className="text-[10px] sm:text-[11px] text-[#898174]">Following</span>
            </div>
          </div>

          {/* Quick Action Buttons directly inside Creator Card */}
          <div className="pt-2 border-t border-[#E5DED4]/70 flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-semibold text-[#898174]">Quick Presets:</span>
            <button
              type="button"
              onClick={handleSetAllVideos}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer ${
                videoLimit === 0
                  ? 'bg-[#8D4B00] text-white border-[#8D4B00] shadow-xs'
                  : 'bg-white text-[#595E68] border-[#E5DED4] hover:bg-[#F3ECE2] hover:text-[#8D4B00]'
              }`}
            >
              Download All ({workCount > 0 ? formatNumber(workCount) : 'All'})
            </button>
            <button
              type="button"
              onClick={handleSetRecent20}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer ${
                videoLimit === 20
                  ? 'bg-[#8D4B00] text-white border-[#8D4B00] shadow-xs'
                  : 'bg-white text-[#595E68] border-[#E5DED4] hover:bg-[#F3ECE2] hover:text-[#8D4B00]'
              }`}
            >
              Recent 20
            </button>
            <button
              type="button"
              onClick={handleFocusDateFilter}
              className="flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs font-semibold bg-white text-[#8D4B00] border border-[#E5DED4] hover:bg-[#F3ECE2] transition-all cursor-pointer"
            >
              <Calendar className="w-3.5 h-3.5" />
              <span>Filter by Date Range</span>
            </button>
          </div>
        </div>
      </div>
    );
  };

  // 2. Single Video Card (for aweme video)
  const renderVideoCard = (preview: PreviewMetadata) => {
    return (
      <div className="space-y-4 animate-fadeIn">
        {/* Aspect Ratio Video Card with Play Overlay */}
        <div className="relative rounded-2xl overflow-hidden border border-[#E5DED4] bg-black/5 aspect-video flex items-center justify-center group shadow-sm">
          {preview.cover_url ? (
            <img
              src={preview.cover_url}
              alt={preview.title}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            />
          ) : (
            <Film className="w-12 h-12 text-[#898174]" />
          )}

          {/* Quality badge */}
          <span className="absolute top-2.5 left-2.5 px-2.5 py-1 bg-black/60 backdrop-blur-xs text-white font-semibold text-[10px] rounded-lg tracking-wide uppercase">
            Video • 1080p HD
          </span>

          {/* Play Button Overlay */}
          <div className="absolute inset-0 flex items-center justify-center bg-black/20 group-hover:bg-black/30 transition-all">
            <div className="w-12 h-12 rounded-full bg-black/60 backdrop-blur-sm flex items-center justify-center text-white shadow-lg group-hover:scale-110 group-hover:bg-[#8D4B00] transition-all">
              <Play className="w-5 h-5 fill-white ml-0.5" />
            </div>
          </div>

          {/* Duration Badge */}
          {preview.duration ? (
            <span className="absolute bottom-2.5 right-2.5 px-2 py-0.5 bg-black/75 text-white font-mono text-[10px] font-semibold rounded-md backdrop-blur-xs">
              {Math.floor(preview.duration / 60)}:
              {(preview.duration % 60).toString().padStart(2, '0')}
            </span>
          ) : null}
        </div>

        {/* Creator Chip */}
        {preview.author && (
          <div className="flex items-center space-x-3 p-2.5 bg-[#FAF8F5] rounded-xl border border-[#E5DED4]">
            <img
              src={preview.author.avatar_thumb || preview.author.avatar || '/avatar-placeholder.png'}
              alt={preview.author.nickname}
              className="w-9 h-9 rounded-full object-cover border border-[#E5DED4]"
              onError={(e) => {
                (e.target as HTMLElement).style.display = 'none';
              }}
            />
            <div className="overflow-hidden flex-1">
              <h4 className="text-xs font-bold text-[#1F2328] truncate">
                {preview.author.nickname}
              </h4>
              <p className="text-[10px] text-[#595E68] font-mono truncate">
                {preview.author.unique_id
                  ? `@${preview.author.unique_id}`
                  : `ID: ${preview.author.short_id || parsedData?.key}`}
              </p>
            </div>
          </div>
        )}

        {/* Title Description */}
        <div>
          <h3 className="text-xs sm:text-sm font-semibold text-[#1F2328] line-clamp-3">
            {preview.title || preview.desc || 'Douyin Video'}
          </h3>
        </div>

        {/* 4 Engagement Stats */}
        <div className="grid grid-cols-4 gap-2 pt-2 border-t border-[#E5DED4] text-center">
          <div className="p-2 rounded-lg bg-[#FAF8F5] border border-[#E5DED4]/60">
            <div className="flex items-center justify-center space-x-1 text-rose-600 text-[11px] font-semibold">
              <Heart className="w-3 h-3 fill-rose-600" />
              <span>{formatNumber(preview.statistics?.digg_count)}</span>
            </div>
            <span className="text-[10px] text-[#898174]">Likes</span>
          </div>
          <div className="p-2 rounded-lg bg-[#FAF8F5] border border-[#E5DED4]/60">
            <div className="flex items-center justify-center space-x-1 text-[#8D4B00] text-[11px] font-semibold">
              <MessageCircle className="w-3 h-3" />
              <span>{formatNumber(preview.statistics?.comment_count)}</span>
            </div>
            <span className="text-[10px] text-[#898174]">Comments</span>
          </div>
          <div className="p-2 rounded-lg bg-[#FAF8F5] border border-[#E5DED4]/60">
            <div className="flex items-center justify-center space-x-1 text-[#595E68] text-[11px] font-semibold">
              <Share2 className="w-3 h-3" />
              <span>{formatNumber(preview.statistics?.share_count)}</span>
            </div>
            <span className="text-[10px] text-[#898174]">Shares</span>
          </div>
          <div className="p-2 rounded-lg bg-[#FAF8F5] border border-[#E5DED4]/60">
            <div className="flex items-center justify-center space-x-1 text-amber-600 text-[11px] font-semibold">
              <Layers className="w-3 h-3" />
              <span>{formatNumber(preview.statistics?.collect_count)}</span>
            </div>
            <span className="text-[10px] text-[#898174]">Collects</span>
          </div>
        </div>
      </div>
    );
  };

  // 3. Photo Album Card (for image note / album)
  const renderPhotoAlbumCard = (preview: PreviewMetadata) => {
    const imagesList =
      preview.images && preview.images.length > 0
        ? preview.images
        : preview.cover_url
        ? [preview.cover_url]
        : [];
    const activePhoto = imagesList[selectedPhotoIdx] || imagesList[0] || preview.cover_url || '';
    const totalPhotos = preview.work_count || imagesList.length || 1;

    return (
      <div className="space-y-4 animate-fadeIn">
        {/* Main Display Image */}
        <div className="relative rounded-2xl overflow-hidden border border-[#E5DED4] bg-black/5 aspect-video flex items-center justify-center group shadow-sm">
          {activePhoto ? (
            <img
              src={activePhoto}
              alt={preview.title}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
              onError={(e) => {
                (e.target as HTMLElement).style.display = 'none';
              }}
            />
          ) : (
            <ImageIcon className="w-12 h-12 text-[#898174]" />
          )}

          {/* Multi-Photo Badge */}
          <span className="absolute top-2.5 left-2.5 px-2.5 py-1 bg-black/65 backdrop-blur-xs text-white font-semibold text-[10px] rounded-lg tracking-wide flex items-center space-x-1">
            <ImageIcon className="w-3 h-3" />
            <span>Album • {totalPhotos} Photos</span>
          </span>

          {/* Previous / Next Arrow Controls */}
          {imagesList.length > 1 && (
            <>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedPhotoIdx((prev) => (prev > 0 ? prev - 1 : imagesList.length - 1));
                }}
                className="absolute left-2.5 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-black/60 hover:bg-[#8D4B00] text-white flex items-center justify-center backdrop-blur-xs opacity-75 group-hover:opacity-100 transition-all cursor-pointer shadow-md"
                title="Previous photo"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedPhotoIdx((prev) => (prev < imagesList.length - 1 ? prev + 1 : 0));
                }}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-black/60 hover:bg-[#8D4B00] text-white flex items-center justify-center backdrop-blur-xs opacity-75 group-hover:opacity-100 transition-all cursor-pointer shadow-md"
                title="Next photo"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </>
          )}

          {/* Photo Counter */}
          <span className="absolute bottom-2.5 right-2.5 px-2 py-0.5 bg-black/75 text-white font-mono text-[10px] font-semibold rounded-md backdrop-blur-xs">
            Photo {selectedPhotoIdx + 1} / {imagesList.length || 1}
          </span>
        </div>

        {/* Thumbnail Carousel / Grid */}
        {imagesList.length > 1 && (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-[11px] text-[#898174]">
              <span>Album Carousel ({imagesList.length} photos)</span>
              <span>Click to view</span>
            </div>
            <div className="flex items-center gap-2 overflow-x-auto pb-1.5 pt-0.5 scrollbar-thin">
              {imagesList.map((imgUrl, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setSelectedPhotoIdx(idx)}
                  className={`relative shrink-0 w-14 h-14 rounded-xl overflow-hidden border transition-all cursor-pointer ${
                    selectedPhotoIdx === idx
                      ? 'ring-2 ring-[#8D4B00] border-transparent shadow-xs scale-105'
                      : 'border-[#E5DED4] opacity-70 hover:opacity-100 hover:border-[#8D4B00]'
                  }`}
                >
                  <img
                    src={imgUrl}
                    alt={`Thumb ${idx + 1}`}
                    className="w-full h-full object-cover"
                  />
                  <span className="absolute bottom-0.5 right-1 text-[8px] font-mono text-white bg-black/60 px-1 rounded">
                    {idx + 1}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Creator Chip */}
        {preview.author && (
          <div className="flex items-center space-x-3 p-2.5 bg-[#FAF8F5] rounded-xl border border-[#E5DED4]">
            <img
              src={preview.author.avatar_thumb || preview.author.avatar || '/avatar-placeholder.png'}
              alt={preview.author.nickname}
              className="w-9 h-9 rounded-full object-cover border border-[#E5DED4]"
              onError={(e) => {
                (e.target as HTMLElement).style.display = 'none';
              }}
            />
            <div className="overflow-hidden flex-1">
              <h4 className="text-xs font-bold text-[#1F2328] truncate">
                {preview.author.nickname}
              </h4>
              <p className="text-[10px] text-[#595E68] font-mono truncate">
                {preview.author.unique_id
                  ? `@${preview.author.unique_id}`
                  : `ID: ${preview.author.short_id || parsedData?.key}`}
              </p>
            </div>
          </div>
        )}

        {/* Title Description */}
        <div>
          <h3 className="text-xs sm:text-sm font-semibold text-[#1F2328] line-clamp-3">
            {preview.title || preview.desc || 'Douyin Photo Album'}
          </h3>
        </div>

        {/* 4 Engagement Stats */}
        <div className="grid grid-cols-4 gap-2 pt-2 border-t border-[#E5DED4] text-center">
          <div className="p-2 rounded-lg bg-[#FAF8F5] border border-[#E5DED4]/60">
            <div className="flex items-center justify-center space-x-1 text-rose-600 text-[11px] font-semibold">
              <Heart className="w-3 h-3 fill-rose-600" />
              <span>{formatNumber(preview.statistics?.digg_count)}</span>
            </div>
            <span className="text-[10px] text-[#898174]">Likes</span>
          </div>
          <div className="p-2 rounded-lg bg-[#FAF8F5] border border-[#E5DED4]/60">
            <div className="flex items-center justify-center space-x-1 text-[#8D4B00] text-[11px] font-semibold">
              <MessageCircle className="w-3 h-3" />
              <span>{formatNumber(preview.statistics?.comment_count)}</span>
            </div>
            <span className="text-[10px] text-[#898174]">Comments</span>
          </div>
          <div className="p-2 rounded-lg bg-[#FAF8F5] border border-[#E5DED4]/60">
            <div className="flex items-center justify-center space-x-1 text-[#595E68] text-[11px] font-semibold">
              <Share2 className="w-3 h-3" />
              <span>{formatNumber(preview.statistics?.share_count)}</span>
            </div>
            <span className="text-[10px] text-[#898174]">Shares</span>
          </div>
          <div className="p-2 rounded-lg bg-[#FAF8F5] border border-[#E5DED4]/60">
            <div className="flex items-center justify-center space-x-1 text-amber-600 text-[11px] font-semibold">
              <Layers className="w-3 h-3" />
              <span>{formatNumber(preview.statistics?.collect_count)}</span>
            </div>
            <span className="text-[10px] text-[#898174]">Collects</span>
          </div>
        </div>
      </div>
    );
  };

  // 4. Collection / Mix Card
  const renderCollectionCard = (preview: PreviewMetadata) => {
    const episodeCount =
      preview.work_count || preview.extra?.updated_to_episode || 1;

    return (
      <div className="space-y-4 animate-fadeIn">
        {/* Album Sleeve Design */}
        <div className="relative p-4 rounded-2xl bg-[#FAF8F5] border-2 border-[#E5DED4] shadow-sm space-y-3">
          {/* Top Badge */}
          <div className="flex items-center justify-between">
            <span className="px-2.5 py-1 bg-[#8D4B00] text-white font-bold text-[10px] rounded-lg uppercase tracking-wider flex items-center space-x-1 shadow-xs">
              <Layers className="w-3 h-3" />
              <span>Collection • {episodeCount} Episodes</span>
            </span>
            <span className="text-[11px] font-mono text-[#898174]">
              Mix ID: {parsedData?.key}
            </span>
          </div>

          {/* Sleeve Cover Container with Stacked Layers */}
          <div className="relative aspect-video rounded-xl overflow-hidden border border-[#E5DED4] bg-white flex items-center justify-center group shadow-sm">
            {preview.cover_url ? (
              <img
                src={preview.cover_url}
                alt={preview.title}
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
              />
            ) : (
              <Layers className="w-12 h-12 text-[#898174]" />
            )}
            <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent flex items-end p-3">
              <p className="text-white text-xs font-semibold line-clamp-1">
                {preview.title}
              </p>
            </div>
          </div>

          {/* Title & Status */}
          <div className="space-y-1">
            <h3 className="text-sm font-bold text-[#1F2328]">
              {preview.title}
            </h3>
            <p className="text-xs text-[#595E68]">
              {preview.desc || `Collection updated to episode ${episodeCount}`}
            </p>
          </div>

          {/* Author Chip */}
          {preview.author && (
            <div className="flex items-center space-x-2.5 pt-2 border-t border-[#E5DED4]">
              <img
                src={preview.author.avatar_thumb || preview.author.avatar || '/avatar-placeholder.png'}
                alt={preview.author.nickname}
                className="w-7 h-7 rounded-full object-cover border border-[#E5DED4]"
                onError={(e) => {
                  (e.target as HTMLElement).style.display = 'none';
                }}
              />
              <span className="text-xs font-medium text-[#1F2328]">
                Curated by <strong className="font-semibold">{preview.author.nickname}</strong>
              </span>
            </div>
          )}
        </div>
      </div>
    );
  };

  // 5. Soundtrack / Music Card
  const renderMusicCard = (preview: PreviewMetadata) => {
    return (
      <div className="space-y-4 animate-fadeIn">
        {/* Vinyl Disc Theme Card */}
        <div className="p-4 rounded-2xl bg-[#FAF8F5] border-2 border-[#E5DED4] shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <span className="px-2.5 py-1 bg-[#8D4B00] text-white font-bold text-[10px] rounded-lg uppercase tracking-wider flex items-center space-x-1 shadow-xs">
              <Music className="w-3 h-3" />
              <span>Original Soundtrack</span>
            </span>
            <span className="text-[11px] font-mono text-[#898174]">
              Music ID: {parsedData?.key}
            </span>
          </div>

          {/* Vinyl Disc Display */}
          <div className="flex items-center justify-center py-4">
            <div className="relative flex items-center">
              {/* Cover Jacket */}
              <div className="w-32 h-32 rounded-xl overflow-hidden border-2 border-[#E5DED4] shadow-md z-10 bg-white">
                {preview.cover_url ? (
                  <img
                    src={preview.cover_url}
                    alt={preview.title}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-[#F3ECE2] text-[#8D4B00]">
                    <Music className="w-10 h-10" />
                  </div>
                )}
              </div>

              {/* Styled Vinyl Record Peeking Out */}
              <div className="w-28 h-28 -ml-12 rounded-full bg-neutral-900 border-4 border-neutral-800 shadow-xl flex items-center justify-center animate-[spin_12s_linear_infinite]">
                {/* Vinyl Grooves */}
                <div className="w-20 h-20 rounded-full border border-neutral-700/60 flex items-center justify-center">
                  <div className="w-14 h-14 rounded-full border border-neutral-700/60 flex items-center justify-center">
                    {/* Vinyl Center Label */}
                    <div className="w-8 h-8 rounded-full bg-[#8D4B00] flex items-center justify-center text-white">
                      <Disc className="w-4 h-4" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Song Title & Musician */}
          <div className="text-center space-y-1">
            <h3 className="text-sm sm:text-base font-bold text-[#1F2328]">
              {preview.title}
            </h3>
            <p className="text-xs text-[#595E68]">
              By <strong className="font-semibold text-[#8D4B00]">{preview.author?.nickname || 'Original Artist'}</strong>
            </p>
          </div>

          {/* Use Count Badge */}
          <div className="p-2.5 rounded-xl bg-white border border-[#E5DED4] text-center">
            <span className="text-xs font-semibold text-[#8D4B00]">
              🎵 {formatNumber(preview.work_count || 1)} Public Works
            </span>
            <span className="text-[11px] text-[#898174] block">
              Created using this soundtrack audio
            </span>
          </div>
        </div>
      </div>
    );
  };

  // 6. Live Stream Card
  const renderLiveCard = (preview: PreviewMetadata) => {
    const isLive =
      preview.extra?.is_live ||
      preview.extra?.status === '2' ||
      preview.desc?.toLowerCase().includes('live streaming');

    return (
      <div className="space-y-4 animate-fadeIn">
        {/* Live Card */}
        <div className="p-4 rounded-2xl bg-[#FAF8F5] border-2 border-[#E5DED4] shadow-sm space-y-3.5">
          {/* Status Badge */}
          <div className="flex items-center justify-between">
            {isLive ? (
              <div className="flex items-center space-x-2 px-3 py-1 rounded-full bg-rose-50 border border-rose-200 text-rose-700 text-xs font-bold shadow-xs">
                <span className="relative flex h-2.5 w-2.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-rose-600"></span>
                </span>
                <span>🔴 LIVE STREAMING</span>
              </div>
            ) : (
              <div className="flex items-center space-x-1.5 px-3 py-1 rounded-full bg-gray-100 border border-gray-200 text-gray-600 text-xs font-bold">
                <span>STREAM ENDED</span>
              </div>
            )}

            <span className="text-[11px] font-mono text-[#898174]">
              Room: {parsedData?.key}
            </span>
          </div>

          {/* Stream Frame / Cover */}
          <div className="relative aspect-video rounded-xl overflow-hidden border border-[#E5DED4] bg-neutral-900 flex items-center justify-center group shadow-sm">
            {preview.cover_url ? (
              <img
                src={preview.cover_url}
                alt={preview.title}
                className="w-full h-full object-cover"
              />
            ) : (
              <Radio className="w-12 h-12 text-[#898174]" />
            )}
            {isLive && (
              <div className="absolute top-2.5 right-2.5 px-2 py-0.5 rounded-md bg-black/70 backdrop-blur-xs text-white text-[10px] font-mono font-semibold flex items-center space-x-1">
                <Users className="w-3 h-3 text-rose-400" />
                <span>
                  {formatNumber(preview.statistics?.play_count || preview.extra?.user_count || 0)} Viewers
                </span>
              </div>
            )}
          </div>

          {/* Streamer Avatar & Room Title */}
          <div className="space-y-1.5">
            <div className="flex items-center space-x-2.5">
              <img
                src={preview.author?.avatar_thumb || preview.author?.avatar || '/avatar-placeholder.png'}
                alt={preview.author?.nickname || 'Streamer'}
                className="w-8 h-8 rounded-full object-cover border border-[#E5DED4]"
                onError={(e) => {
                  (e.target as HTMLElement).style.display = 'none';
                }}
              />
              <div className="overflow-hidden flex-1">
                <h4 className="text-xs font-bold text-[#1F2328] truncate">
                  {preview.author?.nickname || 'Streamer'}
                </h4>
                <p className="text-[11px] text-[#8D4B00] font-medium truncate">
                  Category: {preview.extra?.partition || 'Live Broadcasting'}
                </p>
              </div>
            </div>

            <h3 className="text-xs sm:text-sm font-semibold text-[#1F2328] line-clamp-2">
              {preview.title}
            </h3>
          </div>
        </div>
      </div>
    );
  };

  // Dispatcher for tailored cards
  const renderTailoredPreviewCard = () => {
    if (!parsedData?.preview) {
      return (
        <div className="p-6 rounded-2xl bg-[#FAF8F5] border border-[#E5DED4] text-center space-y-2">
          <Film className="w-8 h-8 text-[#8D4B00] mx-auto" />
          <h4 className="text-xs font-bold text-[#1F2328]">
            Metadata Resolved: {parsedData?.key_type.toUpperCase()}
          </h4>
          <p className="text-[11px] text-[#595E68] font-mono">
            Key: {parsedData?.key}
          </p>
        </div>
      );
    }
    const { preview, key_type, content_type } = parsedData;

    if (key_type === 'user') {
      return renderCreatorHeroCard(preview);
    }
    if (key_type === 'mix') {
      return renderCollectionCard(preview);
    }
    if (key_type === 'music') {
      return renderMusicCard(preview);
    }
    if (key_type === 'live') {
      return renderLiveCard(preview);
    }
    if (content_type === 'image' || (preview.images && preview.images.length > 0)) {
      return renderPhotoAlbumCard(preview);
    }
    return renderVideoCard(preview);
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
              onChange={(e) => handleUrlChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleParse();
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
                  className="p-1 rounded-md text-[#898174] hover:text-[#1F2328] hover:bg-[#E5DED4]/50 transition-colors cursor-pointer"
                  title="Clear input"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
              <button
                type="button"
                onClick={handlePaste}
                className="flex items-center space-x-1 px-2 py-1 rounded-md text-xs font-medium text-[#8D4B00] bg-[#F3ECE2] hover:bg-[#EDE5DA] transition-colors cursor-pointer"
                title="Paste from clipboard"
              >
                <Clipboard className="w-3.5 h-3.5" />
                <span className="hidden md:inline">Paste</span>
              </button>
            </div>
          </div>

          {/* Right Action Button: Primary CTA Analyze & Preview */}
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => handleParse()}
              disabled={parsing || !urlInput.trim()}
              className="w-full sm:w-auto flex items-center justify-center space-x-2 px-5 py-2.5 rounded-xl text-xs sm:text-sm font-bold bg-[#8D4B00] hover:bg-[#723C00] active:scale-[0.98] text-white shadow-md shadow-[#8D4B00]/25 disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer"
              title="Inspect & preview content metadata"
            >
              {parsing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Eye className="w-4 h-4 stroke-[2.5]" />
              )}
              <span>Analyze &amp; Preview</span>
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
      {/* 2. CONDITIONAL VIEW: CLEAN PLACEHOLDER OR SPLIT WORKSPACE            */}
      {/* ==================================================================== */}
      {!parsedData ? (
        <div className="bg-white border border-[#E5DED4] rounded-2xl p-8 sm:p-12 shadow-sm text-center space-y-6 animate-fadeIn">
          {parsing ? (
            <div className="space-y-4 py-6">
              <div className="w-16 h-16 rounded-2xl bg-[#F3ECE2] text-[#8D4B00] mx-auto flex items-center justify-center shadow-xs">
                <Loader2 className="w-8 h-8 animate-spin" />
              </div>
              <div className="max-w-md mx-auto space-y-2">
                <h3 className="text-base sm:text-lg font-bold text-[#1F2328]">
                  Analyzing Link &amp; Fetching Preview...
                </h3>
                <p className="text-xs sm:text-sm text-[#595E68] leading-relaxed">
                  Connecting to Douyin to resolve creator details, work counts, and media assets.
                </p>
              </div>
            </div>
          ) : (
            <>
              <div className="w-16 h-16 rounded-2xl bg-[#F3ECE2] text-[#8D4B00] mx-auto flex items-center justify-center shadow-xs">
                <Sparkles className="w-8 h-8" />
              </div>

              <div className="max-w-md mx-auto space-y-2">
                <h3 className="text-base sm:text-lg font-bold text-[#1F2328]">
                  Ready to Download? Preview First.
                </h3>
                <p className="text-xs sm:text-sm text-[#595E68] leading-relaxed">
                  Paste your Douyin video, creator profile, album, or playlist link above and click{' '}
                  <strong className="text-[#8D4B00]">Analyze &amp; Preview</strong> to inspect creator stats, total video counts, and configure download options.
                </p>
              </div>

          {/* Supported Content Badges */}
          <div className="pt-2">
            <p className="text-[11px] font-semibold text-[#898174] uppercase tracking-wider mb-3">
              Supported Content Types
            </p>
            <div className="flex flex-wrap items-center justify-center gap-2 max-w-xl mx-auto">
              <span className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-[#FAF8F5] border border-[#E5DED4] text-xs font-medium text-[#1F2328]">
                <Video className="w-3.5 h-3.5 text-[#8D4B00]" />
                <span>Single Videos</span>
              </span>
              <span className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-[#FAF8F5] border border-[#E5DED4] text-xs font-medium text-[#1F2328]">
                <ImageIcon className="w-3.5 h-3.5 text-[#8D4B00]" />
                <span>Photo Albums</span>
              </span>
              <span className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-[#FAF8F5] border border-[#E5DED4] text-xs font-medium text-[#1F2328]">
                <User className="w-3.5 h-3.5 text-[#8D4B00]" />
                <span>Creator Profiles</span>
              </span>
              <span className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-[#FAF8F5] border border-[#E5DED4] text-xs font-medium text-[#1F2328]">
                <Layers className="w-3.5 h-3.5 text-[#8D4B00]" />
                <span>Collections &amp; Series</span>
              </span>
              <span className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-[#FAF8F5] border border-[#E5DED4] text-xs font-medium text-[#1F2328]">
                <Music className="w-3.5 h-3.5 text-[#8D4B00]" />
                <span>Soundtracks</span>
              </span>
              <span className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-[#FAF8F5] border border-[#E5DED4] text-xs font-medium text-[#1F2328]">
                <Radio className="w-3.5 h-3.5 text-[#8D4B00]" />
                <span>Live Streams</span>
              </span>
            </div>
          </div>
        </>
      )}
    </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* ------------------------------------------------------------------ */}
          {/* LEFT COLUMN: TAILORED LIVE METADATA PREVIEW (5 cols)               */}
          {/* ------------------------------------------------------------------ */}
          <div className="lg:col-span-5 bg-white border border-[#E5DED4] rounded-2xl p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-[#E5DED4]">
              <div className="flex items-center space-x-2">
                <Sparkles className="w-4 h-4 text-[#8D4B00]" />
                <h2 className="text-sm font-bold text-[#1F2328]">
                  {parsedData.key_type === 'user' ? 'Creator Profile Preview' : 'Detected Content Preview'}
                </h2>
              </div>
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-[#F3ECE2] text-[#8D4B00] border border-[#E5DED4] uppercase">
                {parsedData.key_type}
              </span>
            </div>

            {renderTailoredPreviewCard()}
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
                          ref={startDateInputRef}
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
    )}
  </div>
);
};
