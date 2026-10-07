// frontend/src/components/Step1Preview.tsx

import React, { useState } from 'react';
import {
  AlertCircle,
  ArrowRight,
  Clipboard,
  ExternalLink,
  Eye,
  FileText,
  Film,
  Heart,
  Image as ImageIcon,
  Loader2,
  MessageCircle,
  Radio,
  Search,
  Share2,
  Sparkles,
  User,
  Users,
  Video,
} from 'lucide-react';
import { ParseResponse, PreviewMetadata } from '../types/api';
import { api } from '../services/api';

/**
 * Extracts clean Douyin or HTTP URL from raw clipboard text, Kouling tokens, or share messages.
 * e.g. "0.23 C@u.sr :0pm 01/04 TLJ:/ Catching seafood fresh... https://v.douyin.com/meBXuCMU5l0/ Copy this link..."
 */
export const extractDouyinUrl = (text: string): string => {
  if (!text || !text.trim()) return '';
  // 1. Prioritize Douyin ecosystem link (v.douyin.com, douyin.com, iesdouyin.com)
  const douyinMatch = text.match(/(?:https?:\/\/)?(?:[a-zA-Z0-9\-]+\.)?(?:douyin\.com|iesdouyin\.com)\/[a-zA-Z0-9_./\-?&=%#+:@!~*]*/i);
  const punctuationStrip = /[),.!?，。！？;；:：'"【】（）《》、~\s]+$/;
  if (douyinMatch) {
    let url = douyinMatch[0].replace(punctuationStrip, '');
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      url = 'https://' + url;
    }
    return url;
  }
  // 2. Generic http/https match
  const genericMatch = text.match(/https?:\/\/[a-zA-Z0-9_./\-?&=%#+:@!~*]+/i);
  if (genericMatch) {
    return genericMatch[0].replace(punctuationStrip, '');
  }
  return text.trim();
};

interface Step1PreviewProps {
  onProceedToConfig: (parseData: ParseResponse) => void;
  initialUrl?: string;
  cookieOverride?: string;
}

export const Step1Preview: React.FC<Step1PreviewProps> = ({
  onProceedToConfig,
  initialUrl = '',
  cookieOverride,
}) => {
  const [urlInput, setUrlInput] = useState(initialUrl);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [parsedData, setParsedData] = useState<ParseResponse | null>(null);

  // Detect whether the input contains messy share text with an extractable URL
  const detectedUrl = React.useMemo(() => {
    const extracted = extractDouyinUrl(urlInput);
    return extracted && extracted !== urlInput.trim() ? extracted : null;
  }, [urlInput]);

  const formatNumber = (num: number = 0): string => {
    if (num >= 1000000000) return (num / 1000000000).toFixed(1) + 'B';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toLocaleString();
  };

  const handleParse = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = urlInput.trim();
    if (!trimmed) {
      setError('Please enter a Douyin share link or text');
      return;
    }

    // Auto-extract clean URL from share text
    const cleanUrl = extractDouyinUrl(trimmed) || trimmed;
    if (cleanUrl !== trimmed) {
      setUrlInput(cleanUrl);
    }

    setLoading(true);
    setError(null);
    try {
      const res = await api.parseUrl(cleanUrl, cookieOverride);
      if (!res.success) {
        setError(res.error || 'Failed to parse link metadata');
      } else {
        setParsedData(res);
      }
    } catch (err: any) {
      setError(err.message || 'Network error: unable to connect to parsing engine');
    } finally {
      setLoading(false);
    }
  };

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        setUrlInput(text);
        const clean = extractDouyinUrl(text);
        if (clean && clean !== text.trim()) {
          // If clean link found, automatically set to clean URL
          setUrlInput(clean);
        }
      }
    } catch {
      // clipboard access denied
    }
  };

  const getTypeIcon = (keyType: string, contentType: string) => {
    if (keyType === 'user') return <Users className="w-4 h-4 text-[#8D4B00]" />;
    if (keyType === 'live') return <Radio className="w-4 h-4 text-rose-600 animate-pulse" />;
    if (contentType === 'image') return <ImageIcon className="w-4 h-4 text-amber-600" />;
    return <Film className="w-4 h-4 text-[#8D4B00]" />;
  };

  const getTypeBadge = (keyType: string, contentType: string) => {
    if (keyType === 'user') {
      return (
        <span className="px-2 py-0.5 rounded-md bg-[#F3ECE2] text-[#8D4B00] border border-[#E5DED4] text-[11px] font-semibold flex items-center gap-1">
          <Users className="w-3 h-3" /> User Profile
        </span>
      );
    }
    if (keyType === 'mix') {
      return (
        <span className="px-2 py-0.5 rounded-md bg-[#F3ECE2] text-[#8D4B00] border border-[#E5DED4] text-[11px] font-semibold flex items-center gap-1">
          <Film className="w-3 h-3" /> Mix Collection
        </span>
      );
    }
    if (keyType === 'live') {
      return (
        <span className="px-2 py-0.5 rounded-md bg-rose-50 text-rose-700 border border-rose-200 text-[11px] font-semibold flex items-center gap-1">
          <Radio className="w-3 h-3" /> Live Stream
        </span>
      );
    }
    if (contentType === 'image') {
      return (
        <span className="px-2 py-0.5 rounded-md bg-amber-50 text-amber-700 border border-amber-200 text-[11px] font-semibold flex items-center gap-1">
          <ImageIcon className="w-3 h-3" /> Image Album
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 text-[11px] font-semibold flex items-center gap-1">
        <Film className="w-3 h-3" /> Single Video
      </span>
    );
  };

  const preview = parsedData?.preview;

  return (
    <div className="space-y-6">
      {/* Search & Parse Input Box */}
      <div className="bg-[#FFFFFF] border border-[#E5DED4] rounded-2xl p-6 shadow-sm">
        <div className="mb-3">
          <h2 className="text-sm font-semibold text-[#1F2328] flex items-center space-x-2">
            <span className="w-2 h-2 rounded-full bg-[#8D4B00]" />
            <span>Step 1: Enter Douyin share link</span>
          </h2>
          <p className="text-xs text-[#595E68] mt-1">
            Supports standard URLs, short links (v.douyin.com), or raw text pasted from mobile share
          </p>
        </div>

        <form onSubmit={handleParse} className="space-y-3">
          <div className="relative">
            <textarea
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="Paste Douyin share link or text (https://v.douyin.com/... or https://www.douyin.com/user/...)"
              rows={3}
              className="w-full px-4 py-3 rounded-xl border border-[#E5DED4] bg-[#FAF8F5] text-xs text-[#1F2328] placeholder-[#898174]/70 focus:outline-none focus:ring-2 focus:ring-[#8D4B00]/20 focus:border-[#8D4B00] transition-all resize-none"
            />
            {urlInput && (
              <button
                type="button"
                onClick={() => setUrlInput('')}
                className="absolute top-2.5 right-3 text-xs text-[#898174] hover:text-[#1F2328] transition-colors"
              >
                Clear
              </button>
            )}
          </div>

          {detectedUrl && (
            <div className="flex items-center justify-between px-3 py-2 rounded-xl bg-[#FAF6F0] border border-[#E5DED4] text-xs animate-fadeIn">
              <div className="flex items-center space-x-2 truncate min-w-0">
                <Sparkles className="w-3.5 h-3.5 text-[#8D4B00] shrink-0" />
                <span className="text-[#8D4B00] font-semibold shrink-0">Detected share link:</span>
                <span className="font-mono text-[#595E68] text-[11px] truncate">{detectedUrl}</span>
              </div>
              <button
                type="button"
                onClick={() => setUrlInput(detectedUrl)}
                className="ml-2 px-2.5 py-1 rounded-lg text-[11px] font-semibold text-[#8D4B00] bg-[#F3ECE2] hover:bg-[#EDE5DA] transition-colors shrink-0 cursor-pointer"
              >
                Keep link only
              </button>
            </div>
          )}

          <div className="flex items-center justify-between pt-1">
            <button
              type="button"
              onClick={handlePaste}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-[#595E68] bg-[#F3ECE2] hover:bg-[#EDE5DA] border border-[#E5DED4] transition-colors"
            >
              <Clipboard className="w-3.5 h-3.5 text-[#8D4B00]" />
              <span>Paste from clipboard</span>
            </button>

            <button
              type="submit"
              disabled={loading || !urlInput.trim()}
              className="flex items-center space-x-2 px-6 py-2 rounded-xl text-xs font-semibold text-white bg-[#8D4B00] hover:bg-[#743D00] disabled:opacity-50 disabled:cursor-not-allowed shadow-md shadow-[#8D4B00]/20 transition-all cursor-pointer"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Parsing media metadata...</span>
                </>
              ) : (
                <>
                  <Search className="w-4 h-4" />
                  <span>Parse Link</span>
                </>
              )}
            </button>
          </div>
        </form>

        {error && (
          <div className="mt-4 p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start space-x-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-medium">Parsing encountered an issue</p>
              <p className="text-[11px] text-rose-700 mt-0.5">{error}</p>
            </div>
          </div>
        )}
      </div>

      {/* Preview Card */}
      {parsedData && preview && (
        <div className="bg-[#FFFFFF] border-2 border-[#8D4B00]/40 rounded-2xl p-6 shadow-md transition-all animate-fadeIn">
          <div className="flex items-center justify-between pb-4 border-b border-[#E5DED4]">
            <div className="flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
              <span className="text-xs font-bold uppercase tracking-wider text-[#8D4B00]">
                Parsed Successfully • Content Ready
              </span>
            </div>
            {getTypeBadge(parsedData.key_type, parsedData.content_type)}
          </div>

          <div className="mt-5 grid grid-cols-1 md:grid-cols-12 gap-6">
            {/* Cover / Thumbnail Column */}
            <div className="md:col-span-4 flex flex-col items-center">
              <div className="w-full relative aspect-[9/16] max-h-72 rounded-xl overflow-hidden bg-[#F3ECE2] border border-[#E5DED4] shadow-inner group">
                {preview.cover_url ? (
                  <img
                    src={preview.cover_url}
                    alt={preview.title || 'Cover'}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    referrerPolicy="no-referrer"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src =
                        'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 24 24" fill="%238D4B00"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14.5v-9l6 4.5-6 4.5z"/></svg>';
                    }}
                  />
                ) : (
                  <div className="w-full h-full flex flex-col items-center justify-center text-[#898174]">
                    <Film className="w-10 h-10 stroke-[1.5] text-[#8D4B00]" />
                    <span className="text-[11px] mt-2">No cover available</span>
                  </div>
                )}
                {parsedData.content_type === 'video' && (
                  <div className="absolute inset-0 bg-black/20 flex items-center justify-center pointer-events-none">
                    <div className="w-10 h-10 rounded-full bg-white/80 backdrop-blur-sm flex items-center justify-center text-[#8D4B00]">
                      <Video className="w-5 h-5 ml-0.5" />
                    </div>
                  </div>
                )}
                {preview.images && preview.images.length > 0 && (
                  <div className="absolute top-2 right-2 bg-black/60 backdrop-blur-sm text-white px-2 py-0.5 rounded text-[10px] font-medium flex items-center space-x-1">
                    <ImageIcon className="w-3 h-3" />
                    <span>{preview.images.length} images</span>
                  </div>
                )}
              </div>
            </div>

            {/* Metadata & Details Column */}
            <div className="md:col-span-8 flex flex-col justify-between space-y-4">
              <div>
                {/* Author row */}
                {preview.author && (
                  <div className="flex items-center space-x-3 mb-3 p-2.5 rounded-xl bg-[#FAF8F5] border border-[#E5DED4]">
                    {preview.author.avatar_thumb ? (
                      <img
                        src={preview.author.avatar_thumb}
                        alt={preview.author.nickname}
                        className="w-10 h-10 rounded-full object-cover border border-[#8D4B00]/30"
                        referrerPolicy="no-referrer"
                      />
                    ) : (
                      <div className="w-10 h-10 rounded-full bg-[#F3ECE2] flex items-center justify-center text-[#8D4B00]">
                        <User className="w-5 h-5" />
                      </div>
                    )}
                    <div>
                      <h3 className="font-bold text-xs text-[#1F2328]">
                        {preview.author.nickname || 'Douyin Creator'}
                      </h3>
                      <p className="text-[11px] text-[#595E68] font-mono">
                        {preview.author.unique_id
                          ? `Douyin ID: ${preview.author.unique_id}`
                          : `ID: ${preview.author.sec_uid?.slice(0, 14)}...`}
                      </p>
                    </div>
                  </div>
                )}

                {/* Title & Description */}
                <div className="space-y-1">
                  <h4 className="text-xs font-semibold text-[#1F2328] line-clamp-2">
                    {preview.title || preview.desc || '(Untitled)'}
                  </h4>
                  {preview.desc && preview.desc !== preview.title && (
                    <p className="text-[11px] text-[#595E68] line-clamp-3 leading-relaxed">
                      {preview.desc}
                    </p>
                  )}
                </div>

                {/* Engagement Statistics Row */}
                <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <div className="p-2.5 rounded-xl bg-[#FAF8F5] border border-[#E5DED4] flex items-center space-x-2">
                    <Heart className="w-3.5 h-3.5 text-rose-500 fill-rose-500/20" />
                    <div>
                      <p className="text-[10px] text-[#898174]">Likes</p>
                      <p className="text-xs font-bold text-[#1F2328]">
                        {formatNumber(preview.statistics.digg_count)}
                      </p>
                    </div>
                  </div>
                  <div className="p-2.5 rounded-xl bg-[#FAF8F5] border border-[#E5DED4] flex items-center space-x-2">
                    <MessageCircle className="w-3.5 h-3.5 text-blue-500" />
                    <div>
                      <p className="text-[10px] text-[#898174]">Comments</p>
                      <p className="text-xs font-bold text-[#1F2328]">
                        {formatNumber(preview.statistics.comment_count)}
                      </p>
                    </div>
                  </div>
                  <div className="p-2.5 rounded-xl bg-[#FAF8F5] border border-[#E5DED4] flex items-center space-x-2">
                    <Share2 className="w-3.5 h-3.5 text-amber-500" />
                    <div>
                      <p className="text-[10px] text-[#898174]">Shares</p>
                      <p className="text-xs font-bold text-[#1F2328]">
                        {formatNumber(preview.statistics.share_count)}
                      </p>
                    </div>
                  </div>
                  <div className="p-2.5 rounded-xl bg-[#FAF8F5] border border-[#E5DED4] flex items-center space-x-2">
                    <Eye className="w-3.5 h-3.5 text-emerald-500" />
                    <div>
                      <p className="text-[10px] text-[#898174]">Plays / Est.</p>
                      <p className="text-xs font-bold text-[#1F2328]">
                        {preview.work_count && preview.work_count > 1
                          ? `${preview.work_count} works`
                          : formatNumber(preview.statistics.play_count || 1)}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Call to action buttons */}
              <div className="pt-2 flex flex-col sm:flex-row items-center justify-end space-y-2 sm:space-y-0 sm:space-x-3">
                <button
                  type="button"
                  onClick={() => setParsedData(null)}
                  className="w-full sm:w-auto px-4 py-2 rounded-xl text-xs font-medium text-[#595E68] bg-[#FAF8F5] hover:bg-[#F3ECE2] border border-[#E5DED4] transition-colors"
                >
                  Reset
                </button>
                <button
                  type="button"
                  onClick={() => onProceedToConfig(parsedData)}
                  className="w-full sm:w-auto flex items-center justify-center space-x-2 px-6 py-2.5 rounded-xl text-xs font-semibold text-white bg-[#8D4B00] hover:bg-[#743D00] shadow-md shadow-[#8D4B00]/20 transition-all cursor-pointer"
                >
                  <span>Step 2: Configure & Download</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
