import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { useToast } from '@/hooks/use-toast';
import { apiClient } from '@/config/api';
import Icon from '@/components/ui/icon';
import { LinkFinderLogs } from '@/components/LinkFinderLogs';

export default function LinkFinder() {
  const navigate = useNavigate();
  const { toast } = useToast();
  
  const [isRunning, setIsRunning] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [stats, setStats] = useState({
    total_documents: 0,
    total_processed: 0,
    links_created: 0,
    version_mentions: 0,
    related_mentions: 0,
    phantoms_created: 0,
    errors: 0
  });
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [lastLogTime, setLastLogTime] = useState<Date>(new Date());
  const [retryAttempts, setRetryAttempts] = useState(0);
  const [stuckWarning, setStuckWarning] = useState(false);

  useEffect(() => {
    if (!autoRefresh || !sessionId) return;

    const interval = setInterval(() => {
      const now = new Date();
      const timeSinceLastLog = (now.getTime() - lastLogTime.getTime()) / 1000;

      if (timeSinceLastLog > 30 && isRunning && !stuckWarning) {
        setStuckWarning(true);
        toast({
          title: '⚠️ Предупреждение',
          description: `Нет новых логов ${Math.floor(timeSinceLastLog)} секунд. Попытка перезапуска...`,
          variant: 'destructive'
        });
        handleRetry();
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [autoRefresh, sessionId, lastLogTime, isRunning, stuckWarning]);

  const handleRetry = async () => {
    if (retryAttempts >= 3) {
      toast({
        title: '❌ Критическая ошибка',
        description: 'Не удалось перезапустить поиск связей после 3 попыток',
        variant: 'destructive'
      });
      setIsRunning(false);
      setAutoRefresh(false);
      setStuckWarning(false);
      return;
    }

    setRetryAttempts(prev => prev + 1);
    toast({
      title: '🔄 Перезапуск',
      description: `Попытка ${retryAttempts + 1} из 3...`
    });

    setTimeout(() => {
      handleStart();
    }, 5000);
  };

  const handleStart = async () => {
    setIsRunning(true);
    setAutoRefresh(true);
    setProgress(0);
    setStats({
      total_documents: 0,
      total_processed: 0,
      links_created: 0,
      version_mentions: 0,
      related_mentions: 0,
      phantoms_created: 0,
      errors: 0
    });
    setLastLogTime(new Date());
    setRetryAttempts(0);
    setStuckWarning(false);

    try {
      const result = await apiClient.findDocumentRelations();
      
      if (result.session_id) {
        setSessionId(result.session_id);
      }

      setStats({
        total_documents: result.total_documents || 0,
        total_processed: result.total_processed || 0,
        links_created: result.links_created || 0,
        version_mentions: result.version_mentions || 0,
        related_mentions: result.related_mentions || 0,
        phantoms_created: result.phantoms_created || 0,
        errors: result.errors || 0
      });

      if (result.status === 'completed') {
        setProgress(100);
        setIsRunning(false);
        setAutoRefresh(false);
        toast({
          title: '🎉 Поиск связей завершён!',
          description: `Обработано: ${result.total_processed} документов`
        });
      }
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось запустить поиск связей',
        variant: 'destructive'
      });
      setIsRunning(false);
      setAutoRefresh(false);
    }
  };

  const handleStop = () => {
    setIsRunning(false);
    setAutoRefresh(false);
    toast({
      title: 'Остановлено',
      description: 'Поиск связей остановлен вручную'
    });
  };

  const handleLogUpdate = (newLog: any) => {
    setLastLogTime(new Date());
    setStuckWarning(false);

    if (newLog.step === 'document_completed' && newLog.details?.stats) {
      setStats(prev => ({
        total_documents: prev.total_documents,
        total_processed: prev.total_processed + 1,
        links_created: prev.links_created + (newLog.details.stats.links_created || 0),
        version_mentions: prev.version_mentions + (newLog.details.stats.version_mentions || 0),
        related_mentions: prev.related_mentions + (newLog.details.stats.related_mentions || 0),
        phantoms_created: prev.phantoms_created + (newLog.details.stats.phantoms_created || 0),
        errors: prev.errors + (newLog.details.stats.errors || 0)
      }));

      if (stats.total_documents > 0) {
        setProgress((stats.total_processed / stats.total_documents) * 100);
      }
    }

    if (newLog.step === 'session_completed') {
      setIsRunning(false);
      setAutoRefresh(false);
      setProgress(100);
      toast({
        title: '🎉 Поиск связей полностью завершён!',
        description: `Обработано ${newLog.details?.final_stats?.total_processed || 0} документов`
      });
    }
  };

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Заголовок */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/')}
            >
              <Icon name="ArrowLeft" size={18} />
            </Button>
            <div>
              <h1 className="text-3xl font-bold flex items-center gap-2">
                <Icon name="Link" size={32} />
                Автоматический поиск связей
              </h1>
              <p className="text-muted-foreground mt-1">
                Анализ содержимого документов для поиска упоминаний других постановлений
              </p>
            </div>
          </div>
        </div>

        {/* Информация о работе */}
        <Card className="p-6 bg-blue-50 border-blue-200">
          <div className="flex items-start gap-3">
            <Icon name="Info" size={20} className="text-blue-600 mt-0.5" />
            <div className="space-y-2 text-sm">
              <p className="font-semibold text-blue-900">Как работает:</p>
              <ul className="list-disc pl-5 space-y-1 text-blue-800">
                <li>Читает первые страницы каждого документа (DOCX/PDF)</li>
                <li>Находит упоминания вида "постановление №123 от 01.02.2023"</li>
                <li>Автоматически связывает документы в цепочки версий</li>
                <li>Процесс можно остановить и продолжить позже</li>
              </ul>
            </div>
          </div>
        </Card>

        {/* Прогресс и статистика */}
        {(isRunning || stats.total_processed > 0) && (
          <Card className="p-6 space-y-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">Прогресс:</span>
                <span className="text-muted-foreground">
                  {stats.total_processed} / {stats.total_documents} документов
                </span>
              </div>
              <Progress value={progress} className="h-2" />
              <div className="text-center text-sm text-muted-foreground">
                {progress.toFixed(1)}%
              </div>
            </div>

            <div className="grid grid-cols-4 gap-4">
              <div className="text-center p-4 bg-green-50 rounded-lg">
                <div className="text-3xl font-bold text-green-600">
                  {stats.links_created}
                </div>
                <div className="text-sm text-green-700 mt-1">Связей найдено</div>
              </div>
              
              <div className="text-center p-4 bg-blue-50 rounded-lg">
                <div className="text-3xl font-bold text-blue-600">
                  {stats.total_processed}
                </div>
                <div className="text-sm text-blue-700 mt-1">Обработано</div>
              </div>

              <div className="text-center p-4 bg-purple-50 rounded-lg">
                <div className="text-3xl font-bold text-purple-600">
                  {stats.version_mentions}
                </div>
                <div className="text-sm text-purple-700 mt-1">Упоминаний найдено</div>
              </div>

              <div className="text-center p-4 bg-red-50 rounded-lg">
                <div className="text-3xl font-bold text-red-600">
                  {stats.errors}
                </div>
                <div className="text-sm text-red-700 mt-1">Ошибок</div>
              </div>
            </div>

            {isRunning ? (
              <Button
                onClick={handleStop}
                variant="destructive"
                size="lg"
                className="w-full"
              >
                <Icon name="Square" size={20} />
                Остановить
              </Button>
            ) : (
              <Button
                onClick={handleStart}
                size="lg"
                className="w-full"
              >
                <Icon name="Play" size={20} />
                Запустить поиск связей
              </Button>
            )}

            {stuckWarning && (
              <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg flex items-center gap-3">
                <Icon name="AlertTriangle" size={20} className="text-yellow-600" />
                <div className="text-sm text-yellow-800">
                  <p className="font-semibold">Система зависла</p>
                  <p>Попытка {retryAttempts} из 3 перезапуска...</p>
                </div>
              </div>
            )}
          </Card>
        )}

        {!isRunning && stats.total_processed === 0 && (
          <Button
            onClick={handleStart}
            size="lg"
            className="w-full"
          >
            <Icon name="Play" size={20} />
            Запустить поиск связей
          </Button>
        )}

        {/* Детальные логи */}
        <LinkFinderLogs
          sessionId={sessionId}
          autoRefresh={autoRefresh}
          onLogUpdate={handleLogUpdate}
        />
      </div>
    </div>
  );
}
