import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import Icon from '@/components/ui/icon';

const PARSER_URL = 'https://functions.poehali.dev/8c4db4b8-687e-471b-add5-e4517d47764c';

interface FileStats {
  total_files: number;
  downloaded: number;
  pending: number;
}

const FileDownloadPanel = () => {
  const [stats, setStats] = useState<FileStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [autoDownload, setAutoDownload] = useState(false);

  const fetchStats = async () => {
    try {
      setLoading(true);
      const response = await fetch(PARSER_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'get_download_stats' })
      });
      const data = await response.json();
      setStats(data);
    } catch (error) {
      console.error('Ошибка получения статистики:', error);
    } finally {
      setLoading(false);
    }
  };

  const startDownload = async (enableAutoLoop: boolean = false) => {
    try {
      setDownloading(true);
      
      // Запускаем загрузку с auto_loop флагом (фоновая обработка на бэкенде)
      fetch(PARSER_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          action: 'download_files', 
          limit: 50,
          auto_loop: enableAutoLoop 
        })
      }).catch(() => {});
      
      // Даём время на старт
      setTimeout(() => {
        setDownloading(false);
        fetchStats();
      }, 1000);
      
    } catch (error) {
      console.error('Ошибка загрузки файлов:', error);
      setDownloading(false);
      setAutoDownload(false);
    }
  };

  const toggleAutoDownload = () => {
    if (!autoDownload) {
      setAutoDownload(true);
      startDownload(true); // Включаем auto_loop на бэкенде
    } else {
      setAutoDownload(false);
      setDownloading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 10000); // Обновляем каждые 10 сек
    return () => clearInterval(interval);
  }, []);

  const progress = stats ? (stats.downloaded / stats.total_files) * 100 : 0;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Загрузка файлов в S3</CardTitle>
            <CardDescription>Скачивание документов с сайта и загрузка в облачное хранилище</CardDescription>
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
        {stats && (
          <>
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600">Прогресс</span>
                <span className="font-semibold">{stats.downloaded} / {stats.total_files}</span>
              </div>
              <Progress value={progress} className="h-3" />
              <div className="flex gap-3 text-xs text-gray-500">
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-green-500"></div>
                  <span>Загружено: {stats.downloaded}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-yellow-500"></div>
                  <span>Ожидает: {stats.pending}</span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="p-4 border rounded-lg text-center">
                <div className="text-2xl font-bold text-gray-900">{stats.total_files}</div>
                <div className="text-xs text-gray-500 mt-1">Всего файлов</div>
              </div>
              <div className="p-4 border rounded-lg text-center bg-green-50 border-green-200">
                <div className="text-2xl font-bold text-green-600">{stats.downloaded}</div>
                <div className="text-xs text-green-700 mt-1">Загружено</div>
              </div>
              <div className="p-4 border rounded-lg text-center bg-yellow-50 border-yellow-200">
                <div className="text-2xl font-bold text-yellow-600">{stats.pending}</div>
                <div className="text-xs text-yellow-700 mt-1">Осталось</div>
              </div>
            </div>

            {stats.pending > 0 && (
              <div className="space-y-3 pt-4 border-t">
                <div className="flex gap-3">
                  <Button 
                    className="flex-1"
                    onClick={startDownload}
                    disabled={downloading}
                  >
                    <Icon name="Download" size={16} className="mr-2" />
                    {downloading ? 'Загрузка...' : 'Загрузить 50 файлов'}
                  </Button>
                  <Button 
                    variant={autoDownload ? "destructive" : "outline"}
                    onClick={toggleAutoDownload}
                    disabled={downloading && !autoDownload}
                  >
                    <Icon name={autoDownload ? "Square" : "PlayCircle"} size={16} className="mr-2" />
                    {autoDownload ? 'Остановить' : 'Авто'}
                  </Button>
                </div>
                
                <div className="p-3 border rounded-lg bg-blue-50 border-blue-200">
                  <div className="flex items-start gap-3">
                    <Icon name="Info" size={18} className="text-blue-600 mt-0.5" />
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-blue-900">Автономный режим</p>
                      <p className="text-xs text-blue-700">
                        Загрузка работает в фоне на сервере. Можно закрыть страницу — процесс продолжится автоматически до завершения.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {stats.pending === 0 && (
              <div className="flex items-center gap-2 p-4 bg-green-50 border border-green-200 rounded-lg">
                <Icon name="CheckCircle" size={18} className="text-green-600" />
                <div>
                  <p className="text-sm font-medium text-green-900">Все файлы загружены!</p>
                  <p className="text-xs text-green-700">Документы доступны в CDN</p>
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default FileDownloadPanel;