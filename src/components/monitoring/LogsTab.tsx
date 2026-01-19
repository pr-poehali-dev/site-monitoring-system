import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import Icon from '@/components/ui/icon';
import LinkFindingLogs from './LinkFindingLogs';

const PARSER_URL = 'https://functions.poehali.dev/8c4db4b8-687e-471b-add5-e4517d47764c';

interface FileStats {
  total_files: number;
  downloaded: number;
  pending: number;
}

interface LogsTabProps {
  logs: any[];
  autoRefreshLogs: boolean;
  setAutoRefreshLogs: (value: boolean) => void;
  formatDateTime: (dateStr: string) => string;
}

const LogsTab = ({ logs, autoRefreshLogs, setAutoRefreshLogs, formatDateTime }: LogsTabProps) => {
  const [fileStats, setFileStats] = useState<FileStats | null>(null);

  const fetchFileStats = async () => {
    try {
      const response = await fetch(PARSER_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'get_download_stats' })
      });
      const data = await response.json();
      setFileStats(data);
    } catch (error) {
      console.error('Ошибка получения статистики файлов:', error);
    }
  };

  useEffect(() => {
    fetchFileStats();
    const interval = setInterval(fetchFileStats, 5000);
    return () => clearInterval(interval);
  }, []);

  const progress = fileStats ? (fileStats.downloaded / fileStats.total_files) * 100 : 0;

  return (
    <div className="space-y-6">
      <LinkFindingLogs />
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Логи парсинга</CardTitle>
            <CardDescription>Подробная информация о работе системы</CardDescription>
          </div>
          <div className="flex items-center gap-3">
            <Label htmlFor="auto-refresh" className="text-sm cursor-pointer">
              <div className="flex items-center gap-2">
                {autoRefreshLogs && <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />}
                Автообновление
              </div>
            </Label>
            <Switch 
              id="auto-refresh" 
              checked={autoRefreshLogs} 
              onCheckedChange={setAutoRefreshLogs}
            />
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Панель прогресса загрузки файлов */}
        {fileStats && fileStats.pending > 0 && (
          <div className="p-4 border-2 border-blue-200 rounded-lg bg-blue-50">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Icon name="Download" size={18} className="text-blue-600" />
                <span className="text-sm font-semibold text-blue-900">Загрузка файлов в S3</span>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="bg-blue-100 text-blue-800">
                  {fileStats.downloaded} / {fileStats.total_files}
                </Badge>
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
              </div>
            </div>
            <Progress value={progress} className="h-2 mb-2" />
            <div className="flex justify-between text-xs text-blue-700">
              <span>Загружено: {fileStats.downloaded}</span>
              <span>Осталось: {fileStats.pending}</span>
              <span>{progress.toFixed(1)}%</span>
            </div>
          </div>
        )}

        {fileStats && fileStats.pending === 0 && fileStats.total_files > 0 && (
          <div className="flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg">
            <Icon name="CheckCircle" size={18} className="text-green-600" />
            <span className="text-sm font-medium text-green-900">
              ✅ Все {fileStats.total_files} файлов загружены в S3
            </span>
          </div>
        )}

        <div className="space-y-3">
          {logs.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              Нет записей в логах
            </div>
          ) : (
            logs.map((log) => (
              <div key={log.id} className="flex gap-3 p-3 border rounded-lg font-mono text-sm">
                <div className="flex-shrink-0">
                  {log.status === 'success' && (
                    <Icon name="CheckCircle2" size={18} className="text-green-600" />
                  )}
                  {log.status === 'info' && (
                    <Icon name="Info" size={18} className="text-blue-600" />
                  )}
                  {log.status === 'error' && (
                    <Icon name="XCircle" size={18} className="text-red-600" />
                  )}
                  {log.status === 'warning' && (
                    <Icon name="AlertTriangle" size={18} className="text-orange-600" />
                  )}
                </div>
                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-3 text-gray-500 text-xs">
                    <span>{formatDateTime(log.started_at)}</span>
                    <span>•</span>
                    <span>{log.duration_ms ? `${log.duration_ms}ms` : '-'}</span>
                  </div>
                  <div className="text-gray-900 whitespace-pre-wrap">{log.message}</div>
                </div>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
    </div>
  );
};

export default LogsTab;