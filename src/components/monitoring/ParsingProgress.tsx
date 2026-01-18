import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import Icon from '@/components/ui/icon';
import { useEffect, useState } from 'react';
import { apiClient } from '@/config/api';

interface ParsingProgressProps {
  autoRefresh?: boolean;
}

const ParsingProgress = ({ autoRefresh = false }: ParsingProgressProps) => {
  const [progress, setProgress] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const loadProgress = async () => {
    try {
      const data = await apiClient.getParsingProgress();
      setProgress(data);
      setLoading(false);
    } catch (error) {
      console.error('Failed to load parsing progress:', error);
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProgress();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    
    const interval = setInterval(loadProgress, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  if (loading) {
    return (
      <Card className="bg-gradient-to-br from-blue-50 to-indigo-50 border-blue-200">
        <CardContent className="p-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
              <Icon name="Loader" size={20} className="text-blue-600 animate-spin" />
            </div>
            <div>
              <div className="h-4 w-32 bg-blue-100 rounded animate-pulse" />
              <div className="h-3 w-24 bg-blue-100 rounded animate-pulse mt-2" />
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!progress) return null;

  const isCompleted = progress.completed_tasks === progress.total_tasks && progress.total_tasks > 0;
  const hasRunning = progress.running_count > 0;

  return (
    <Card className={`${isCompleted ? 'bg-gradient-to-br from-green-50 to-emerald-50 border-green-200' : 'bg-gradient-to-br from-blue-50 to-indigo-50 border-blue-200'}`}>
      <CardContent className="p-6 space-y-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${isCompleted ? 'bg-green-100' : 'bg-blue-100'}`}>
              {isCompleted ? (
                <Icon name="CheckCircle2" size={20} className="text-green-600" />
              ) : hasRunning ? (
                <Icon name="Loader" size={20} className="text-blue-600 animate-spin" />
              ) : (
                <Icon name="Clock" size={20} className="text-blue-600" />
              )}
            </div>
            <div>
              <h3 className={`font-semibold ${isCompleted ? 'text-green-900' : 'text-blue-900'}`}>
                {isCompleted ? '🎉 Парсинг завершён' : hasRunning ? 'Парсинг в процессе' : 'Готов к запуску'}
              </h3>
              <p className={`text-sm ${isCompleted ? 'text-green-600' : 'text-blue-600'}`}>
                {isCompleted 
                  ? `Все ${progress.total_tasks} задач выполнены` 
                  : `${progress.completed_tasks} из ${progress.total_tasks} задач`}
              </p>
            </div>
          </div>
          <div className={`text-2xl font-bold ${isCompleted ? 'text-green-700' : 'text-blue-700'}`}>
            {progress.progress_percent}%
          </div>
        </div>

        <Progress value={progress.progress_percent} className="h-2" />

        {progress.current_task && (
          <div className="flex items-center gap-2 p-3 bg-white/60 rounded-lg border border-blue-200">
            <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
            <div className="text-sm">
              <span className="font-medium text-gray-900">Обрабатывается:</span>
              <span className="text-gray-700 ml-2">
                {progress.current_task.section}, {progress.current_task.year} год
                {progress.current_task.page > 1 && ` (страница ${progress.current_task.page})`}
              </span>
            </div>
          </div>
        )}

        {progress.failed_count > 0 && (
          <div className="flex items-center gap-2 p-3 bg-red-50 rounded-lg border border-red-200">
            <Icon name="AlertTriangle" size={16} className="text-red-600" />
            <div className="text-sm text-red-700">
              Задач с ошибками: {progress.failed_count}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default ParsingProgress;
