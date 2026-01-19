import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import Icon from '@/components/ui/icon';

const API_BASE_URL = 'https://functions.poehali.dev/73bc5c25-0ee1-409f-89c6-2cf97269ec2d';

interface LinkFinderLogsProps {
  sessionId?: string | null;
  autoRefresh?: boolean;
}

export function LinkFinderLogs({ sessionId, autoRefresh = false }: LinkFinderLogsProps) {
  const [logs, setLogs] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [loading, setLoading] = useState(false);

  const limit = 50;

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        endpoint: 'link_finding_logs',
        limit: limit.toString(),
        offset: ((page - 1) * limit).toString(),
        ...(sessionId && { session_id: sessionId }),
        ...(searchQuery && { search: searchQuery }),
        ...(filterStatus && { status: filterStatus })
      });

      const response = await fetch(`${API_BASE_URL}?${params}`);
      const data = await response.json();

      if (data.logs) {
        setLogs(data.logs);
        setTotal(data.total);
      }
    } catch (error) {
      console.error('Ошибка загрузки логов:', error);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchLogs();
  }, [page, searchQuery, filterStatus, sessionId]);

  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      fetchLogs();
    }, 2000);

    return () => clearInterval(interval);
  }, [autoRefresh, page, searchQuery, filterStatus, sessionId]);

  const totalPages = Math.ceil(total / limit);

  const getStatusBadge = (status: string) => {
    const variants: Record<string, { color: string; icon: string }> = {
      success: { color: 'bg-green-100 text-green-800 border-green-200', icon: 'CheckCircle2' },
      info: { color: 'bg-blue-100 text-blue-800 border-blue-200', icon: 'Info' },
      warning: { color: 'bg-orange-100 text-orange-800 border-orange-200', icon: 'AlertTriangle' },
      error: { color: 'bg-red-100 text-red-800 border-red-200', icon: 'XCircle' }
    };

    const variant = variants[status] || variants.info;

    return (
      <Badge className={`${variant.color} border`}>
        <Icon name={variant.icon as any} size={14} className="mr-1" />
        {status}
      </Badge>
    );
  };

  const renderLogDetails = (log: any) => {
    const details = log.details;

    // СИСТЕМНЫЕ ЛОГИ (старт, итерации, завершение)
    if (log.step === 'system_start') {
      return (
        <div className="space-y-2 text-sm">
          <div className="font-semibold text-blue-900">🚀 Запуск поиска связей</div>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div><span className="text-muted-foreground">Всего документов:</span> <span className="font-medium">{details.total_documents}</span></div>
            <div><span className="text-muted-foreground">Уже обработано:</span> <span className="font-medium">{details.already_processed}</span></div>
            <div><span className="text-muted-foreground">Осталось:</span> <span className="font-medium">{details.remaining}</span></div>
          </div>
          {details.auto_loop && (
            <div className="text-xs text-blue-600">🔄 Режим auto-loop активирован</div>
          )}
        </div>
      );
    }

    if (log.step === 'system_iteration') {
      return (
        <div className="space-y-1 text-sm">
          <div className="font-semibold text-blue-900">🔄 Итерация {details.iteration}</div>
          <div className="text-xs text-muted-foreground">Осталось документов: {details.remaining}</div>
        </div>
      );
    }

    if (log.step === 'system_iteration_completed') {
      return (
        <div className="space-y-2 text-sm">
          <div className="font-semibold text-green-900">✅ Итерация {details.iteration} завершена</div>
          <div className="grid grid-cols-4 gap-2 text-xs">
            <div><span className="text-muted-foreground">Обработано:</span> <span className="font-medium">{details.stats.total_processed}/{details.batch_size}</span></div>
            <div><span className="text-muted-foreground">Версий:</span> <span className="font-medium">{details.stats.version_mentions}</span></div>
            <div><span className="text-muted-foreground">Связей:</span> <span className="font-medium">{details.stats.links_created}</span></div>
            <div><span className="text-muted-foreground">Осталось:</span> <span className="font-medium">{details.remaining}</span></div>
          </div>
          <div className="text-xs text-muted-foreground">Время: {details.duration_ms}мс</div>
        </div>
      );
    }

    if (log.step === 'system_completed') {
      return (
        <div className="space-y-1 text-sm">
          <div className="font-semibold text-green-900">🎉 Поиск связей полностью завершён!</div>
          <div className="text-xs text-muted-foreground">
            Обработано: {details.total_documents} документов за {details.total_iterations} итераций
          </div>
        </div>
      );
    }

    // ЛОГИ ПО ФАЙЛАМ (file_processing)
    if (log.step === 'file_processing') {
      return (
        <div className="space-y-3 text-sm bg-gray-50 rounded-lg p-4">
          {/* Заголовок файла */}
          <div className="flex items-center justify-between pb-2 border-b">
            <div className="font-semibold">
              📄 Документ №{details.document_number} от {details.document_date}
            </div>
            <div className="text-xs text-muted-foreground">{details.total_duration_ms}мс</div>
          </div>

          {/* Этапы обработки */}
          <div className="space-y-2">
            {/* Скачивание */}
            {details.stages.download && (
              <div className="flex items-center gap-2 text-xs">
                {details.stages.download.status === 'success' ? (
                  <Icon name="Download" size={14} className="text-green-600" />
                ) : (
                  <Icon name="XCircle" size={14} className="text-red-600" />
                )}
                <span className="font-medium">Скачивание:</span>
                {details.stages.download.status === 'success' ? (
                  <span className="text-muted-foreground">
                    {details.stages.download.size_kb} КБ за {details.stages.download.duration_ms}мс
                  </span>
                ) : (
                  <span className="text-red-600">{details.stages.download.error}</span>
                )}
              </div>
            )}

            {/* Парсинг */}
            {details.stages.parse && (
              <div className="flex items-center gap-2 text-xs">
                {details.stages.parse.status === 'success' ? (
                  <Icon name="FileText" size={14} className="text-green-600" />
                ) : (
                  <Icon name="XCircle" size={14} className="text-red-600" />
                )}
                <span className="font-medium">Парсинг ({details.stages.parse.format}):</span>
                {details.stages.parse.status === 'success' ? (
                  <span className="text-muted-foreground">
                    {details.stages.parse.text_length} символов за {details.stages.parse.duration_ms}мс
                  </span>
                ) : (
                  <span className="text-red-600">{details.stages.parse.error}</span>
                )}
              </div>
            )}

            {/* Упоминания */}
            {details.stages.mentions && (
              <div className="flex items-center gap-2 text-xs">
                <Icon name="Search" size={14} className="text-blue-600" />
                <span className="font-medium">Найдено упоминаний:</span>
                <span className="text-muted-foreground">
                  {details.stages.mentions.total} (Версии: {details.stages.mentions.version_count}, Связанные: {details.stages.mentions.related_count})
                </span>
              </div>
            )}

            {/* Ключевые слова */}
            {details.stages.mentions && (details.stages.mentions.version_keywords.length > 0 || details.stages.mentions.related_keywords.length > 0) && (
              <div className="text-xs space-y-1">
                {details.stages.mentions.version_keywords.length > 0 && (
                  <div className="flex gap-1 flex-wrap">
                    <span className="text-purple-700 font-medium">VERSION:</span>
                    {details.stages.mentions.version_keywords.slice(0, 3).map((kw: string, i: number) => (
                      <Badge key={i} variant="outline" className="text-xs bg-purple-50 text-purple-700">
                        {kw.replace(/\\s\+/g, ' ').slice(0, 20)}
                      </Badge>
                    ))}
                  </div>
                )}
                {details.stages.mentions.related_keywords.length > 0 && (
                  <div className="flex gap-1 flex-wrap">
                    <span className="text-cyan-700 font-medium">RELATED:</span>
                    {details.stages.mentions.related_keywords.slice(0, 3).map((kw: string, i: number) => (
                      <Badge key={i} variant="outline" className="text-xs bg-cyan-50 text-cyan-700">
                        {kw.replace(/\\s\+/g, ' ').slice(0, 20)}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Связи */}
            {details.stages.links && (
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-xs">
                  <Icon name="Link" size={14} className="text-green-600" />
                  <span className="font-medium">Результат:</span>
                  <span className="text-green-600">Создано: {details.stages.links.created}</span>
                  <span className="text-orange-600">Пропущено: {details.stages.links.skipped}</span>
                  {details.stages.links.deleted.length > 0 && (
                    <span className="text-red-600">Удалено: {details.stages.links.deleted.length}</span>
                  )}
                </div>

                {/* Детали действий */}
                {details.stages.links.actions.slice(0, 3).map((action: any, i: number) => (
                  <div key={i} className="text-xs text-muted-foreground pl-6">
                    {action.action === 'created' && (
                      <span>✅ Создана связь {action.link_type} → №{action.target_number} от {action.target_date}</span>
                    )}
                    {action.action === 'skipped' && (
                      <span>⏭ Пропущено: {action.reason === 'already_exists' ? 'уже существует' : action.reason}</span>
                    )}
                    {action.action === 'phantom_created' && (
                      <span>👻 Создан фантом №{action.phantom_number}</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Финальная статистика */}
          <div className="flex items-center justify-between pt-2 border-t text-xs">
            <div className="flex gap-4">
              <span>📎 Версий: {details.stats.version_mentions}</span>
              <span>🔗 Связанных: {details.stats.related_mentions}</span>
              <span>➕ Связей: {details.stats.links_created}</span>
            </div>
            {details.stats.errors > 0 && (
              <span className="text-red-600">❌ Ошибок: {details.stats.errors}</span>
            )}
          </div>
        </div>
      );
    }

    return null;
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Логи обработки</CardTitle>
            <CardDescription>Подробная информация о каждом файле</CardDescription>
          </div>
          {autoRefresh && (
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              <span className="text-sm text-muted-foreground">Автообновление</span>
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Фильтры */}
        <div className="flex gap-3">
          <Input
            placeholder="Поиск по номеру документа..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="flex-1"
          />
          <div className="flex gap-2">
            <Button
              variant={filterStatus === '' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setFilterStatus('')}
            >
              Все
            </Button>
            <Button
              variant={filterStatus === 'success' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setFilterStatus('success')}
            >
              Успешно
            </Button>
            <Button
              variant={filterStatus === 'warning' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setFilterStatus('warning')}
            >
              Предупреждения
            </Button>
            <Button
              variant={filterStatus === 'error' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setFilterStatus('error')}
            >
              Ошибки
            </Button>
          </div>
        </div>

        {/* Логи */}
        <div className="space-y-3">
          {loading && logs.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              Загрузка...
            </div>
          ) : logs.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              Нет логов
            </div>
          ) : (
            logs.map((log) => (
              <div key={log.id} className="border rounded-lg p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {getStatusBadge(log.status)}
                    {log.document_title && (
                      <span className="text-sm font-medium">{log.document_title}</span>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {new Date(log.created_at).toLocaleString('ru-RU')}
                  </div>
                </div>
                {renderLogDetails(log)}
              </div>
            ))
          )}
        </div>

        {/* Пагинация */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between pt-4 border-t">
            <div className="text-sm text-muted-foreground">
              Показано {(page - 1) * limit + 1}-{Math.min(page * limit, total)} из {total}
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 1}
                onClick={() => setPage(page - 1)}
              >
                <Icon name="ChevronLeft" size={16} />
              </Button>
              <span className="flex items-center px-3 text-sm">
                {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page === totalPages}
                onClick={() => setPage(page + 1)}
              >
                <Icon name="ChevronRight" size={16} />
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
