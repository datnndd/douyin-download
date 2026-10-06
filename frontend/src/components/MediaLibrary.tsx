// frontend/src/components/MediaLibrary.tsx

import React, { useEffect, useState } from 'react';
import {
  Download,
  FileCode,
  FileText,
  Film,
  FolderOpen,
  Image as ImageIcon,
  LayoutGrid,
  List,
  Loader2,
  Music,
  Play,
  RefreshCw,
  Search,
  Volume2,
  X,
} from 'lucide-react';
import { MediaItem } from '../types/api';
import { api } from '../services/api';

interface MediaLibraryProps {
  onOpenFolder: () => void;
}

export const MediaLibrary: React.FC<MediaLibraryProps> = ({ onOpenFolder }) => {
  const [mediaList, setMediaList] = useState<MediaItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  // Player modal state
  const [activePlaybackItem, setActivePlaybackItem] = useState<MediaItem | null>(null);

  const fetchMedia = async () => {
    setLoading(true);
    try {
      const res = await api.getMedia();
      setMediaList(res.items || []);
    } catch (err) {
      console.error('Failed to load media items:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMedia();
  }, []);

  const formatBytes = (bytes: number): string => {
    if (bytes <= 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (isoStr: string): string => {
    try {
      const date = new Date(isoStr);
      return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return isoStr;
    }
  };

  const filteredItems = mediaList.filter((item) => {
    const matchesSearch = item.filename.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesType = typeFilter === 'all' || item.media_type === typeFilter;
    return matchesSearch && matchesType;
  });

  const getMediaIcon = (type: string) => {
    switch (type) {
      case 'video':
        return <Film className="w-5 h-5 text-[#8D4B00]" />;
      case 'audio':
        return <Music className="w-5 h-5 text-amber-600" />;
      case 'image':
        return <ImageIcon className="w-5 h-5 text-blue-600" />;
      case 'json':
        return <FileCode className="w-5 h-5 text-emerald-600" />;
      default:
        return <FileText className="w-5 h-5 text-stone-600" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Controls Bar */}
      <div className="bg-[#FFFFFF] border border-[#E5DED4] rounded-2xl p-5 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-[#1F2328] flex items-center space-x-2">
              <Film className="w-4 h-4 text-[#8D4B00]" />
              <span>下载媒体库 ({mediaList.length} 个文件)</span>
            </h2>
            <p className="text-xs text-[#595E68] mt-0.5">
              浏览本地已归档的视频、音乐、封面图及元数据文档，支持直接在线播放与调用系统文件管理器
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={fetchMedia}
              disabled={loading}
              className="p-2 rounded-xl text-[#595E68] hover:text-[#1F2328] bg-[#FAF8F5] hover:bg-[#F3ECE2] border border-[#E5DED4] transition-colors"
              title="刷新媒体列表"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>

            <button
              onClick={onOpenFolder}
              className="flex items-center space-x-1.5 px-3 py-2 rounded-xl text-xs font-semibold text-[#8D4B00] bg-[#F3ECE2] hover:bg-[#EDE5DA] border border-[#E5DED4] transition-colors cursor-pointer"
              title="在系统文件管理器中打开"
            >
              <FolderOpen className="w-4 h-4" />
              <span>打开下载目录</span>
            </button>
          </div>
        </div>

        {/* Search & Filters */}
        <div className="flex flex-col md:flex-row items-center justify-between gap-3 pt-2 border-t border-[#E5DED4]">
          {/* Search box */}
          <div className="relative w-full md:w-80">
            <Search className="w-4 h-4 text-[#898174] absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="搜索已下载文件名..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 rounded-xl border border-[#E5DED4] bg-[#FAF8F5] text-xs text-[#1F2328] focus:outline-none focus:border-[#8D4B00]"
            />
          </div>

          {/* Type Filters & View Mode */}
          <div className="flex items-center justify-between w-full md:w-auto space-x-3">
            <div className="flex items-center bg-[#FAF8F5] p-1 rounded-xl border border-[#E5DED4]">
              {['all', 'video', 'audio', 'image', 'json'].map((t) => (
                <button
                  key={t}
                  onClick={() => setTypeFilter(t)}
                  className={`px-3 py-1 rounded-lg text-xs font-medium capitalize transition-all cursor-pointer ${
                    typeFilter === t
                      ? 'bg-[#8D4B00] text-white font-semibold shadow-xs'
                      : 'text-[#595E68] hover:text-[#1F2328]'
                  }`}
                >
                  {t === 'all'
                    ? '全部'
                    : t === 'video'
                    ? '视频'
                    : t === 'audio'
                    ? '音乐'
                    : t === 'image'
                    ? '封面/图集'
                    : 'JSON'}
                </button>
              ))}
            </div>

            <div className="flex items-center bg-[#FAF8F5] p-1 rounded-xl border border-[#E5DED4]">
              <button
                onClick={() => setViewMode('grid')}
                className={`p-1.5 rounded-lg text-xs transition-all ${
                  viewMode === 'grid'
                    ? 'bg-white text-[#8D4B00] shadow-xs'
                    : 'text-[#898174] hover:text-[#1F2328]'
                }`}
                title="网格视图"
              >
                <LayoutGrid className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`p-1.5 rounded-lg text-xs transition-all ${
                  viewMode === 'list'
                    ? 'bg-white text-[#8D4B00] shadow-xs'
                    : 'text-[#898174] hover:text-[#1F2328]'
                }`}
                title="列表视图"
              >
                <List className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Media Items Display */}
      {loading && mediaList.length === 0 ? (
        <div className="py-20 flex flex-col items-center justify-center space-y-3">
          <Loader2 className="w-8 h-8 text-[#8D4B00] animate-spin" />
          <p className="text-xs text-[#595E68]">正在扫描本地媒体库...</p>
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="bg-white border border-[#E5DED4] rounded-2xl p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-[#F3ECE2] text-[#8D4B00] flex items-center justify-center mx-auto">
            <Film className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-[#1F2328]">未找到媒体文件</h3>
          <p className="text-xs text-[#595E68] max-w-sm mx-auto">
            下载目录中尚无符合条件的内容。请返回“下载器”页面输入抖音作品链接开始下载。
          </p>
        </div>
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {filteredItems.map((item) => {
            const isPlayable = item.media_type === 'video' || item.media_type === 'audio';

            return (
              <div
                key={item.id}
                className="bg-white border border-[#E5DED4] rounded-2xl overflow-hidden shadow-sm hover:shadow-md hover:border-[#8D4B00]/40 transition-all flex flex-col justify-between group"
              >
                {/* Media Preview Box */}
                <div className="relative aspect-video bg-[#FAF8F5] border-b border-[#E5DED4] flex items-center justify-center overflow-hidden">
                  {item.media_type === 'video' ? (
                    <>
                      <video
                        src={item.preview_url}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        preload="metadata"
                      />
                      <button
                        onClick={() => setActivePlaybackItem(item)}
                        className="absolute inset-0 bg-black/30 group-hover:bg-black/40 flex items-center justify-center transition-all cursor-pointer"
                        title="在线全屏播放"
                      >
                        <div className="w-11 h-11 rounded-full bg-white/90 group-hover:bg-white text-[#8D4B00] flex items-center justify-center shadow-lg transform group-hover:scale-110 transition-transform">
                          <Play className="w-5 h-5 ml-0.5 fill-[#8D4B00]" />
                        </div>
                      </button>
                    </>
                  ) : item.media_type === 'image' ? (
                    <img
                      src={item.preview_url}
                      alt={item.filename}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      loading="lazy"
                    />
                  ) : item.media_type === 'audio' ? (
                    <button
                      onClick={() => setActivePlaybackItem(item)}
                      className="w-full h-full flex flex-col items-center justify-center space-y-2 bg-[#FAF6F0] hover:bg-[#F3ECE2] transition-colors cursor-pointer"
                    >
                      <div className="w-10 h-10 rounded-full bg-[#8D4B00]/10 flex items-center justify-center text-[#8D4B00]">
                        <Volume2 className="w-5 h-5" />
                      </div>
                      <span className="text-[11px] font-semibold text-[#8D4B00]">点击试听音频</span>
                    </button>
                  ) : (
                    <div className="flex flex-col items-center justify-center text-[#898174] space-y-1">
                      {getMediaIcon(item.media_type)}
                      <span className="text-[11px] font-mono">JSON</span>
                    </div>
                  )}

                  <div className="absolute top-2 right-2 px-2 py-0.5 rounded bg-black/60 backdrop-blur-sm text-white font-mono text-[10px] font-semibold uppercase">
                    {item.media_type}
                  </div>
                </div>

                {/* Details */}
                <div className="p-4 space-y-2 flex-1 flex flex-col justify-between">
                  <div>
                    <h4
                      className="text-xs font-semibold text-[#1F2328] line-clamp-2 leading-snug"
                      title={item.filename}
                    >
                      {item.filename}
                    </h4>
                    <p className="text-[10px] text-[#898174] font-mono mt-1">
                      {item.relative_path}
                    </p>
                  </div>

                  <div className="pt-2 border-t border-[#E5DED4]/60 flex items-center justify-between text-[11px] text-[#595E68]">
                    <span className="font-mono">{formatBytes(item.file_size)}</span>
                    <span className="text-[10px]">{formatDate(item.created_at)}</span>
                  </div>
                </div>

                {/* Bottom Action Footer */}
                <div className="px-4 py-2.5 bg-[#FAF8F5] border-t border-[#E5DED4] flex items-center justify-between">
                  {isPlayable ? (
                    <button
                      onClick={() => setActivePlaybackItem(item)}
                      className="flex items-center space-x-1 text-xs font-semibold text-[#8D4B00] hover:underline cursor-pointer"
                    >
                      <Play className="w-3.5 h-3.5 fill-[#8D4B00]" />
                      <span>播放</span>
                    </button>
                  ) : (
                    <div />
                  )}

                  <a
                    href={item.download_url}
                    download={item.filename}
                    className="p-1.5 rounded-lg text-[#595E68] hover:text-[#1F2328] hover:bg-[#F3ECE2] border border-[#E5DED4] transition-colors"
                    title="下载到本地电脑"
                  >
                    <Download className="w-3.5 h-3.5 text-[#8D4B00]" />
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* List View */
        <div className="bg-white border border-[#E5DED4] rounded-2xl overflow-hidden shadow-sm divide-y divide-[#E5DED4]">
          {filteredItems.map((item) => (
            <div
              key={item.id}
              className="p-4 hover:bg-[#FAF8F5] flex items-center justify-between space-x-4 transition-colors"
            >
              <div className="flex items-center space-x-3 overflow-hidden flex-1">
                <div className="w-9 h-9 rounded-xl bg-[#F3ECE2] flex items-center justify-center shrink-0">
                  {getMediaIcon(item.media_type)}
                </div>
                <div className="overflow-hidden">
                  <h4 className="text-xs font-semibold text-[#1F2328] truncate">
                    {item.filename}
                  </h4>
                  <p className="text-[10px] text-[#898174] font-mono mt-0.5 truncate">
                    {item.relative_path}
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-6 text-xs text-[#595E68] shrink-0">
                <span className="font-mono text-[11px]">{formatBytes(item.file_size)}</span>
                <span className="text-[11px] hidden md:inline">{formatDate(item.created_at)}</span>

                <div className="flex items-center space-x-2">
                  {(item.media_type === 'video' || item.media_type === 'audio') && (
                    <button
                      onClick={() => setActivePlaybackItem(item)}
                      className="px-2.5 py-1 rounded-lg text-xs font-medium bg-[#F3ECE2] hover:bg-[#EDE5DA] text-[#8D4B00] border border-[#E5DED4] flex items-center space-x-1 transition-colors cursor-pointer"
                    >
                      <Play className="w-3 h-3 fill-[#8D4B00]" />
                      <span>播放</span>
                    </button>
                  )}

                  <a
                    href={item.download_url}
                    download={item.filename}
                    className="p-1.5 rounded-lg text-[#595E68] hover:text-[#1F2328] hover:bg-[#F3ECE2] border border-[#E5DED4] transition-colors"
                    title="下载到本地"
                  >
                    <Download className="w-3.5 h-3.5 text-[#8D4B00]" />
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* HTML5 In-Browser Audio / Video Player Modal */}
      {activePlaybackItem && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-[#FAF8F5] border border-[#E5DED4] rounded-2xl w-full max-w-3xl overflow-hidden shadow-2xl flex flex-col">
            {/* Player Header */}
            <div className="px-5 py-3.5 bg-white border-b border-[#E5DED4] flex items-center justify-between">
              <div className="flex items-center space-x-2 overflow-hidden">
                <div className="w-7 h-7 rounded-lg bg-[#F3ECE2] flex items-center justify-center text-[#8D4B00]">
                  {getMediaIcon(activePlaybackItem.media_type)}
                </div>
                <h3 className="text-xs font-bold text-[#1F2328] truncate max-w-lg">
                  {activePlaybackItem.filename}
                </h3>
              </div>

              <button
                onClick={() => setActivePlaybackItem(null)}
                className="p-1.5 rounded-lg text-[#898174] hover:text-[#1F2328] hover:bg-[#F3ECE2] transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Player Body */}
            <div className="bg-black flex items-center justify-center min-h-[360px] max-h-[70vh]">
              {activePlaybackItem.media_type === 'video' ? (
                <video
                  src={activePlaybackItem.preview_url}
                  controls
                  autoPlay
                  className="w-full max-h-[68vh] object-contain"
                />
              ) : activePlaybackItem.media_type === 'audio' ? (
                <div className="p-12 w-full flex flex-col items-center justify-center space-y-6 bg-[#FAF6F0]">
                  <div className="w-20 h-20 rounded-full bg-[#8D4B00]/10 flex items-center justify-center text-[#8D4B00] animate-pulse">
                    <Music className="w-10 h-10" />
                  </div>
                  <audio
                    src={activePlaybackItem.preview_url}
                    controls
                    autoPlay
                    className="w-full max-w-md accent-[#8D4B00]"
                  />
                </div>
              ) : null}
            </div>

            {/* Player Footer */}
            <div className="px-5 py-3 bg-[#FAF8F5] border-t border-[#E5DED4] flex items-center justify-between text-xs text-[#595E68]">
              <span className="font-mono text-[11px]">
                大小: {formatBytes(activePlaybackItem.file_size)}
              </span>
              <a
                href={activePlaybackItem.download_url}
                download={activePlaybackItem.filename}
                className="flex items-center space-x-1 font-semibold text-[#8D4B00] hover:underline"
              >
                <Download className="w-3.5 h-3.5" />
                <span>保存文件</span>
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
