import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import Icon from '@/components/ui/icon';
import { apiClient } from '@/config/api';
import { useToast } from '@/hooks/use-toast';
import DocumentsTab from '@/components/monitoring/DocumentsTab';
import ChangesTab from '@/components/monitoring/ChangesTab';
import LogsTab from '@/components/monitoring/LogsTab';
import SettingsTab from '@/components/monitoring/SettingsTab';

const Index = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSection, setSelectedSection] = useState('all');
  const [selectedYear, setSelectedYear] = useState('all');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('DESC');
  const [documents, setDocuments] = useState<any[]>([]);
  const [changes, setChanges] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [stats, setStats] = useState({ total_documents: 0, changes_this_week: 0, active_sections: 0 });
  const [settings, setSettings] = useState<any>({});
  const [loading, setLoading] = useState(false);
  const [telegramChatId, setTelegramChatId] = useState('');
  const [activeTab, setActiveTab] = useState('documents');
  const [autoRefreshLogs, setAutoRefreshLogs] = useState(false);
  const { toast } = useToast();

  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: currentYear - 2008 }, (_, i) => (2009 + i).toString());

  useEffect(() => {
    loadAllData();
  }, []);

  useEffect(() => {
    loadDocuments();
  }, [searchQuery, selectedSection, selectedYear, sortBy, sortOrder]);

  useEffect(() => {
    if (autoRefreshLogs) {
      const interval = setInterval(async () => {
        try {
          const [logsData, statsData] = await Promise.all([
            apiClient.getLogs(50),
            apiClient.getStats()
          ]);
          setLogs(logsData.logs || []);
          setStats(statsData);
        } catch (error) {
          console.error('Failed to refresh logs:', error);
        }
      }, 3000);

      return () => clearInterval(interval);
    }
  }, [autoRefreshLogs]);

  const loadAllData = async () => {
    try {
      const [statsData, docsData, changesData, logsData, settingsData] = await Promise.all([
        apiClient.getStats(),
        apiClient.getDocuments({ limit: 100 }),
        apiClient.getChanges(50),
        apiClient.getLogs(50),
        apiClient.getSettings()
      ]);
      
      setStats(statsData);
      setDocuments(docsData.documents || []);
      setChanges(changesData.changes || []);
      setLogs(logsData.logs || []);
      setSettings(settingsData.settings || {});
      setTelegramChatId(settingsData.settings?.telegram_chat_id || '');
    } catch (error) {
      console.error('Failed to load data:', error);
    }
  };

  const loadDocuments = async () => {
    try {
      const params: any = { limit: 100 };
      if (searchQuery) params.search = searchQuery;
      if (selectedSection !== 'all') params.section = selectedSection;
      if (selectedYear !== 'all') params.year = selectedYear;
      params.sort_by = sortBy;
      params.sort_order = sortOrder;

      const docsData = await apiClient.getDocuments(params);
      setDocuments(docsData.documents || []);
    } catch (error) {
      console.error('Failed to load documents:', error);
    }
  };

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
      apiClient.runParser(['postanovleniya', 'rasporyazheniya', 'programmy'], years.map(y => parseInt(y)));
      
      toast({
        title: 'Парсинг запущен в фоне',
        description: `Система начала сканирование документов за ${years.length} лет (2009-${currentYear}). Логи обновляются автоматически.`
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

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Icon name="FileSearch" size={24} className="text-primary" />
            <h1 className="text-xl font-semibold text-gray-900">Мониторинг документов</h1>
          </div>
          <Badge variant="outline" className="gap-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            Активен
          </Badge>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-gray-600">Всего документов</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-end justify-between">
                <div className="text-3xl font-bold text-gray-900">{stats.total_documents.toLocaleString()}</div>
                <Icon name="FileText" size={20} className="text-gray-400" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-gray-600">Изменений за неделю</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-end justify-between">
                <div className="text-3xl font-bold text-gray-900">{stats.changes_this_week}</div>
                <Icon name="TrendingUp" size={20} className="text-green-500" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-gray-600">Активных разделов</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-end justify-between">
                <div className="text-3xl font-bold text-gray-900">{stats.active_sections}</div>
                <Icon name="Folders" size={20} className="text-gray-400" />
              </div>
            </CardContent>
          </Card>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList>
            <TabsTrigger value="documents" className="gap-2">
              <Icon name="FileText" size={16} />
              Документы
            </TabsTrigger>
            <TabsTrigger value="changes" className="gap-2">
              <Icon name="Bell" size={16} />
              Изменения
            </TabsTrigger>
            <TabsTrigger value="logs" className="gap-2">
              <Icon name="ScrollText" size={16} />
              Логи
            </TabsTrigger>
            <TabsTrigger value="settings" className="gap-2">
              <Icon name="Settings" size={16} />
              Настройки
            </TabsTrigger>
          </TabsList>

          <TabsContent value="documents">
            <DocumentsTab
              documents={documents}
              searchQuery={searchQuery}
              setSearchQuery={setSearchQuery}
              selectedSection={selectedSection}
              setSelectedSection={setSelectedSection}
              selectedYear={selectedYear}
              setSelectedYear={setSelectedYear}
              years={years}
              sortBy={sortBy}
              sortOrder={sortOrder}
              handleSort={handleSort}
              getSortIcon={getSortIcon}
              formatDate={formatDate}
              formatDateTime={formatDateTime}
              formatFileSize={formatFileSize}
            />
          </TabsContent>

          <TabsContent value="changes">
            <ChangesTab
              changes={changes}
              formatDateTime={formatDateTime}
              formatFileSize={formatFileSize}
            />
          </TabsContent>

          <TabsContent value="logs">
            <LogsTab
              logs={logs}
              autoRefreshLogs={autoRefreshLogs}
              setAutoRefreshLogs={setAutoRefreshLogs}
              formatDateTime={formatDateTime}
            />
          </TabsContent>

          <TabsContent value="settings">
            <SettingsTab
              telegramChatId={telegramChatId}
              setTelegramChatId={setTelegramChatId}
              handleSaveSettings={handleSaveSettings}
              handleRunParser={handleRunParser}
              loading={loading}
            />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
};

export default Index;
