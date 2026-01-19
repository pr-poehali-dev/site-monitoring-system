import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { API_BASE_URL } from '@/config/api';
import Icon from '@/components/ui/icon';

interface LinkFinderLogsProps {
  sessionId: string | null;
  autoRefresh: boolean;
  onLogUpdate?: (log: any) => void;
}

export function LinkFinderLogs({ sessionId, autoRefresh, onLogUpdate }: LinkFinderLogsProps) {
  const [logs, setLogs] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const limit = 50;

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        endpoint: 'link_finding_logs',
        limit: limit.toString(),
        offset: (page * limit).toString(),
        ...(sessionId && { session_id: sessionId }),
        ...(search && { search }),
        ...(statusFilter && { status: statusFilter })
      });

      const response = await fetch(`${API_BASE_URL}?${params}`);
      const data = await response.json();

      setLogs(data.logs || []);
      setTotal(data.total || 0);

      if (data.logs && data.logs.length > 0 && onLogUpdate) {
        onLogUpdate(data.logs[0]);
      }
    } catch (error) {
      console.error('Ошибка загрузки логов:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [sessionId, page, search, statusFilter]);

  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      fetchLogs();
    }, 2000);

    return () => clearInterval(interval);
  }, [autoRefresh, sessionId, page, search, statusFilter]);

  const getStepIcon = (step: string) => {
    const icons: Record<string, string> = {
      'session_start': 'Play',
      'file_download': 'Download',
      'file_parse': 'FileText',
      'pattern_search': 'Search',
      'link_create': 'Link',
      'link_skip': 'SkipForward',
      'link_delete': 'Trash2',
      'phantom_create': 'Ghost',
      'document_completed': 'CheckCircle',
      'session_completed': 'Trophy',
      'error': 'AlertCircle'
    };
    return icons[step] || 'Circle';
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      'success': 'text-green-600 bg-green-50',
      'info': 'text-blue-600 bg-blue-50',
      'warning': 'text-yellow-600 bg-yellow-50',
      'error': 'text-red-600 bg-red-50'
    };
    return colors[status] || 'text-gray-600 bg-gray-50';
  };

  const formatDetails = (step: string, details: any) => {
    if (!details) return null;

    if (step === 'file_download') {
      return (
        <div className="text-xs space-y-1">
          <p>Размер: {details.size_kb} КБ</p>
          <p>Время: {details.duration_ms}мс</p>
          {details.error && <p className="text-red-600">Ошибка: {details.error}</p>}
        </div>
      );
    }

    if (step === 'file_parse') {
      return (
        <div className="text-xs space-y-1">
          <p>Формат: {details.format}</p>
          <p>Параграфов: {details.paragraphs}</p>
          <p>Символов: {details.text_length}</p>
          <p>Время: {details.duration_ms}мс</p>
        </div>
      );
    }

    if (step === 'pattern_search') {
      return (
        <div className="text-xs space-y-2">
          {details.version_keywords_found && details.version_keywords_found.length > 0 && (
            <div>
              <p className="font-semibold text-purple-700">VERSION паттерны:</p>
              <p className="text-purple-600">{details.version_keywords_found.join(', ')}</p>
            </div>
          )}
          {details.related_keywords_found && details.related_keywords_found.length > 0 && (
            <div>
              <p className="font-semibold text-blue-700">RELATED паттерны:</p>
              <p className="text-blue-600">{details.related_keywords_found.join(', ')}</p>
            </div>
          )}
          {details.mentions && details.mentions.length > 0 && (
            <div>
              <p className="font-semibold">Упоминания ({details.mentions.length}):</p>
              {details.mentions.slice(0, 5).map((m: any, i: number) => (
                <div key={i} className="pl-2 border-l-2 border-gray-300 mt-1">
                  <p>№{m.number} от {m.date}</p>
                  <p className="text-gray-600 italic">Тип: {m.type}</p>
                  <p className="text-gray-500 text-xs">{m.context?.slice(0, 100)}...</p>
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }

    if (step === 'link_create') {
      return (
        <div className="text-xs space-y-1">
          <p className="font-semibold text-green-700">Создана связь {details.link_type}</p>
          <p>№{details.target_number} от {details.target_date}</p>
          <p className="text-gray-600">Паттерн: {details.pattern}</p>
          <p className="text-gray-600">Ключевые слова: {details.keywords?.join(', ')}</p>
          <p className="text-gray-500 italic text-xs">{details.context?.slice(0, 150)}...</p>
        </div>
      );
    }

    if (step === 'link_skip') {
      return (
        <div className="text-xs space-y-1">
          <p>№{details.target_number} от {details.target_date}</p>
          <p className="text-yellow-700">Причина: {details.reason}</p>
          {details.existing_link_id && (
            <p className="text-gray-600">Связь уже существует (ID: {details.existing_link_id})</p>
          )}
          {details.exclusion_phrase && (
            <p className="text-gray-600">Внешний документ: {details.exclusion_phrase}</p>
          )}
        </div>
      );
    }

    if (step === 'link_delete') {
      return (
        <div className="text-xs space-y-1">
          <p className="font-semibold text-red-700">Удалена связь {details.link_type}</p>
          <p>№{details.target_number} от {details.target_date}</p>
          <p className="text-gray-600">Причина: {details.reason}</p>
          <p className="text-gray-500">Оригинал создан: {details.original_created_at}</p>
        </div>
      );
    }

    if (step === 'phantom_create') {
      return (
        <div className="text-xs space-y-1">
          <p className="font-semibold text-purple-700">Фантом создан</p>
          <p>№{details.phantom_number} от {details.phantom_date}</p>
          <p className="text-gray-600">ID: {details.phantom_id}</p>
        </div>
      );
    }

    if (step === 'document_completed') {
      const s = details.stats || {};
      return (
        <div className="text-xs space-y-1 font-semibold">
          <p className="text-green-700">✅ Время: {details.total_duration_ms}мс</p>
          <p>Связей создано: {s.links_created || 0}</p>
          <p>Связей пропущено: {s.links_skipped || 0}</p>
          <p>Связей удалено: {s.links_deleted || 0}</p>
          <p>Фантомов создано: {s.phantoms_created || 0}</p>
          {s.errors > 0 && <p className="text-red-600">Ошибок: {s.errors}</p>}
        </div>
      );
    }

    return (
      <pre className="text-xs bg-gray-100 p-2 rounded overflow-auto max-h-40">
        {JSON.stringify(details, null, 2)}
      </pre>
    );
  };

  const totalPages = Math.ceil(total / limit);

  return (
    <Card className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <Icon name="FileText" size={24} />
          Детальные логи обработки
        </h2>
        <div className="flex items-center gap-2">
          {autoRefresh && (
            <div className="flex items-center gap-2 text-sm text-green-600">
              <Icon name="RefreshCw" size={16} className="animate-spin" />
              Авто-обновление
            </div>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={fetchLogs}
            disabled={loading}
          >
            <Icon name="RefreshCw" size={16} />
            Обновить
          </Button>
        </div>
      </div>

      {/* Фильтры */}
      <div className="flex gap-2">
        <Input
          placeholder="Поиск по номеру документа..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm"
        />
        <Button
          variant={statusFilter === '' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setStatusFilter('')}
        >
          Все ({total})
        </Button>
        <Button
          variant={statusFilter === 'success' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setStatusFilter('success')}
        >
          Успешные
        </Button>
        <Button
          variant={statusFilter === 'warning' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setStatusFilter('warning')}
        >
          Предупреждения
        </Button>
        <Button
          variant={statusFilter === 'error' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setStatusFilter('error')}
        >
          Ошибки
        </Button>
      </div>

      {/* Логи */}
      <div className="space-y-3 max-h-[600px] overflow-y-auto">
        {logs.length === 0 && (
          <div className="text-center py-8 text-muted-foreground">
            {loading ? 'Загрузка логов...' : 'Логов пока нет'}
          </div>
        )}

        {logs.map((log) => (
          <div
            key={log.id}
            className={`p-4 rounded-lg border ${getStatusColor(log.status)}`}
          >
            <div className="flex items-start gap-3">
              <Icon name={getStepIcon(log.step)} size={20} className="mt-0.5" />
              <div className="flex-1 space-y-2">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-semibold">
                      {log.document_number ? `№${log.document_number}` : 'Система'}
                      {log.document_date && ` от ${log.document_date}`}
                    </p>
                    <p className="text-xs text-gray-600">
                      {log.step} • {new Date(log.created_at).toLocaleString('ru-RU')}
                    </p>
                  </div>
                  <span className={`px-2 py-1 rounded text-xs font-semibold ${getStatusColor(log.status)}`}>
                    {log.status}
                  </span>
                </div>

                {log.document_title && (
                  <p className="text-sm text-gray-700">{log.document_title}</p>
                )}

                {log.details && formatDetails(log.step, log.details)}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Пагинация */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-4 border-t">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0 || loading}
          >
            <Icon name="ChevronLeft" size={16} />
            Назад
          </Button>
          <span className="text-sm text-muted-foreground">
            Страница {page + 1} из {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1 || loading}
          >
            Вперёд
            <Icon name="ChevronRight" size={16} />
          </Button>
        </div>
      )}
    </Card>
  );
}
