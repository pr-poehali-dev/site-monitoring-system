import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import Icon from '@/components/ui/icon';

interface LogsTabProps {
  logs: any[];
  autoRefreshLogs: boolean;
  setAutoRefreshLogs: (value: boolean) => void;
  formatDateTime: (dateStr: string) => string;
}

const LogsTab = ({ logs, autoRefreshLogs, setAutoRefreshLogs, formatDateTime }: LogsTabProps) => {
  return (
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
      <CardContent>
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
  );
};

export default LogsTab;
