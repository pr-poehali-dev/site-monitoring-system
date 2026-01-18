import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import Icon from '@/components/ui/icon';
import { apiClient, PARSER_BASE_URL } from '@/config/api';

interface FileStats {
  total_files: number;
  downloaded: number;
  pending: number;
  failed: number;
  status_counts: Record<string, number>;
}

const MissingFilesPanel = () => {
  const [stats, setStats] = useState<FileStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [retrying, setRetrying] = useState(false);

  const fetchStats = async () => {
    try {
      setLoading(true);
      const data = await apiClient.getFileDownloadStats();
      setStats(data);
    } catch (error) {
      console.error('Ошибка получения статистики файлов:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRetryDownloads = async () => {
    const confirmed = window.confirm(
      'Запустить повторную загрузку незагруженных файлов?\n\n' +
      'Файлы будут загружены через систему парсера в фоновом режиме.'
    );

    if (!confirmed) return;

    try {
      setRetrying(true);
      
      // Помечаем файлы для повторной загрузки
      const result = await apiClient.retryFailedDownloads();
      
      // Запускаем загрузку через парсер
      fetch(PARSER_BASE_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'download_files',
          limit: 50,
          auto_loop: true
        })
      }).catch(() => {});

      alert(`✅ ${result.message}\n\nЗагрузка запущена в фоновом режиме.`);
      
      setTimeout(() => {
        fetchStats();
      }, 2000);
    } catch (error) {
      alert('Ошибка запуска повторной загрузки');
    } finally {
      setRetrying(false);
    }
  };

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 15000);
    return () => clearInterval(interval);
  }, []);

  if (!stats) return null;
  
  if (stats.pending === 0 && stats.failed === 0) return null;

  const progress = (stats.downloaded / stats.total_files) * 100;
  const needsAction = stats.pending > 0 || stats.failed > 0;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Незагруженные файлы</CardTitle>
            <CardDescription>
              {stats.pending} файлов ожидают загрузки в CDN
            </CardDescription>
          </div>
          <Button 
            variant="outline" 
            size="sm"
            onClick={fetchStats}
            disabled={loading}
          >
            <Icon name="RefreshCw" size={14} className={loading ? 'animate-spin' : ''} />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {needsAction && (
          <div className="p-4 border-2 border-orange-200 rounded-lg bg-orange-50">
            <div className="flex items-start gap-3">
              <Icon name="AlertCircle" size={18} className="text-orange-600 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm font-medium text-orange-900">
                  Обнаружены документы без файлов
                </p>
                <p className="text-xs text-orange-700 mt-1">
                  {stats.pending} файлов не загружены в CDN. Это могут быть старые документы или ошибки загрузки.
                </p>
              </div>
            </div>
          </div>
        )}

        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-600">Прогресс загрузки</span>
            <span className="font-semibold">{stats.downloaded} / {stats.total_files}</span>
          </div>
          <Progress value={progress} className="h-3" />
          <div className="flex gap-4 text-xs">
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-green-500"></div>
              <span className="text-gray-600">Загружено: <strong className="text-gray-900">{stats.downloaded}</strong></span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-yellow-500"></div>
              <span className="text-gray-600">Ожидает: <strong className="text-gray-900">{stats.pending}</strong></span>
            </div>
            {stats.failed > 0 && (
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full bg-red-500"></div>
                <span className="text-gray-600">Ошибки: <strong className="text-gray-900">{stats.failed}</strong></span>
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div className="p-4 border rounded-lg text-center bg-green-50 border-green-200">
            <div className="text-2xl font-bold text-green-600">{stats.downloaded}</div>
            <div className="text-xs text-green-700 mt-1">Загружено</div>
          </div>
          <div className="p-4 border rounded-lg text-center bg-yellow-50 border-yellow-200">
            <div className="text-2xl font-bold text-yellow-600">{stats.pending}</div>
            <div className="text-xs text-yellow-700 mt-1">Ожидает</div>
          </div>
          <div className="p-4 border rounded-lg text-center bg-red-50 border-red-200">
            <div className="text-2xl font-bold text-red-600">{stats.failed}</div>
            <div className="text-xs text-red-700 mt-1">Ошибки</div>
          </div>
        </div>

        {needsAction && (
          <div className="pt-4 border-t">
            <Button 
              className="w-full"
              onClick={handleRetryDownloads}
              disabled={retrying}
            >
              <Icon name="Download" size={16} className="mr-2" />
              {retrying ? 'Запуск...' : 'Догрузить файлы'}
            </Button>
            <p className="text-xs text-gray-500 text-center mt-2">
              Запустит автоматическую загрузку всех незагруженных файлов в CDN
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default MissingFilesPanel;