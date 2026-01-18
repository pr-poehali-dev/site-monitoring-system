import { apiClient } from '@/config/api';
import { useToast } from '@/hooks/use-toast';

interface UseMonitoringActionsProps {
  telegramChatId: string;
  years: string[];
  setLoading: (loading: boolean) => void;
  setActiveTab: (tab: string) => void;
  setAutoRefreshLogs: (auto: boolean) => void;
  loadAllData: () => Promise<void>;
  loadAnalytics: () => Promise<void>;
  sortBy: string;
  sortOrder: string;
  setSortBy: (field: string) => void;
  setSortOrder: (order: string) => void;
}

export const useMonitoringActions = ({
  telegramChatId,
  years,
  setLoading,
  setActiveTab,
  setAutoRefreshLogs,
  loadAllData,
  loadAnalytics,
  sortBy,
  sortOrder,
  setSortBy,
  setSortOrder
}: UseMonitoringActionsProps) => {
  const { toast } = useToast();

  const handleSaveSettings = async () => {
    try {
      await apiClient.updateSettings({ telegram_chat_id: telegramChatId });
      toast({
        title: 'Настройки сохранены',
        description: `Telegram Chat ID: ${telegramChatId}`
      });
      await loadAllData();
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось сохранить настройки',
        variant: 'destructive'
      });
    }
  };

  const handleRunParser = async () => {
    setLoading(true);
    setActiveTab('logs');
    setAutoRefreshLogs(true);
    
    try {
      await apiClient.runParser(['programmy', 'rasporyazheniya', 'postanovleniya'], years.map(y => parseInt(y)));
      
      // Запускаем автопродолжение в цикле
      const continueLoop = async () => {
        try {
          const result = await apiClient.continueParsing(false);
          
          if (result.status === 'continued') {
            // Есть ещё задачи, продолжаем через 1 сек
            setTimeout(continueLoop, 1000);
          } else if (result.status === 'all_completed') {
            toast({
              title: '🎉 Парсинг завершён!',
              description: result.message || 'Все разделы обработаны'
            });
            setAutoRefreshLogs(false);
          }
        } catch (error) {
          console.error('Continue parsing failed:', error);
          // Повторяем через 3 сек при ошибке
          setTimeout(continueLoop, 3000);
        }
      };
      
      setTimeout(continueLoop, 2000);
      
      toast({
        title: 'Парсинг запущен',
        description: `Обрабатываем документы...`
      });
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось запустить парсинг',
        variant: 'destructive'
      });
      setAutoRefreshLogs(false);
    } finally {
      setLoading(false);
    }
  };

  const handleContinueParsing = async () => {
    setActiveTab('logs');
    setAutoRefreshLogs(true);
    
    const continueLoop = async () => {
      try {
        const result = await apiClient.continueParsing(false);
        
        if (result.status === 'continued') {
          // Есть ещё задачи, продолжаем через 1 сек
          setTimeout(continueLoop, 1000);
        } else if (result.status === 'all_completed') {
          toast({
            title: '🎉 Парсинг завершён!',
            description: result.message || 'Все разделы обработаны'
          });
          setAutoRefreshLogs(false);
        } else if (result.status === 'no_pending') {
          toast({
            title: 'Нет незавершённых задач',
            description: 'Все парсинги завершены'
          });
          setAutoRefreshLogs(false);
        }
      } catch (error) {
        console.error('Continue parsing failed:', error);
        // Повторяем через 3 сек при ошибке
        setTimeout(continueLoop, 3000);
      }
    };
    
    continueLoop();
  };

  const handleForceReparse = async () => {
    const confirmed = window.confirm(
      '⚠️ Внимание! Это полностью перезапустит парсинг всех документов с нуля.\n\n' +
      'Все годы (2009-2026) будут спарсены заново.\n' +
      'Процесс может занять ~1 час.\n\n' +
      'Продолжить?'
    );

    if (!confirmed) return;

    setLoading(true);
    setActiveTab('logs');
    setAutoRefreshLogs(true);
    
    try {
      await apiClient.runParser(['programmy', 'rasporyazheniya', 'postanovleniya'], years.map(y => parseInt(y)), true);
      
      // Запускаем автопродолжение в цикле
      const continueLoop = async () => {
        try {
          const result = await apiClient.continueParsing(false);
          
          if (result.status === 'continued') {
            setTimeout(continueLoop, 1000);
          } else if (result.status === 'all_completed') {
            toast({
              title: '🎉 Перепарсинг завершён!',
              description: result.message || 'Все разделы обработаны заново'
            });
            setAutoRefreshLogs(false);
          }
        } catch (error) {
          console.error('Continue parsing failed:', error);
          setTimeout(continueLoop, 3000);
        }
      };
      
      setTimeout(continueLoop, 2000);
      
      toast({
        title: '🔄 Полный перепарсинг запущен',
        description: `Обрабатываем все документы заново...`
      });
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось запустить перепарсинг',
        variant: 'destructive'
      });
      setAutoRefreshLogs(false);
    } finally {
      setLoading(false);
    }
  };

  const handleCleanLogs = async () => {
    const confirmed = window.confirm(
      'Удалить логи парсинга старше 7 дней?\n\n' +
      'Это поможет очистить базу данных от старых записей.'
    );

    if (!confirmed) return;

    try {
      const result = await apiClient.cleanOldLogs(7);
      
      toast({
        title: '🗑️ Логи очищены',
        description: result.message || `Удалено ${result.deleted} записей`
      });

      setTimeout(() => {
        loadAllData();
      }, 1000);
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось очистить логи',
        variant: 'destructive'
      });
    }
  };

  const handleFullReset = async () => {
    const confirmed = window.confirm(
      '🚨 КРИТИЧЕСКОЕ ДЕЙСТВИЕ!\n\n' +
      'Это ПОЛНОСТЬЮ очистит базу данных:\n' +
      '- Все документы\n' +
      '- Все файлы\n' +
      '- Историю изменений\n' +
      '- Все логи\n\n' +
      'После этого нужно будет запустить парсинг заново.\n\n' +
      'Вы уверены?'
    );

    if (!confirmed) return;

    const doubleConfirm = window.confirm(
      '⚠️ Последнее предупреждение!\n\n' +
      'Данные будут удалены БЕЗВОЗВРАТНО.\n\n' +
      'Точно продолжить?'
    );

    if (!doubleConfirm) return;

    setLoading(true);

    try {
      const result = await apiClient.fullReset();
      
      toast({
        title: '✅ База данных очищена',
        description: `Удалено ${result.total_deleted} записей. Теперь можно запустить парсинг.`
      });

      setTimeout(() => {
        loadAllData();
        loadAnalytics();
      }, 1000);
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось очистить базу данных',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (!bytes) return '-';
    const kb = bytes / 1024;
    if (kb < 1024) return `${kb.toFixed(1)} КБ`;
    return `${(kb / 1024).toFixed(1)} МБ`;
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('ru-RU', { 
      day: '2-digit', 
      month: '2-digit', 
      year: 'numeric' 
    });
  };

  const formatDateTime = (dateStr: string) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const handleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'DESC' ? 'ASC' : 'DESC');
    } else {
      setSortBy(field);
      setSortOrder('DESC');
    }
  };

  const getSortIcon = (field: string) => {
    if (sortBy !== field) return null;
    return sortOrder === 'DESC' ? '↓' : '↑';
  };

  return {
    handleSaveSettings,
    handleRunParser,
    handleContinueParsing,
    handleForceReparse,
    handleCleanLogs,
    handleFullReset,
    formatFileSize,
    formatDate,
    formatDateTime,
    handleSort,
    getSortIcon
  };
};