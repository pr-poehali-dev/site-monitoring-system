import { useState, useEffect, useRef } from 'react';
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
  const [stats, setStats] = useState({
    total_documents: 0,
    remaining: 0,
    iteration: 1
  });
  const isRunningRef = useRef(false);

  const handleStart = async (iteration = 1) => {
    setIsRunning(true);
    isRunningRef.current = true;
    
    try {
      const response = await fetch('https://functions.poehali.dev/8c4db4b8-687e-471b-add5-e4517d47764c', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'find_relations', auto_loop: false, iteration })
      });
      
      const result = await response.json();
      
      console.log('LinkFinder: API response', result);
      
      if (result.session_id) {
        setSessionId(result.session_id);
        console.log('LinkFinder: sessionId set to', result.session_id);
      }

      setStats({
        total_documents: result.total_documents || 0,
        remaining: result.remaining || 0,
        iteration: result.iteration || iteration
      });

      if (result.status === 'all_completed' || result.remaining === 0) {
        setIsRunning(false);
        isRunningRef.current = false;
        toast({
          title: '🎉 Поиск связей полностью завершён!',
          description: `Обработано: ${result.total_documents} документов`
        });
      } else if (result.remaining > 0 && isRunningRef.current) {
        setTimeout(() => {
          if (isRunningRef.current) {
            handleStart(iteration + 1);
          }
        }, 2000);
      }
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось запустить поиск связей',
        variant: 'destructive'
      });
      setIsRunning(false);
      isRunningRef.current = false;
    }
  };

  const handleStop = () => {
    setIsRunning(false);
    isRunningRef.current = false;
    toast({
      title: 'Остановлено',
      description: 'Поиск связей будет остановлен после текущей итерации'
    });
  };

  const progress = stats.total_documents > 0 
    ? ((stats.total_documents - stats.remaining) / stats.total_documents) * 100 
    : 0;

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
                <li>Работает в фоне, можно закрыть страницу</li>
              </ul>
            </div>
          </div>
        </Card>

        {/* Прогресс и управление */}
        <Card className="p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold">Процесс обработки</h2>
            <div className="flex gap-2">
              {!isRunning ? (
                <Button onClick={handleStart} size="lg">
                  <Icon name="Play" size={18} className="mr-2" />
                  Запустить
                </Button>
              ) : (
                <Button onClick={handleStop} variant="destructive" size="lg">
                  <Icon name="Pause" size={18} className="mr-2" />
                  Остановить
                </Button>
              )}
            </div>
          </div>

          {stats.total_documents > 0 && (
            <>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">Прогресс:</span>
                  <span className="text-muted-foreground">
                    {stats.total_documents - stats.remaining} / {stats.total_documents} документов
                  </span>
                </div>
                <Progress value={progress} className="h-2" />
                <div className="text-center text-sm text-muted-foreground">
                  {progress.toFixed(1)}% • Итерация {stats.iteration}
                </div>
              </div>

              {stats.remaining > 0 && isRunning && (
                <div className="flex items-center gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                  <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                  <span className="text-sm font-medium text-blue-900">
                    Обработка в фоне... Осталось: {stats.remaining} документов
                  </span>
                </div>
              )}
            </>
          )}
        </Card>

        {/* Логи */}
        <LinkFinderLogs 
          sessionId={sessionId} 
          autoRefresh={isRunning}
        />
      </div>
    </div>
  );
}