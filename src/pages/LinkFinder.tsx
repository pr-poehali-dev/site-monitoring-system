import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { useToast } from '@/hooks/use-toast';
import Icon from '@/components/ui/icon';

export default function LinkFinder() {
  const navigate = useNavigate();
  const { toast } = useToast();
  
  const [isRunning, setIsRunning] = useState(false);
  const [stats, setStats] = useState({
    processed: 0,
    iteration: 1
  });
  const isRunningRef = useRef(false);

  const handleStart = async (iteration = 1, processedTotal = 0) => {
    setIsRunning(true);
    isRunningRef.current = true;
    
    try {
      const response = await fetch('https://functions.poehali.dev/8c4db4b8-687e-471b-add5-e4517d47764c', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ batch_mode: true, limit: 50 })
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const result = await response.json();

      const processed = result.processed || 0;
      const newProcessedTotal = processedTotal + processed;

      setStats({
        processed: newProcessedTotal,
        iteration
      });

      // Если обработано меньше 50 — закончились документы
      if (processed < 50) {
        setIsRunning(false);
        isRunningRef.current = false;
        toast({
          title: '🎉 Поиск связей полностью завершён!',
          description: `Обработано: ${newProcessedTotal} документов`
        });
      } else if (isRunningRef.current) {
        setTimeout(() => {
          if (isRunningRef.current) {
            handleStart(iteration + 1, newProcessedTotal);
          }
        }, 2000);
      }
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: error instanceof Error ? error.message : 'Не удалось запустить поиск связей',
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

  // Прогресс не показываем точно, т.к. общее количество неизвестно

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
                <Button onClick={() => handleStart()} size="lg">
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

          {stats.processed > 0 && (
            <div className="space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">Обработано документов:</span>
                  <span className="text-2xl font-bold text-primary">
                    {stats.processed}
                  </span>
                </div>
                <div className="text-center text-sm text-muted-foreground">
                  Итерация {stats.iteration}
                </div>
              </div>

              {isRunning && (
                <div className="flex items-center gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                  <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                  <span className="text-sm font-medium text-blue-900">
                    Обработка в фоне... Обрабатывается следующая партия из 50 документов
                  </span>
                </div>
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}